'''
sudo apt install python3.12-venv
python3 -m venv venv  
source venv/bin/activate
pip install -r requirements.txt
'''

'''
sudo apt install dos2unix
dos2unix run_visualizer.sh
chmod +x run_visualizer.sh
./run_visualizer.sh
'''



Test: ``redis-cli -h localhost -p 6379 KEYS "*"``
- If no keys seen, visualizer has nothing to attatch to. 
- ''Could not connect to Redis at localhost:6379: Connection refused'': 
    ``ssh -i ~/.ssh/aws/schrodinger-key-pair.pem -L 6379:localhost:6379 ec2-user@18.236.60.202``  # Forward port 6379 to laptop. Won't work
-   ``ssh -i ~/.ssh/aws/schrodinger-key-pair.pem -L 6379:localhost:6379 ec2-user@18.236.60.202`` #  Forward fport 6379 from EC2 instance
