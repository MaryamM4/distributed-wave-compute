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

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_channel = os.environ.get("REDIS_CHANNEL", "wave_channel")


# Helper function for polling redis for values
# Since multiple parts in program cannot continue without info being published
def poll_redis_raw(r, key, sleep_interval=0.05, timeout=None, fail_quetly=False, default=None):
    start = time.time()

    while not r.exists(key):
        if timeout is not None and (time.time() - start) > timeout:
            if fail_quetly:
                print((f"[WARN] Key '{key}' not found in Redis within timeout."))
                return default
            
            else:
                raise TimeoutError(f"[ERROR] Key '{key}' not found in Redis within timeout.")
            
        time.sleep(sleep_interval)

    return r.get(key) # Do not .decode(), since not always expecting strings/json

# @NOTE: Alternative options to sharing via Redis:
# B. Compute initial matrix before launching workers, save to object storage (con: shared filesystem or S3 setup, so no).
# C. Modify the Fortran function to only compute chunk. Favoring this option but am avoiding Fortran edits rn.
def get_initial_state(r, job_idx, grid_size):
    if job_idx == 0:  # (First job only) calls Fortran module to compute initial state
        matrix = np.zeros((grid_size, grid_size), dtype=np.float64, order="F")
        schrodinger_mod.schrodinger_mod.compute_wave_matrix(matrix=matrix, grid_size=grid_size, num_steps=NUM_STEPS, h_bar=H_BAR, mass=MASS) 

        # Publish initial grid for other workers to use
        r.set("initial_matrix", matrix.tobytes()) 

    else:
        raw = poll_redis_raw(r, "initial_matrix")
        matrix = np.frombuffer(raw, dtype=np.float64).copy().reshape((grid_size, grid_size))
    
    return matrix

# Helper function returns partition start/end 
def get_partition_edges(job_idx, total_jobs, grid_size):
    rows_per_job = grid_size // total_jobs
    start = job_idx * rows_per_job
    end = start + rows_per_job if job_idx != total_jobs - 1 else grid_size
    return start, end

def serialize_complex_row(row):
    return json.dumps([{"r": float(x.real), "i": float(x.imag)} for x in row])
def deserialize_complex_row(data):
    arr = json.loads(data)
    return np.array([complex(x["r"], x["i"]) for x in arr])

def push_edges(r, job_idx, chunk):
    r.set(f"worker:{job_idx}:top", serialize_complex_row(chunk[0, :]))
    r.set(f"worker:{job_idx}:bottom", serialize_complex_row(chunk[-1, :]))

def pull_neighbor_edges(r, job_idx, total_jobs):
    top_neighbor = None
    bottom_neighbor = None

    # @TODO: Am debating wether to use poll_redis_raw or if skipping
    #        unpublished neighbors is acceptable for speed. Not critical rn.
    if job_idx > 0: 
        data = r.get(f"worker:{job_idx-1}:bottom")
        if data:
            top_neighbor = deserialize_complex_row(data)

    if job_idx < total_jobs - 1:
        data = r.get(f"worker:{job_idx+1}:top")
        if data:
            bottom_neighbor = deserialize_complex_row(data)
    
    return top_neighbor, bottom_neighbor

def compute_laplacian(grid):
    # np.roll shifts the grid to easily grab adjacent cells
    return ( 
        np.roll(grid, -1, axis=0) +  # Up neighbor
        np.roll(grid, 1, axis=0) +   # Down neighbor
        np.roll(grid, -1, axis=1) +  # Right neighbor
        np.roll(grid, 1, axis=1) -   # Left neighbor
        4 * grid                     # Center cell * 4
    )

# Forces outer edges of the grid to stay at 0 so the wave bounces.
def apply_boundary(grid):
    grid[0, :] = 0
    grid[-1, :] = 0
    grid[:, 0] = 0
    grid[:, -1] = 0

def trim_ghost_rows(grid, top_neighbor, bottom_neighbor):
    if top_neighbor is not None:
        grid = grid[1:, :]
    if bottom_neighbor is not None:
        grid = grid[:-1, :]
    return grid

def main():
    # Read environment variables
    total_steps = int(os.getenv("TOTAL_STEPS", "100")) 
    grid_size = int(os.getenv("GRID_SIZE", "200"))
    
    job_idx = int(os.environ.get("JOB_COMPLETION_INDEX", "0"))  # 0-based worker index
    total_jobs = int(os.getenv("TOTAL_JOBS", "10"))    

    # Setup redis connection
    r = redis.Redis(host=redis_host, port=redis_port)

    # Prepare/get first frame (worker 0 uses Fortran module to compute it)
    matrix = get_initial_state(r, job_idx, grid_size)

    # Determine current worker's reponsiblity
    start_row, end_row = get_partition_edges(job_idx, total_jobs, grid_size)
    print(f"Job {job_idx} working on rows {start_row}-{end_row-1}.")

    chunk = matrix[start_row:end_row, :].astype(np.complex128)
    extended = chunk # "Extended" will accomodate neighbors 

    for step in range(total_steps): # "Animation" loop
        # Boundary exchange 
        push_edges(r, job_idx, chunk)
        time.sleep(0.001) # To avoid Redis thrashing & provide sync delay before neighbors write
        top_neighbor, bottom_neighbor = pull_neighbor_edges(r, job_idx, total_jobs)

        # Edges need to see neighbors for laplacian
        extended[1:-1, :] = chunk    # Fill center (chunk)
        if top_neighbor is not None: # Fill ghost rows (neighbors)
            extended = np.vstack([top_neighbor, extended])
        if bottom_neighbor is not None:
            extended = np.vstack([extended, bottom_neighbor])

        laplacian = compute_laplacian(extended)  # Neighbor math: Up + Down + Left + Right - 4*(Center)
        laplacian = trim_ghost_rows(laplacian, top_neighbor, bottom_neighbor) 

        chunk += 1j * laplacian * DT # Update wave
        apply_boundary(laplacian)    # Force outer edges of grid to stay at 0 so the wave bounces.

        # Prepare message and publish to redis (periodically to avoid spam)
        if step % PUBLISH_INTERVAL == 0:
            message = {"worker": job_idx, "step": step, "start_row": start_row, "data": np.abs(chunk).tolist()}
            r.publish("wave_channel", json.dumps(message))

            print(f"Worker {job_idx} Published step {step}")


    print(f"Worker {job_idx} completed rows {start_row}-{end_row-1}.")

if __name__ == "__main__":
    main()