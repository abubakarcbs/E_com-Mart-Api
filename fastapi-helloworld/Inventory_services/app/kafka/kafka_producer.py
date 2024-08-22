# inventory_services/kafka_producer.py

from confluent_kafka import Producer

class KafkaProducer:
    def __init__(self, broker: str):
        self.producer = Producer({'bootstrap.servers': broker})

    def produce_message(self, topic: str, key: str, value: str):
        def delivery_report(err, msg):
            if err is not None:
                print(f"Message delivery failed: {err}")
            else:
                print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

        self.producer.produce(topic, key=key, value=value, callback=delivery_report)
        self.producer.flush()

# Example usage
# producer = KafkaProducer('localhost:9092')
# producer.produce_message('inventory-topic', key='item1', value='Item updated')
