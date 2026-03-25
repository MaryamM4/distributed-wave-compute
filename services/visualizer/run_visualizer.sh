#!/bin/bash

# Interactive Replay: ./run_visualizer.sh replay
# Replay & Export:    ./run_visualizer.sh export
# Live:               ./run_visualizer.sh 
# Use --log for live logging of messages

# May need to install ts for timestamping before running this script:
# sudo apt install moreutils -y

FPS=30
FRAME_SKIP=2

# Save config
SAVE_MODE=true
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
LOG_DIR="logs/visualizer"
FULL_DIR="$PROJECT_ROOT/dev-tools/$LOG_DIR"
RUN_ID=$(date +"%Y%m%d_%H%M%S")
FILE_NAME="viz_${RUN_ID}.log"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/$FULL_DIR"
OUTPUT_FILE="$OUTPUT_DIR/$FILE_NAME"

# Redis config
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT=6379
DEFAULT_GRID=200
DEFAULT_WORKERS=10

VIS_SCRIPT="app.py"
RUNS_DIR="runs"
VENV_DIR="venv"

MODE="live"
EXPORT=false

# Colors
RED='\033[0;31m'
YELLOW='\033[0;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# Spinner
SPINNER_FRAMES=('|' '/' '—' '\\')
SPINNER_INDEX=0
REPEAT_COUNT=0
LAST_MSG=""
FRAME_MSG_COUNT=0
FRAME_LOG_INTERVAL=10

FIRST_REPEAT_TS=""
IN_REPEAT_MODE=false

# Whatever it is, try to take up 5 spaces
REPEAT_SIGNAL="  ↻  "

# Parse flags
LOG_LIVE=false
for arg in "$@"; do
    case $arg in
        replay) MODE="replay" ;;
        export) MODE="replay"; EXPORT=true ;;
        --log) LOG_LIVE=true ;;
    esac
done

# Setup log directory
if $SAVE_MODE; then
    mkdir -p "$OUTPUT_DIR"
    echo
    echo "Saving output to $LOG_DIR/$FILE_NAME..."
    echo
    echo "=== Visualizer Run ($RUN_ID) ===" > "$OUTPUT_FILE"
    echo >> "$OUTPUT_FILE"
fi

# --- Helpers ---

save_log() {
    local msg="$1"
    if $SAVE_MODE; then
        ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"
        echo "[$ts] $msg" >> "$OUTPUT_FILE"
    fi
}

colorize_msg() {
    local msg="$1"
    if [[ "$msg" == *"[INFO"* ]]; then
        echo -e "${GREEN}${msg}${NC}"
    elif [[ "$msg" == *"[ERROR"* ]] || [[ "$msg" == *"[REDIS"* ]]; then
        echo -e "${RED}${msg}${NC}"
    else
        echo "$msg"
    fi
}

write_spinner() {
    local msg="$1"
    SPINNER_INDEX=$(( (SPINNER_INDEX + 1) % 4 ))
    local frame="${SPINNER_FRAMES[$SPINNER_INDEX]}"
    ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"
    echo -ne "\r\033[K[$ts] $frame $msg"
}

print_with_spinner() {
    local msg="$1"
    local ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"

    # Only show count for ERROR
    local attempt_msg=""
    if [[ "$msg" == *"[ERROR"* ]]; then
        attempt_msg=" ($REPEAT_COUNT)"
    fi

    # If repeating → show continuation line
    if $IN_REPEAT_MODE; then
        local spinner="${SPINNER_FRAMES[$((REPEAT_COUNT % 4))]}"
        echo -ne "\r\033[K[$ts] [$REPEAT_SIGNAL]$attempt_msg $spinner"
    else
        # First occurrence → print normally
        echo -e "\r\033[K[$ts] $msg"
    fi
}

track_repeated_msg() {
    local msg="$1"

    if [[ "$msg" == "$LAST_MSG" ]]; then
        ((REPEAT_COUNT++))
        if ! $IN_REPEAT_MODE; then
            IN_REPEAT_MODE=true
            FIRST_REPEAT_TS="$(date '+%Y-%m-%d %H:%M:%S.%3N')"
        fi
    else
        REPEAT_COUNT=0
        IN_REPEAT_MODE=false
        FIRST_REPEAT_TS=""
    fi

    LAST_MSG="$msg"
}

should_log_frame() {
    local msg="$1"
    if [[ "$msg" == *"[FRAME]"* ]]; then
        ((FRAME_MSG_COUNT++))
        if (( FRAME_MSG_COUNT < FRAME_LOG_INTERVAL )); then
            return 1
        fi
        FRAME_MSG_COUNT=0
    fi
    return 0
}

display_msg() {
    local msg="$1"
    track_repeated_msg "$msg"
    local colored=$(colorize_msg "$msg")
    print_with_spinner "$colored" "$REPEAT_COUNT"
    save_log "$msg"
}

wait_for_redis() {
    local msg="[REDIS] Connection failed. Retrying..."

    while ! redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" PING &>/dev/null; do
        track_repeated_msg "$msg"      
        colored=$(colorize_msg "$msg")     
        print_with_spinner "$colored"    
        sleep 0.5
    done

    echo
    write "[INFO ] Redis connection established."
}

write() {
    local msg="$1"
    local colored=$(colorize_msg "$msg")
    ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"
    echo -e "[$ts] $colored"
    save_log "$msg"
}

# Replay helper
select_run() {
    if [ ! -d "$RUNS_DIR" ]; then
        write "[ERROR] No runs directory found."
        exit 1
    fi

    runs=($(ls "$RUNS_DIR"))
    if [ ${#runs[@]} -eq 0 ]; then
        write "[ERROR] No saved runs."
        exit 1
    fi

    echo "Available runs:"
    for i in "${!runs[@]}"; do
        echo "[$i] ${runs[$i]}"
    done

    echo -n "Select run index: "
    read idx

    if ! [[ "$idx" =~ ^[0-9]+$ ]] || (( idx < 0 || idx >= ${#runs[@]} )); then
        write "[ERROR] Invalid run index."
        exit 1
    fi

    echo "${runs[$idx]}"
}

# --- Live mode ---
if [ "$MODE" == "live" ]; then
    CHANNEL="*:wave_channel"
    write "[INFO ] Subscribing to pattern: $CHANNEL"

    wait_for_redis

    $VENV_DIR/bin/python "$VIS_SCRIPT" live \
        --redis-host "$REDIS_HOST" --redis-port "$REDIS_PORT" --channel "$CHANNEL" \
        --grid-size "$DEFAULT_GRID" --total-workers "$DEFAULT_WORKERS" \
        --record 2>&1 | while IFS= read -r line; do

        if ! should_log_frame "$line"; then
            continue
        fi

        # track repeated message
        track_repeated_msg "$line"
        colored=$(colorize_msg "$line")
        print_with_spinner "$colored" "$REPEAT_COUNT"
        save_log "$line"
    done
fi

# --- Replay mode ---
if [ "$MODE" == "replay" ]; then
    RUN_ID=$(select_run)
    write "[INFO ] Selected run: $RUN_ID"

    if $EXPORT; then
        OUTPUT="runs/$RUN_ID/video.mp4"
        $VENV_DIR/bin/python "$VIS_SCRIPT" replay --run-id "$RUN_ID" --skip $FRAME_SKIP --fps $FPS \
            --export-video --output "$OUTPUT"
        write "[INFO ] Saved to $OUTPUT"
    else
        $VENV_DIR/bin/python "$VIS_SCRIPT" replay --run-id "$RUN_ID" --skip $FRAME_SKIP --fps $FPS
    fi
fi