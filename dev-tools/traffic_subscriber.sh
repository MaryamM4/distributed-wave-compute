#!/bin/bash

SSH_KEY="$HOME/.ssh/aws/schrodinger-key-pair.pem"

EC2_USER="ec2-user"
EC2_IP="18.236.60.202"

LOCAL_PORT="6380"
REMOTE_PORT="6379" # Redis port

# Ensure ssh key usable
chmod 400 "$SSH_KEY"
ls -l "$SSH_KEY" 
echo

echo "[INFO] Cleaning up port $LOCAL_PORT..."
pkill -f "ssh -f -N.*$LOCAL_PORT:localhost:$REMOTE_PORT" 2>/dev/null

echo "[INFO] Creating SSH tunnel to Redis on EC2..."
ssh -f -N -o IdentitiesOnly=yes -i "$SSH_KEY" -L "$LOCAL_PORT:localhost:$REMOTE_PORT" "$EC2_USER@$EC2_IP"
sleep 1

echo "[INFO] Connected. Listening for Redis PUB/SUB messages..."
echo
redis-cli -p "$LOCAL_PORT" PSUBSCRIBE '*'
echo