import os
import json
import time
import numpy as np
import redis
import schrodinger_mod
import sys
import logging

DEBUG_MODE = False
LINGER_SECONDS = 600 # Keep pod alive for 10 mins

REMOTE_DIR="/tmp"

H_BAR = 1.054e-34
MASS = 9.11e-31
DT = 0.0005
NUM_STEPS = 1
step_width = 2

PUBLISH_INTERVAL = 500
TTL = 10800 # Long enough that it won't expire mid-work
MAX_HANG_TIME = 3600

RUN_ID = os.getenv("RUN_ID", "-1")
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))
redis_channel = f"{RUN_ID}:{os.environ.get('REDIS_CHANNEL', 'wave_channel')}"

def setup_logger(job_idx):
    logger = logging.getLogger(f"worker_{job_idx}")
    level = logging.DEBUG if DEBUG_MODE else logging.INFO
    logger.setLevel(level)

    logger.propagate = False # Logs can duplicate in some environments
    if logger.hasHandlers(): # Prevent duplicate handlers if re-run
        logger.handlers.clear()  

    formatter = logging.Formatter(fmt=f"%(asctime)s [run:{RUN_ID}] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # File output (persistent in container)
    file_handler = logging.FileHandler(f"{REMOTE_DIR}/worker_{job_idx}.log", delay=False) 
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Console output (for kubectl logs)
    console_handler = logging.StreamHandler(sys.stdout) 
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# Helper function for polling redis for values, since multiple parts in program cannot continue without info being published
def poll_redis_raw(r, key, logger, sleep_interval=0.05, timeout=MAX_HANG_TIME, fail_quietly=False, default=None, job_idx=None):
    start = time.time()

    logger.debug(f"Polling waiting for key {key} (start: {start:.3f}).")
    
    while not r.exists(key):
        if timeout is not None and (time.time() - start) > timeout:
            mssg = f"Key '{key}' not found in Redis within timeout."

            if fail_quietly:
                logger.warning(f"{mssg} Failed quietly.") 
                return default
            
            else:
                logger.error(mssg)
                raise TimeoutError(mssg)
            
        time.sleep(sleep_interval)

    wait_time = time.time() - start
    logger.debug(f"[POLL] Waited {wait_time:.3f}s for key {key}.")

    return r.get(key) # Do not .decode(), since not always expecting strings/json

# @NOTE: Alternative options to sharing via Redis:
# B. Compute initial matrix before launching workers, save to object storage (con: shared filesystem or S3 setup, so no).
# C. Modify the Fortran function to only compute chunk. Favoring this option but am avoiding Fortran edits rn.
def get_initial_state(r, job_idx, grid_size, logger):
    init_key = f"{RUN_ID}:initial_matrix"

    if job_idx == 0:  # (First job only) calls Fortran module to compute initial state
        matrix = np.zeros((grid_size, grid_size), dtype=np.float64, order="F")
        schrodinger_mod.schrodinger_mod.compute_wave_matrix(matrix=matrix, size_n=grid_size, num_steps=NUM_STEPS, h_bar=H_BAR, mass=MASS) 
        r.set(init_key, matrix.tobytes(), ex=TTL) # Publish initial grid for other workers to use
        logger.info(f"[WRITE] Computed and stored initial grid in Redis.")
        
    else:
        raw = poll_redis_raw(r, init_key, job_idx=job_idx, logger=logger)
        matrix = np.frombuffer(raw, dtype=np.float64).copy().reshape((grid_size, grid_size))
        logger.info(f"[READ] Retrieved initial grid from Redis.")
    
    return matrix

# Helper function returns partition start/end 
def get_partition_edges(job_idx, total_jobs, grid_size):
    rows_per_job = grid_size // total_jobs
    start = job_idx * rows_per_job
    end = start + rows_per_job if job_idx != total_jobs - 1 else grid_size
    return start, end

def deserialize_row(raw):
    return np.frombuffer(raw, dtype=np.complex128) if raw else None

def push_edges(pipe, job_idx, chunk, step, logger):
    top_key = f"{RUN_ID}:worker:{job_idx}:top:{step}"
    bot_key = f"{RUN_ID}:worker:{job_idx}:bottom:{step}"

    pipe.set(top_key, chunk[0, :].tobytes(), ex=TTL)
    pipe.set(bot_key, chunk[-1, :].tobytes(), ex=TTL)

    logger.info(f"[WRITE][step {step:<{step_width}d}] wrote edges to [{top_key}] and [{bot_key}].")

# Blocks until read
def pull_neighbor_edges(r, job_idx, total_jobs, step, logger):
    top_neighbor = None
    bot_neighbor = None

    if job_idx > 0: 
        key = f"{RUN_ID}:worker:{job_idx-1}:bottom:{step}"
        raw = poll_redis_raw(r, key, timeout=None, job_idx=job_idx, logger=logger) 
        top_neighbor = deserialize_row(raw)

        t_shape = top_neighbor.shape if top_neighbor is not None else None
        logger.info(f"[READ][step {step:<{step_width}d}] Received TOP neighbor from worker {job_idx-1} (key: {key}, shape={t_shape}).")

    if job_idx < total_jobs - 1:
        key = f"{RUN_ID}:worker:{job_idx+1}:top:{step}"
        raw = poll_redis_raw(r, key, timeout=None, job_idx=job_idx, logger=logger) 
        bot_neighbor = deserialize_row(raw)
        
        b_shape = bot_neighbor.shape if bot_neighbor is not None else None
        logger.info(f"[READ][step {step:<{step_width}d}] Received BOTTOM neighbor from worker {job_idx+1} (key: {key}, shape={b_shape}).")
    
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
    step_width = len(str(total_steps))
    grid_size = int(os.getenv("GRID_SIZE", "200"))
    
    job_idx = int(os.environ.get("JOB_COMPLETION_INDEX", "0"))  # 0-based worker index
    total_jobs = int(os.getenv("TOTAL_JOBS", "10"))    

    # Setup redis connection
    r = redis.Redis(host=redis_host, port=redis_port)

    # Determine current worker's reponsiblity
    start_row, end_row = get_partition_edges(job_idx, total_jobs, grid_size)

    # Setup logging
    logger = setup_logger(job_idx)

    logger.info("Kubernetes containers are ephemeral; /tmp logs will be lost unless copied.")
    logger.info("Use kubectl cp or your collect_worker_logs script (Linger duration: {LINGER_SECONDS} seconds).")

    logger.info(f"[START] Planning {total_steps} steps for rows {start_row}-{end_row-1}.")

    # Prepare/get first frame (worker 0 uses Fortran module to compute it)
    matrix = get_initial_state(r, job_idx, grid_size, logger=logger) # Will block until it's avilable
    chunk = matrix[start_row:end_row, :].astype(np.complex128)

    for step in range(total_steps): # "Animation" loop
        step_start = time.time()
        ready_key = f"{RUN_ID}:ready:{step}"
        go_key = f"{RUN_ID}:go:{step}"

        # [Worker Boundary Exchange]
        push_pipe = r.pipeline()
        
        push_edges(push_pipe, job_idx, chunk, step, logger=logger)
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
        wait_start = time.time() 
        while not r.exists(go_key):
            if time.time() - wait_start > MAX_HANG_TIME:
                mssg = f"Timeout waiting for 'go' signal at step {step}."
                logger.error(f"[SYNC] {mssg}")
                raise RuntimeError(mssg)
            
            time.sleep(sleep)
        
        logger.debug(f"[SYNC][step {step:<{step_width}d}] barrier wait {time.time() - wait_start:.4f}s")

        top_neighbor, bot_neighbor = pull_neighbor_edges(r, job_idx, total_jobs, step, logger=logger) 

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
            logger.info(f"[PUB][step {step:<{step_width}d}] published chunk to channel [{redis_channel}]")
        
        logger.debug(f"[STEP] {step} completed (Write> Sync> Read> Compute> Pub) in {time.time() - step_start:.4f}s.")

    logger.info(f"[FIN] {total_steps} steps completed for rows {start_row}-{end_row-1}.")

    time.sleep(LINGER_SECONDS) 

if __name__ == "__main__":
    main()