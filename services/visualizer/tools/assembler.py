# Reconstructs frames from worker chunks

import numpy as np
from collections import defaultdict

class FrameAssembler:
    def __init__(self, grid_size, total_workers):
        self.grid_size = grid_size
        self.total_workers = total_workers

        # step -> {worker_id: (start_row, chunk)}
        self.frames = defaultdict(dict)

        self.last_completed_step = -1

    def add_chunk(self, step, worker_id, start_row, chunk):
        """
        chunk: 2D list -> convert to numpy
        """
        chunk_np = np.array(chunk)

        self.frames[step][worker_id] = (start_row, chunk_np)

        if len(self.frames[step]) == self.total_workers:
            return self._assemble_frame(step)

        return None

    def _assemble_frame(self, step):
        full = np.zeros((self.grid_size, self.grid_size))

        for worker_id, (start_row, chunk) in self.frames[step].items():
            rows = chunk.shape[0]
            full[start_row:start_row + rows, :] = chunk

        del self.frames[step]  # Cleanup old frames to prevent memory leak

        self.last_completed_step = step
        return step, full