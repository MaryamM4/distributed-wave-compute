# For saving & loading frames 

import os
import json
import numpy as np
from datetime import datetime

def get_run_dir(run_id):
    return os.path.join("runs", str(run_id))

def create_run(run_id, metadata):
    run_dir = get_run_dir(run_id)
    os.makedirs(run_dir, exist_ok=True)

    metadata["created_at"] = datetime.utcnow().isoformat()

    with open(os.path.join(run_dir, "manifest.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    return run_dir

def save_frames(run_dir, frames):
    """
    frames: list of (step, np.array)
    """
    steps = []
    data = []

    for step, frame in frames:
        steps.append(step)
        data.append(frame)

    np.savez_compressed(os.path.join(run_dir, "frames.npz"), steps=np.array(steps), frames=np.array(data))

def load_run(run_id):
    run_dir = get_run_dir(run_id)

    with open(os.path.join(run_dir, "manifest.json")) as f:
        metadata = json.load(f)

    data = np.load(os.path.join(run_dir, "frames.npz"))

    steps = data["steps"]
    frames = data["frames"]

    return metadata, steps, frames

class Recorder:
    def __init__(self, run_id, grid_size, total_workers, channel):
        self.run_id = run_id
        self.frames = []
        self.run_dir = create_run(run_id, {"grid_size": grid_size, "total_workers": total_workers,"channel": channel})

        print(f"[REC  ] Recording run to: {self.run_dir}")

    def add_frame(self, step, frame):
        self.frames.append((step, frame.copy()))

    def finalize(self):
        print(f"[REC  ] Saving {len(self.frames)} frames...")
        save_frames(self.run_dir, self.frames)
        print("[REC  ] Done.")