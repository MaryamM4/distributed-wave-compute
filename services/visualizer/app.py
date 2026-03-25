import matplotlib
matplotlib.use("TkAgg")

import argparse
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import threading
import queue
import time

from tools.redis_client import RedisSubscriber
from tools.assembler import FrameAssembler
from tools.plotting import SurfacePlot
from tools.recorder import Recorder
from tools.recorder import load_run

LIVE_INTERVAL=100  # 50 or 100 for less CPU load

ani = None # Prevent garbage collection

'''
Live Mode (also Exports (to video) & Records to enable replay):
python visualizer/app.py live --redis-host <EC2_IP> --channel <RUN_ID>:wave_channel --record --run-id test_run

Replay Mode:
python visualizer/app.py replay --run-id test_run --skip 5 --fps 30

Replay & Export Mode:
python visualizer/app.py replay --run-id test_run --skip 2 --fps 30  --export-video  --output wave.mp4
'''

def run_live(args):
    global ani
    q = queue.Queue()

    # Redis subscriber thread
    def redis_thread():
        sub = RedisSubscriber(args.redis_host, args.redis_port, args.channel)
        sub.connect()

        for msg in sub.listen():
            q.put(msg)

    threading.Thread(target=redis_thread, daemon=True).start()
    assembler = FrameAssembler(args.grid_size, args.total_workers)

    recorder = None
    if args.record: # Save frames to enable replays in future runs
        recorder = Recorder(run_id=args.run_id, grid_size=args.grid_size, total_workers=args.total_workers, channel=args.channel)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.view_init(elev=30, azim=135) # viewing angle
    plot = SurfacePlot(ax, args.grid_size)

    last_step = None
    last_frame_time = time.time()
    current_frame = None

    def update(_):
        nonlocal current_frame, last_frame_time, last_step

        while not q.empty(): # Drain queue
            msg = q.get()

            frame = assembler.add_chunk(step=msg["step"], worker_id=msg["worker"], start_row=msg["start_row"], chunk=msg["data"])

            if frame is not None:
                step, full = frame
                last_step = step
                current_frame = full
                last_frame_time = time.time()

                print(f"[FRAME] step={step}")

                if recorder:
                    recorder.add_frame(step, full)

        
        if current_frame is None:
            ax.set_title("Waiting for data...")
            return 
        
        # No data to start off from 
        if current_frame is None:
            ax.set_title("Waiting for data...")
            return

        plot.update(current_frame) 
        
        # Title
        if last_step is None:                   # Handle no data case
            ax.set_title(f"Last step empty...")
        elif time.time() - last_frame_time > 5: # Handle stalled stream
            ax.set_title(f"PAUSED (last step: {last_step})...")
        else:
            ax.set_title(f"Live: Step {last_step}")

    ani = FuncAnimation(fig, update, interval=LIVE_INTERVAL, cache_frame_data=False)

    try:
        plt.show() # Update plot

    finally:
        if recorder: # Regardless of plot success, save data.
            recorder.finalize()
    
    return ani

def run_replay(args):
    global ani
    metadata, steps, frames = load_run(args.run_id)

    print(f"[REPLAY] Run: {args.run_id}")
    print(f"[REPLAY] Frames: {len(frames)}")
    print(f"[REPLAY] Skip: {args.skip}")
    print(f"[REPLAY] FPS: {args.fps}")

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.view_init(elev=30, azim=135) # viewing angle
    plot = SurfacePlot(ax, metadata["grid_size"])

    # Precompute frame indices (important for export)
    indices = list(range(0, len(frames), args.skip))

    def update(i):
        frame_idx = indices[i]
        frame = frames[frame_idx]
        step = steps[frame_idx]

        plot.update(frame)
        ax.set_title(f"Replay: step={step}, frame={i}")

    interval = int(1000 / args.fps)

    if len(indices) == 0:
        print("[ERROR] No frames to replay.")
        return

    ani = FuncAnimation(fig, update, frames=len(indices), interval=interval)

    if args.export_video:
        print(f"[EXPORT] Writing video to {args.output} ...")
        ani.save(args.output, writer="ffmpeg", fps=args.fps)
        print("[EXPORT] Done.")
        return

    plt.show()
    return ani

def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="mode")

    # LIVE
    live = subparsers.add_parser("live")
    live.add_argument("--redis-host", required=True)
    live.add_argument("--redis-port", type=int, default=6379)
    live.add_argument("--channel", required=True)
    live.add_argument("--grid-size", type=int, default=200)
    live.add_argument("--total-workers", type=int, default=10)
    live.add_argument("--record", action="store_true")
    live.add_argument("--run-id", default="default_run")

    # REPLAY (stub for now)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-id", required=True)
    replay.add_argument("--skip", type=int, default=1)
    replay.add_argument("--fps", type=int, default=30)
    replay.add_argument("--export-video", action="store_true")
    replay.add_argument("--output", default="video.mp4")

    args = parser.parse_args()

    if args.mode == "live":
        ani = run_live(args)
    elif args.mode == "replay":
       ani =  run_replay(args)
    else:
        parser.print_help()
    


if __name__ == "__main__":
    main()