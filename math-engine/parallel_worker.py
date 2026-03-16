import os
import json
import numpy as np
#import redis
import schrodinger_mod


H_BAR = 1.054e-34
MASS = 9.11e-31

def main():
    # Read environment variables
    job_index = int(os.getenv("JOB_COMPLETION_INDEX", "0")) # Used as time step
    grid_size = int(os.getenv("GRID_SIZE", "200"))
    total_workers = int(os.getenv("TOTAL_WORKERS", "10"))

    '''
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    '''

    print(f"Worker {job_index} starting (at time step {job_index})...")

    # Call Fortran computation
    matrix = np.zeros((grid_size, grid_size), dtype=np.float64, order="F")
    schrodinger_mod.schrodinger_mod.compute_wave_matrix(matrix=matrix, size_n=grid_size, num_steps=job_index, h_bar=H_BAR, mass=MASS) # yes "schrodinger_mod.schrodinger_mod.compute_wave_matrix" works

    # Connect to Redis, prepare message, and publish result
    ''' 
    r = redis.Redis(host=redis_host, port=redis_port)
    message = {"worker": job_index, "timestep": job_index, "matrix": matrix_chunk.tolist()}
    r.publish("wave_channel", json.dumps(message))
    '''

    print(f"Worker {job_index} published results for timestep {job_index}.")

    # Check (delete me)
    print(matrix[100,100])


if __name__ == "__main__":
    main()