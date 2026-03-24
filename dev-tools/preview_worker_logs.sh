#!/bin/bash

# Run with "save" flag to log into file.
# ./dev-tools/preview_worker_logs.sh --save

HEAD_COUNT=7
TAIL_COUNT=7

HEAD_START_AT=3  # First two lines are uneccassary info prints

N_WORKERS=10
NAMESPACE="schrodinger"

SAVE_MODE=false

LOG_DIR="logs"
FILE_NAME="worker_previews.log"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # Resolve directory of this script
OUTPUT_DIR="$SCRIPT_DIR/$LOG_DIR"       # Output directory and file (relative to script location)
OUTPUT_FILE="$OUTPUT_DIR/$FILE_NAME"

# Parse flags
for arg in "$@"; do
    if [[ "$arg" == "--save" ]]; then
        SAVE_MODE=true
        mkdir -p "$OUTPUT_DIR"
        echo "Saving output to $LOG_DIR/$FILE_NAME..."
        echo "=== Worker Log Previews ===" > "$OUTPUT_FILE"
        echo >> "$OUTPUT_FILE"
    fi
done

write() { # Helper to print or save
    if $SAVE_MODE; then
        echo "$1" >> "$OUTPUT_FILE"
    else
        echo "$1"
    fi
}

write "Previewing logs for $N_WORKERS workers (head=$HEAD_COUNT, tail=$TAIL_COUNT)."
write "Note: Head starts at line $HEAD_START_AT."
write ""

for ((i=0; i<$N_WORKERS; i++)); do
    pod=$(kubectl get pod -n "$NAMESPACE" \
        -l batch.kubernetes.io/job-completion-index=$i \
        -o jsonpath='{.items[*].metadata.name}' | awk '{print $1}')

    write "============================================"

    if [ -z "$pod" ]; then
        write "No pod found for worker $i."
        write ""
        continue
    fi

    write " Worker $i  |  Pod: $pod"
    logs=$(kubectl logs -n "$NAMESPACE" "$pod" 2>/dev/null)

    if [ -z "$logs" ]; then
        write ""
        write "No logs available."
        write ""
        continue
    fi

    write "---    TOP $HEAD_COUNT LINES    ---"
    write "$(echo "$logs" | tail -n +$HEAD_START_AT | head -n $HEAD_COUNT)"
    write ""
    write "---    BOTTOM $TAIL_COUNT LINES    ---"
    write "$(echo "$logs" | tail -n $TAIL_COUNT)"
    write ""
done

if [[ "$SAVE_MODE" == true ]]; then
    echo "Saved worker previews to $OUTPUT_FILE"
fi
