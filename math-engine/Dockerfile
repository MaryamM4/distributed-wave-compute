
# STAGE 1: BUILD FORTRAN MODULE
FROM python:3.12 AS builder

# Install build tools
RUN apt-get update && apt-get install -y \
        meson ninja-build gfortran \ 
        python3-numpy python3-dev \
        build-essential python3-dev wget \
        && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements & install Python dependencies 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY schrodinger.f90 .
COPY parallel_worker.py .

# Compile Fortran module via standalone f2py script (avoid python wrapper)
RUN f2py -c -m schrodinger_mod schrodinger.f90 --fcompiler=gnu95

#============================
# STAGE 2: RUNTIME CONTAINER 
FROM python:3.12-slim

WORKDIR /app

# Install Python runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy compiled scripts from builder
COPY --from=builder /build/schrodinger_mod*.so /app/
COPY --from=builder /build/parallel_worker.py /app/

# Default environment variables
ENV GRID_SIZE=200
ENV TOTAL_WORKERS=10

# Run the command
CMD ["python", "parallel_worker.py"]

# Verify build:
# docker build --provenance=false --platform linux/amd64 -t verify-build .