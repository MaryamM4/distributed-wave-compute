#!/bin/bash

set -e

VENV_DIR="venv"
REQUIREMENTS="requirements.txt"

echo "[SETUP] Starting environment setup..."

# Install system dependencies (Debian/Ubuntu)
if command -v apt >/dev/null 2>&1; then
    echo "[SETUP] Installing system packages..."

    sudo apt update
    sudo apt install -y python3-venv dos2unix python3.12-tk
fi

# Fix line endings (safe even if already correct)
if [ -f "run_visualizer.sh" ]; then
    echo "[SETUP] Normalizing script line endings..."
    dos2unix run_visualizer.sh 2>/dev/null || true
fi

# Create virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo "[SETUP] Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "[SETUP] Virtual environment already exists"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install Python dependencies
if [ -f "$REQUIREMENTS" ]; then
    echo "[SETUP] Installing Python dependencies..."
    python -m pip install --upgrade pip
    python -m pip install -r "$REQUIREMENTS"
else
    echo "[WARN] No requirements.txt found"
fi

echo "[SETUP] Done"
echo ""
echo "Next step:"
echo "chmod +x run_visualizer.sh"
echo "./run_visualizer.sh"
