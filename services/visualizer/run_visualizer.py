#!/bin/bash

# Live: ./run_visualizer.sh
# Interactive Replay: ./run_visualizer.sh replay
# Replay & Export: ./run_visualizer.sh export

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT=6379
DEFAULT_GRID=200
DEFAULT_WORKERS=10

VIS_SCRIPT="visualizer/app.py"
RUNS_DIR="runs"

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

# Helper interactively picks run 
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

# Helper auto-detects RUN_ID from Redis
# (RUN_ID isn't sensitive info, just a unique "version" tag)
detect_run_id() {
    echo "[INFO] Detecting active RUN_ID from Redis..."

    keys=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" KEYS "*:worker:*:top:*" 2>/dev/null)

    if [ -z "$keys" ]; then
        echo "[ERROR] Could not detect RUN_ID (no active workers?)"
        exit 1
    fi

    # Extract RUN_ID from first key
    # Format: RUN_ID:worker:X:top:Y
    run_id=$(echo "$keys" | head -n 1 | cut -d':' -f1)

    echo "$run_id"
}

# ==================
# --- Live mode ---
if [ "$MODE" == "live" ]; then
    RUN_ID=$(detect_run_id)

    CHANNEL="${RUN_ID}:wave_channel"

    echo "[LIVE] RUN_ID: $RUN_ID"
    echo "[LIVE] Channel: $CHANNEL"

    python "$VIS_SCRIPT" live \
        --redis-host "$REDIS_HOST" \
        --redis-port "$REDIS_PORT" \
        --channel "$CHANNEL" \
        --grid-size "$DEFAULT_GRID" \
        --total-workers "$DEFAULT_WORKERS" \
        --record \
        --run-id "$RUN_ID"

# ==================
# --- Replay mode ---
elif [ "$MODE" == "replay" ]; then
    RUN_ID=$(select_run)

    echo "[REPLAY] Selected run: $RUN_ID"

    if $EXPORT; then
        OUTPUT="runs/$RUN_ID/video.mp4"

        python "$VIS_SCRIPT" replay \
            --run-id "$RUN_ID" \
            --skip 2 \
            --fps 30 \
            --export-video \
            --output "$OUTPUT"

        echo "[EXPORT] Saved to $OUTPUT"

    else
        python "$VIS_SCRIPT" replay \
            --run-id "$RUN_ID" \
            --skip 2 \
            --fps 30
    fi
fi