#!/bin/bash

N_WORKERS=10
NAMESPACE="schrodinger"

PATTERN="[PUB" 

SAVE_MODE=false

LOG_DIR="logs"
FILE_NAME="worker_publish_events.log"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" # Resolve directory of this script
OUTPUT_DIR="$SCRIPT_DIR/$LOG_DIR"   # Output directory and file (relative to script location)
OUTPUT_FILE="$OUTPUT_DIR/$FILE_NAME"

# Parse flags
for arg in "$@"; do
    if [[ "$arg" == "--save" ]]; then
        SAVE_MODE=true
        mkdir -p "$OUTPUT_DIR"
        echo "Saving publish events to $LOG_DIR/$FILE_NAME..."
        echo "=== Worker Publish Events ===" > "$OUTPUT_FILE"
        echo >> "$OUTPUT_FILE"
    fi
done

write() {
    if $SAVE_MODE; then
        echo "$1" >> "$OUTPUT_FILE"
    else
        echo "$1"
    fi
}

write "Showing publish events for $N_WORKERS workers"
write "Matching pattern:  $PATTERN"
write ""

for ((i=0; i<$N_WORKERS; i++)); do
    pod=$(kubectl get pod -n "$NAMESPACE" \
        -l batch.kubernetes.io/job-completion-index=$i \
        -o jsonpath='{.items[*].metadata.name}' | awk '{print $1}')

    write "============================================"
    write " Worker $i  |  Pod: ${pod:-NONE}"

    if [ -z "$pod" ]; then
        write "No pod found."
        write ""
        continue
    fi

    matches=$(kubectl logs -n "$NAMESPACE" "$pod" 2>/dev/null | grep -F "$PATTERN")

    if [ -z "$matches" ]; then
        write "No publish events found."
    else
        write "$matches"
    fi

    write ""
done

if [[ "$SAVE_MODE" == true ]]; then
    echo "Saved to: $OUTPUT_FILE"
fi
