# inventory_services/kafka_consumer.py

from confluent_kafka import Consumer, KafkaException, KafkaError

class KafkaConsumer:
    def __init__(self, broker: str, group_id: str, topics: list):
        self.consumer = Consumer({
            'bootstrap.servers': broker,
            'group.id': group_id,
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(topics)

    def consume_messages(self):
        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())
                print(f"Received message: {msg.value().decode('utf-8')} from topic: {msg.topic()}")

        except KeyboardInterrupt:
            pass
        finally:
            self.consumer.close()

# Example usage
# consumer = KafkaConsumer('localhost:9092', 'inventory-group', ['inventory-topic'])
# consumer.consume_messages()
