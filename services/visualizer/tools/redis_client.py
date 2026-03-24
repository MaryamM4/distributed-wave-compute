# Handles pub/sub

import redis
import json
import time

class RedisSubscriber:
    def __init__(self, host, port, channel, retry_delay=2):
        self.host = host
        self.port = port
        self.channel = channel
        self.retry_delay = retry_delay

        self.client = None
        self.pubsub = None

    def connect(self):
        while True:
            try:
                self.client = redis.Redis(host=self.host, port=self.port)
                self.pubsub = self.client.pubsub()
                self.pubsub.subscribe(self.channel)
                print(f"[REDIS] Subscribed to {self.channel}")
                return
            except Exception as e:
                print(f"[REDIS] Connection failed: {e}, retrying...")
                time.sleep(self.retry_delay)

    def listen(self):
        while True:
            try:
                for message in self.pubsub.listen():
                    if message["type"] != "message":
                        continue

                    data = json.loads(message["data"])
                    yield data

            except Exception as e:
                print(f"[REDIS] Error: {e}, reconnecting...")
                time.sleep(self.retry_delay)
                self.connect()