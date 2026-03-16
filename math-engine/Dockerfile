
# STAGE 1: BUILD FORTRAN MODULE
# Use slim python image
FROM python:3.11-slim AS builder

# Install build tools
RUN apt-get update && apt-get install -y \
        gfortran build-essential python3-venv wget \
        && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /build

# Copy requirements & install Python dependencies 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY schrodinger.f90 .
COPY parallel_worker.py .

# Compile Fortran module via f2py
RUN python -m numpy.f2py -c -m schrodinger_mod schrodinger.f90 --fcompiler=gnu95

# STAGE 2: RUNTIME CONTAINER (small)
FROM python:3.11-slim
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