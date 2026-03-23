import os
import json
import time
import numpy as np
import redis
import schrodinger_mod

H_BAR = 1.054e-34
MASS = 9.11e-31
DT = 0.0005
NUM_STEPS = 1

PUBLISH_INTERVAL = 500
TTL = 10800 # Long enough that it won't expire mid-work
MAX_HANG_TIME = 3600

RUN_ID = os.getenv("RUN_ID", "-1")
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_channel = f"{RUN_ID}:{os.environ.get('REDIS_CHANNEL', 'wave_channel')}"

# Helper function for polling redis for values
# Since multiple parts in program cannot continue without info being published
def poll_redis_raw(r, key, sleep_interval=0.05, timeout=MAX_HANG_TIME, fail_quietly=False, default=None, job_idx=None):
    start = time.time()
    #print(f"[J{job_idx}-POLL-START] Waiting for key: {key}") 
    
    while not r.exists(key):
        if timeout is not None and (time.time() - start) > timeout:
            if fail_quietly:
                print((f"[J{job_idx}-WARN] Key '{key}' not found in Redis within timeout."))
                return default
            
            else:
                raise TimeoutError(f"[J{job_idx}-ERROR] Key '{key}' not found in Redis within timeout.")
            
        time.sleep(sleep_interval)

    #print(f"[J{job_idx}-POLL-END] Received key: {key}") 
    return r.get(key) # Do not .decode(), since not always expecting strings/json

# @NOTE: Alternative options to sharing via Redis:
# B. Compute initial matrix before launching workers, save to object storage (con: shared filesystem or S3 setup, so no).
# C. Modify the Fortran function to only compute chunk. Favoring this option but am avoiding Fortran edits rn.
def get_initial_state(r, job_idx, grid_size):
    init_key = f"{RUN_ID}:initial_matrix"

    if job_idx == 0:  # (First job only) calls Fortran module to compute initial state
        matrix = np.zeros((grid_size, grid_size), dtype=np.float64, order="F")
        schrodinger_mod.schrodinger_mod.compute_wave_matrix(matrix=matrix, size_n=grid_size, num_steps=NUM_STEPS, h_bar=H_BAR, mass=MASS) 
        r.set(init_key, matrix.tobytes(), ex=TTL) # Publish initial grid for other workers to use
        print(f"[J{job_idx}-WRITE] Computed and stored initial grid in Redis.")
        
    else:
        raw = poll_redis_raw(r, init_key, job_idx=job_idx)
        matrix = np.frombuffer(raw, dtype=np.float64).copy().reshape((grid_size, grid_size))
        print(f"[J{job_idx}-READ] Retrieved initial grid from Redis.")
    
    return matrix

# Helper function returns partition start/end 
def get_partition_edges(job_idx, total_jobs, grid_size):
    rows_per_job = grid_size // total_jobs
    start = job_idx * rows_per_job
    end = start + rows_per_job if job_idx != total_jobs - 1 else grid_size
    return start, end

def deserialize_row(raw):
    return np.frombuffer(raw, dtype=np.complex128) if raw else None

def push_edges(pipe, job_idx, chunk, step):
    top_key = f"{RUN_ID}:worker:{job_idx}:top:{step}"
    bot_key = f"{RUN_ID}:worker:{job_idx}:bottom:{step}"

    pipe.set(top_key, chunk[0, :].tobytes(), ex=TTL)
    pipe.set(bot_key, chunk[-1, :].tobytes(), ex=TTL)

    print(f"[J{job_idx}-WRITE] Step {step}: wrote edges to [{top_key}] and [{bot_key}].")

# Blocks until read
def pull_neighbor_edges(r, job_idx, total_jobs, step):
    top_neighbor = None
    bot_neighbor = None

    if job_idx > 0: 
        key = f"{RUN_ID}:worker:{job_idx-1}:bottom:{step}"
        raw = poll_redis_raw(r, key, timeout=None, job_idx=job_idx) 
        top_neighbor = deserialize_row(raw)

        print(f"[J{job_idx}-READ] Step {step}: Received top neighbor from worker {job_idx-1} (key: {key}, shape={top_neighbor.shape}).")

    if job_idx < total_jobs - 1:
        key = f"{RUN_ID}:worker:{job_idx+1}:top:{step}"
        raw = poll_redis_raw(r, key, timeout=None, job_idx=job_idx) 
        bot_neighbor = deserialize_row(raw)
        
        print(f"[J{job_idx}-READ] Step {step}: Received bottom neighbor from worker {job_idx+1} (key: {key}, shape={bot_neighbor.shape}).")
    
    return top_neighbor, bot_neighbor

def compute_laplacian(grid):
    # np.roll shifts the grid to easily grab adjacent cells
    return (
        np.roll(grid, -1, axis=0) +   # Up neighbor
        np.roll(grid, 1, axis=0) +    # Down neighbor
        np.roll(grid, -1, axis=1) +   # Right neighbor
        np.roll(grid, 1, axis=1) -    # Left neighbor
        4 * grid                      # Center cell * 4
    )

# Forces outer edges of the grid to stay at 0 so the wave bounces.
def apply_boundary(grid):
    grid[0, :] = 0
    grid[-1, :] = 0
    grid[:, 0] = 0
    grid[:, -1] = 0

def trim_ghost_rows(grid, top_neighbor, bot_neighbor):
    if top_neighbor is not None:
        grid = grid[1:, :]
    if bot_neighbor is not None:
        grid = grid[:-1, :]
    return grid

def build_extended(chunk, top_neighbor, bot_neighbor):
    rows = []
    if top_neighbor is not None:
        rows.append(top_neighbor)
    rows.append(chunk)
    if bot_neighbor is not None:
        rows.append(bot_neighbor)

    return np.vstack(rows)

def main():
    # Read environment variables
    total_steps = int(os.getenv("TOTAL_STEPS", "100")) 
    grid_size = int(os.getenv("GRID_SIZE", "200"))
    
    job_idx = int(os.environ.get("JOB_COMPLETION_INDEX", "0"))  # 0-based worker index
    total_jobs = int(os.getenv("TOTAL_JOBS", "10"))    

    # Setup redis connection
    r = redis.Redis(host=redis_host, port=redis_port)

    # Determine current worker's reponsiblity
    start_row, end_row = get_partition_edges(job_idx, total_jobs, grid_size)
    print(f"[J{job_idx}-START] Planning {total_steps} steps for rows {start_row}-{end_row-1}.")

    # Prepare/get first frame (worker 0 uses Fortran module to compute it)
    matrix = get_initial_state(r, job_idx, grid_size) # Will block until it's avilable
    chunk = matrix[start_row:end_row, :].astype(np.complex128)
    print(f"Job {job_idx} published/Received initial matrix.")

    for step in range(total_steps): # "Animation" loop
        ready_key = f"{RUN_ID}:ready:{step}"
        go_key = f"{RUN_ID}:go:{step}"

        # [Worker Boundary Exchange]
        push_pipe = r.pipeline()
        
        push_edges(push_pipe, job_idx, chunk, step)
        push_pipe.execute()       # Push edges first, then
        count = r.incr(ready_key) # mark this worker as ready

        if count >= total_jobs:  # If last worker to finish, signal "go", 
            r.setnx(go_key, 1) 
            # Temporarily avoid cleanup for now. 
            # Possible issue: A deletes ready:0 while B hasn't read it yet.
            #if step > 0:    # & clean up stale memory to prevent buildup.
            #    pipe.delete(f"ready:{step-1}", f"go:{step-1}")
        
        # Wait for "go" to be published to check if its safe to read. 
        sleep = 0.0005         
        start = time.time() 
        while not r.exists(go_key):
            if time.time() - start > MAX_HANG_TIME:
                raise RuntimeError(f'Stuck waiting for "go" at step {step}')
            time.sleep(sleep)

        top_neighbor, bot_neighbor = pull_neighbor_edges(r, job_idx, total_jobs, step) 

        # [Computation]
        extended = build_extended(chunk, top_neighbor, bot_neighbor) #  Edges need to see neighbors for laplacian
        laplacian = compute_laplacian(extended)               # Neighbor math: Up + Down + Left + Right - 4*(Center)
        laplacian = trim_ghost_rows(laplacian, top_neighbor, bot_neighbor) 

        chunk += 1j * laplacian * DT # Update wave
        apply_boundary(chunk)        # Force outer edges of grid to stay at 0 so the wave bounces.

        # [Periodically Publish to Redis Server]
        if step % PUBLISH_INTERVAL == 0:
            message = {"worker": job_idx, "step": step, "start_row": start_row, "data": np.abs(chunk).tolist()}

            r.publish(redis_channel, json.dumps(message))
            print(f"[J{job_idx}-PUB] Step {step}: published chunk to channel [{redis_channel}]")

    print(f"[J{job_idx}-FIN] {total_steps} steps completed for rows {start_row}-{end_row-1}.")

if __name__ == "__main__":
    main()