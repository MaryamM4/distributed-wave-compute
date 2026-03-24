# Prerequisites
- Configure AWS CLI: ``aws configure``
- Install AWS CLI on WSL: https://dev.to/pu-lazydev/installing-aws-cli-v2-on-wsl-ubuntu-plg 
- Setup kubectl and eksctl: https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html#linux_amd64_kubectl/ 
- Install eksctl: https://docs.aws.amazon.com/eks/latest/eksctl/installation.html 
- IAM Permissions: IAM > Users > (user) > Add permissions > Attatch policies directly
    -	AmazonEKSClusterPolicy
    -	AmazonEKSWorkerNodePolicy
    -	AmazonEC2FullAccess
    -	AmazonEC2ContainerRegistryReadOnly
    -   Attach AmazonEC2ContainerRegistryReadOnly (allow nodes to pull from ECR)

- Create IAM OIDC provider (if not exists) to allow Kubernetes service accounts to assume IAM roles: 
    ``eksctl utils associate-iam-oidc-provider --region us-west-2 --cluster schrodinger-cluster --approve``

# 1. Deploy node group 
- Run: ``eksctl create cluster -f cluster.yaml``
- Verify ``cluster: kubectl get nodes``

# 2. Create Redis worker task. 
This one requires:
- A Redis server running somewhere (EC2-better or inside Kubernetes-easier)
- A server job/pod that connects to Redis
- Setting environment variables like: REDIS_HOST, REDIS_PORT, REDIS_CHANNEL

EC2 > create key pair. Copy file to local directory & ``chmod 400 keypair.pem``.


# 3. Apply Kubernets Job YAML
- Apply: ``kubectl apply -f schrodinger-job.yaml``
- Verify: ``kubectl get pods -w``

# 4. Implement PV then PVC
First required an EBS volume:
- Check if exits: ``aws ec2 describe-volumes --filters Name=availability-zone,Values=us-west-2a``
- If not: ``aws ec2 create-volume --availability-zone us-west-2a --size 5 --volume-type gp2``

Create PV YAML & apply: ``kubectl apply -f pv.yaml``
Create PVC & apply: ``kubectl apply -f pvc.yaml``

# 5. Add volume & to Kubernets Job YAML & reapply job
``kubectl delete job schrodinger-job``
``kubectl apply -f schrodinger-job.yaml``

Verify: ``kubectl describe pod <pod-name>``
    Look for: "**Mounts:** /data from results-storage"


# NOTE
Since you're using EBS-backed PV, only ONE node can mount it. So:
- Pod on Node A; works
- Pod on Node B; mount fails OR stuck Pending

``kubectl get pods`` will likely show some Running pods and Pending ones (volume conflict).