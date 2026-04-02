# Distributed Wave Compute
A distributed wave‑simulation system running on Kubernetes, using Redis for synchronization and a Fortran‑accelerated compute kernel. 
Each worker pod computes a partition of a 2D Schrodinger wave equation, exchanges ghost‑cell boundaries through Redis, and periodically publishes frames for visualization.

## Steps
1. The grid is partitioned across N workers (Kubernetes Job with `completionMode: Indexed`).
2. Worker 0 computes the initial wave state using the Fortran module and stores it in Redis.
3. Each worker:
   - Loads its assigned grid slice  
   - Exchanges boundary rows with neighbors via Redis  
   - Computes the next timestep using a Laplacian operator  
   - Publishes periodic frames for visualization  
4. A visualizer service (WIP) reconstructs full frames from worker outputs.

## Project Status
- Compute pipeline: **Complete**  
- Redis synchronization: **Done**  
- Visualization service: **Incomplete**  
- Telemetry: **Skipped**  

# Overview
- **Kubernetes (AWS EKS)** orchestrates multiple worker pods.
- **Redis** acts as a synchronization and messaging layer for:
  - ghost‑cell boundary exchange  
  - barrier synchronization  
  - periodic frame publishing  
- **Fortran (via f2py)** accelerates the core numerical wave‑equation computation.
- **Python workers** handle partitioning, communication, and iterative simulation steps.
- **AWS ECR** and **GitLab CI/CD** automate container builds and deployments.
- **EFS persistent storage** supports shared output across pods.

## Main parts
- `parallel_worker.py`: Main distributed compute worker  
- `schrodinger.f90`: (Provided) Fortran wave‑equation kernel  
- `infra/kubernetes/`: EKS cluster, Jobs, StorageClass, PVC  
- `infra/redis/`:  EC2 Redis CloudFormation template  
- `dev-tools/`: log collectors, Redis stream subscribers, debugging tools  
- `services/visualizer/`: Frame reconstruction and plotting (in progress)

## Deployment Pipeline
- GitLab CI builds Docker images  
- Images are pushed to **AWS ECR**  
- CI deploys a Kubernetes Job to **AWS EKS**  
- Workers run in parallel and write logs to `/tmp` (retrieved via helper scripts)

