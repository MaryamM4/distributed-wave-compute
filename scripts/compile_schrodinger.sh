#!/bin/bash

set -e # Stop script at errors

echo "Compiling Fortran schrodinger code in via Numpy f2py..."

# Get into the right directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT/math-engine"

python -m numpy.f2py -c -m schrodinger_mod schrodinger.f90 # Compile

echo "Build complete. Python-importable module:"
ls schrodinger_mod*.so