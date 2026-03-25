#!/bin/bash

# May need to install ts for timestamping before running this script:
# sudo apt install moreutils -y

# Save config
SAVE_MODE=true
LOG_DIR="logs"
RUN_ID=$(date +"%Y%m%d_%H%M%S")
FILE_NAME="redis_stream_${RUN_ID}.log"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/$LOG_DIR"
OUTPUT_FILE="$OUTPUT_DIR/$FILE_NAME"

# Connection config
SSH_KEY="$HOME/.ssh/aws/schrodinger-key-pair.pem"

EC2_USER="ec2-user"
EC2_IP="18.236.60.202" 

LOCAL_PORT="6380"
REMOTE_PORT="6379" # Redis port

# Parse flags
for arg in "$@"; do
    if [[ "$arg" == "--no-save" ]]; then
        SAVE_MODE=false
    fi
done

# Setup the output (console only, or log too)
if $SAVE_MODE; then
    mkdir -p "$OUTPUT_DIR"
    echo "Saving output to $LOG_DIR/$FILE_NAME..."
    echo "=== Redis Stream ($RUN_ID) ===" > "$OUTPUT_FILE"
    echo >> "$OUTPUT_FILE"
fi

# Colors (terminal only)
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # no color

# Helper for stream-safe write
write() {
    ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"

    msg="$1"
    colored_msg="$msg"

    # Color only for terminal output
    if [[ "$msg" == *"[INFO"* ]]; then
        colored_msg="${GREEN}${msg}${NC}"
    elif [[ "$msg" == *"[ERROR"* ]]; then
        colored_msg="${RED}${msg}${NC}"
    fi

    if $SAVE_MODE; then
        # File gets NO color
        echo "[$ts] $msg" >> "$OUTPUT_FILE"
        # Console gets color
        echo -e "[$ts] $colored_msg"
    else
        echo -e "[$ts] $colored_msg"
    fi
}

# Track ssh tunnel pid
SSH_PID=""

# Helper handles cleanup
cleanup() {
    echo
    write "[INFO ] Shutting down..."

    if [[ -n "$SSH_PID" ]]; then
        write "[INFO ] Closing SSH tunnel (pid=$SSH_PID)..."
        kill "$SSH_PID" 2>/dev/null
    fi

    exit 0
}
trap cleanup INT TERM

# --===============================--

# Ensure ssh key usable
chmod 400 "$SSH_KEY"
ls -l "$SSH_KEY" 
write ""

write "[INFO ] Cleaning up port $LOCAL_PORT..."
pkill -f "ssh -f -N.*$LOCAL_PORT:localhost:$REMOTE_PORT" 2>/dev/null

write "[INFO ] Creating SSH tunnel to Redis on EC2..."
ssh -f -N -o IdentitiesOnly=yes -i "$SSH_KEY" -L "$LOCAL_PORT:localhost:$REMOTE_PORT" "$EC2_USER@$EC2_IP"

# Capture SSH PID
SSH_PID=$(pgrep -f "ssh -f -N.*$LOCAL_PORT:localhost:$REMOTE_PORT" | head -n 1)

sleep 1

write "[INFO ] Connected. Listening for Redis PUB/SUB messages..."
write ""

# Stream Redis output
if $SAVE_MODE; then # Stream output live to both console and file
    redis-cli -p "$LOCAL_PORT" PSUBSCRIBE '*' \
        | ts '[%Y-%m-%d %H:%M:%S.%3N]' \
        | tee -a "$OUTPUT_FILE"
else                # Steam output live to just the consile
    redis-cli -p "$LOCAL_PORT" PSUBSCRIBE '*' \
        | ts '[%Y-%m-%d %H:%M:%S.%3N]'
fi

write ""