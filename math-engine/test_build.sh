#!/bin/bash

# Verify build locally (ensure Dockerfile is valid)
# docker build --provenance=false --platform linux/amd64 -t test-build .

echo "Verifying Docker Build..."

# Attempt Build
docker build --provenance=false --platform linux/amd64 -t verify-build .

if [ $? -eq 0 ]; then
    echo "[PASS] Dockerfile is valid."
    echo "[PASS] Build successful."
else
    echo "[FAIL] Docker build failed."
    exit 1
fi