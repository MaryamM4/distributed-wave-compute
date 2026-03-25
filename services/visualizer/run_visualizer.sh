#!/bin/bash

# Live: ./run_visualizer.sh
# Interactive Replay: ./run_visualizer.sh replay
# Replay & Export: ./run_visualizer.sh export

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT=6379
DEFAULT_GRID=200
DEFAULT_WORKERS=10

VIS_SCRIPT="app.py"
RUNS_DIR="runs"
VENV_DIR="venv"

MODE="live"
EXPORT=false

# Parse args
for arg in "$@"; do
    case $arg in
        replay)
            MODE="replay"
            ;;
        export)
            MODE="replay"
            EXPORT=true
            ;;
    esac
done

# Ensure venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "[ERROR] Virtual environment not found."
    echo "        Run: ./prereqs.sh first"
    exit 1
fi

# Activate venv
source "$VENV_DIR/bin/activate"
PYTHON_BIN="$VENV_DIR/bin/python"

# Helper selects run
select_run() {
    if [ ! -d "$RUNS_DIR" ]; then
        echo "[ERROR] No runs directory found."
        exit 1
    fi

    runs=($(ls "$RUNS_DIR"))

    if [ ${#runs[@]} -eq 0 ]; then
        echo "[ERROR] No saved runs."
        exit 1
    fi

    echo "Available runs:"
    for i in "${!runs[@]}"; do
        echo "[$i] ${runs[$i]}"
    done

    echo -n "Select run index: "
    read idx

    echo "${runs[$idx]}"
}

# ==================
# --- Live mode ---
if [ "$MODE" == "live" ]; then
    CHANNEL="*:wave_channel"

    echo "[LIVE ] Subscribing to pattern: $CHANNEL"

    $PYTHON_BIN "$VIS_SCRIPT" live \
        --redis-host "$REDIS_HOST" \
        --redis-port "$REDIS_PORT" \
        --channel "$CHANNEL" \
        --grid-size "$DEFAULT_GRID" \
        --total-workers "$DEFAULT_WORKERS" \
        --record
fi

# ==================
# --- Replay mode ---
if [ "$MODE" == "replay" ]; then
    RUN_ID=$(select_run)

    echo "[REPLAY] Selected run: $RUN_ID"

    if $EXPORT; then
        OUTPUT="runs/$RUN_ID/video.mp4"

        $PYTHON_BIN "$VIS_SCRIPT" replay \
            --run-id "$RUN_ID" \
            --skip 2 \
            --fps 30 \
            --export-video \
            --output "$OUTPUT"

        echo "[EXPORT] Saved to $OUTPUT"
    else
        $PYTHON_BIN "$VIS_SCRIPT" replay \
            --run-id "$RUN_ID" \
            --skip 2 \
            --fps 30
    fi
fi