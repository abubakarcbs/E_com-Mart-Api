# payment_service/app/kafka_producer.py

from confluent_kafka import Producer
from starlette.config import Config
from starlette.datastructures import Secret

# Load configuration from .env file or environment variables
config = Config(".env")

BOOTSTRAP_SERVER = config("BOOTSTRAP_SERVER", cast=str)

class KafkaPaymentProducer:
    def __init__(self):
        # Initialize the Kafka producer with the bootstrap server from the config
        self.producer = Producer({'bootstrap.servers': BOOTSTRAP_SERVER})

    def produce_message(self, topic: str, key: str, value: str):
        def delivery_report(err, msg):
            if err is not None:
                print(f"Message delivery failed: {err}")
            else:
                print(f"Message delivered to {msg.topic()} [{msg.partition()}] - key: {key}, value: {value}")

        # Produce a message to the specified topic
        self.producer.produce(topic, key=key, value=value, callback=delivery_report)
        # Wait for any outstanding messages to be delivered
        self.producer.flush()
