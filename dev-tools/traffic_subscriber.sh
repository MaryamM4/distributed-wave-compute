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

# ControlMaster socket
SOCKET="/tmp/redis_tunnel_${RUN_ID}.sock"

# Colors, don't change
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # no color

# --===============================--

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

# Helper for stream-safe write
write() {
    ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"

    msg="$1"
    colored_msg="$msg"

    # Color for terminal output
    if [[ "$msg" == *"[INFO"* ]]; then
        colored_msg="${GREEN}${msg}${NC}"
    elif [[ "$msg" == *"[ERROR"* ]]; then
        colored_msg="${RED}${msg}${NC}"
    fi

    if $SAVE_MODE; then
        echo "[$ts] $msg" >> "$OUTPUT_FILE"
        echo -e "[$ts] $colored_msg"
    else
        echo -e "[$ts] $colored_msg"
    fi
}

# Helper for inline overwrite (console only, no file logging)
write_inline() {
    ts="$(date '+%Y-%m-%d %H:%M:%S.%3N')"

    msg="$1"
    colored_msg="$msg"

    if [[ "$msg" == *"[INFO"* ]]; then
        colored_msg="${GREEN}${msg}${NC}"
    elif [[ "$msg" == *"[ERROR"* ]]; then
        colored_msg="${RED}${msg}${NC}"
    fi

    echo -ne "\r[$ts] $colored_msg"
}

# Helper handles cleanup
cleanup() {
    echo
    write "[INFO ] Shutting down..."

    if [[ -S "$SOCKET" ]]; then
        write "[INFO ] Closing SSH tunnel..."
        ssh -S "$SOCKET" -O exit "$EC2_USER@$EC2_IP" 2>/dev/null
        rm -f "$SOCKET"
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
pkill -f "ssh.*$LOCAL_PORT:localhost:$REMOTE_PORT" 2>/dev/null

write "[INFO ] Creating SSH tunnel to Redis on EC2..."

ssh -f -N -o IdentitiesOnly=yes -o ControlMaster=yes -o ControlPath="$SOCKET" -o ControlPersist=yes \
    -i "$SSH_KEY" -L "$LOCAL_PORT:localhost:$REMOTE_PORT" "$EC2_USER@$EC2_IP"

sleep 1

# Verify tunnel
if ssh -S "$SOCKET" -O check "$EC2_USER@$EC2_IP" 2>/dev/null; then
    write "[INFO ] Tunnel established."
else
    write "[ERROR] Failed to establish SSH tunnel."
    exit 1
fi

write "[INFO ] Connected. Listening for Redis PUB/SUB messages..."
write ""

# Auto-reconnect
retry_count=0

while true; do
    write "[INFO ] Starting Redis subscription..."
    retry_count=0    

    if $SAVE_MODE; then
        redis-cli -p "$LOCAL_PORT" PSUBSCRIBE '*' | ts '[%Y-%m-%d %H:%M:%S.%3N]' | tee -a "$OUTPUT_FILE"
    else
        redis-cli -p "$LOCAL_PORT" PSUBSCRIBE '*' | ts '[%Y-%m-%d %H:%M:%S.%3N]'
    fi

    write "[ERROR] Redis stream disconnected. Retrying in 2s..."
    sleep 2

    # Check tunnel health, restart if needed
    if ! ssh -S "$SOCKET" -O check "$EC2_USER@$EC2_IP" 2>/dev/null; then
        while true; do
            ((retry_count++))

            write_inline "[ERROR] SSH tunnel is down. Reconnecting... (attempt $retry_count)"

            ssh -f -N -o IdentitiesOnly=yes -o ControlMaster=yes -o ControlPath="$SOCKET" -o ControlPersist=yes \
                -i "$SSH_KEY" -L "$LOCAL_PORT:localhost:$REMOTE_PORT" "$EC2_USER@$EC2_IP"

            sleep 1

            if ssh -S "$SOCKET" -O check "$EC2_USER@$EC2_IP" 2>/dev/null; then
                echo
                write "[INFO ] Tunnel re-established after $retry_count attempt(s)."
                retry_count=0
                break
            fi

            sleep 2
        done
    fi
done

write ""