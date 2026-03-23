#!/bin/bash

local_dir="./logs"
REMOTE_DIR="/tmp" 

N_WORKERS=10 
NAMESPACE="schrodinger"

mkdir -p "$local_dir"

for ((i=0; i<$N_WORKERS; i++)); do
    # Find the pod for this worker index
    pod=$(kubectl get pod -n $NAMESPACE \
        -l batch.kubernetes.io/job-completion-index=$i \
        -o jsonpath='{.items[*].metadata.name}' | awk '{print $1}')

    if [ -z "$pod" ]; then
        echo "No pod found for worker $i"
        continue
    fi

    echo "Worker $i pod: $pod"

    # File logs (logger) and stdout logs (Kubernetes view)
    kubectl cp "$NAMESPACE/$pod:$REMOTE_DIR/worker_${i}.log" "$local_dir/worker_${i}.log" 2>/dev/null
    kubectl logs -n $NAMESPACE "$pod" > "$local_dir/worker_${i}_stdout.log"

    if [ $? -eq 0 ]; then
        echo "Copied worker_${i}.log"
    else
        echo "No $REMOTE_DIR/worker_${i}.log found in pod"
    fi

    echo
done
