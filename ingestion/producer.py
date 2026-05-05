import json
import logging
from typing import Any, Dict
from confluent_kafka import Producer

from .config import settings

logger = logging.getLogger(__name__)

class WeatherKafkaProducer:
    """
    Singleton wrapper for the Confluent Kafka Producer.
    Handles serialization and delivering messages reliably.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WeatherKafkaProducer, cls).__new__(cls)
            cls._instance._init_producer()
        return cls._instance

    def _init_producer(self):
        conf = {
            'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
            'client.id': settings.KAFKA_CLIENT_ID,
            'compression.type': settings.KAFKA_COMPRESSION_TYPE,
            'acks': 'all',  # Strongest guarantee
            'retries': 5,
            'delivery.timeout.ms': 120000,
            'linger.ms': 5  # Add a tiny delay to allow batching
        }
        self.producer = Producer(conf)
        logger.info(f"Kafka Producer initialized: {settings.KAFKA_BOOTSTRAP_SERVERS}")

    def delivery_report(self, err, msg):
        """ Called once for each message produced to indicate delivery result """
        if err is not None:
            logger.error(f"Message delivery failed to topic {msg.topic()}: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

    def publish_message(self, topic: str, payload: Dict[str, Any], key: str = None):
        """
        Produce a JSON message to a Kafka topic.
        """
        try:
            # Trigger any available delivery report callbacks
            self.producer.poll(0)
            
            serialized_payload = json.dumps(payload).encode('utf-8')
            encoded_key = key.encode('utf-8') if key else None
            
            self.producer.produce(
                topic=topic,
                key=encoded_key,
                value=serialized_payload,
                callback=self.delivery_report
            )
            # Flush periodically or rely on lingering buffer; we will just let it buffer for high throughput
        except BufferError:
            logger.warning(f"Local producer queue is full ({len(self.producer)} messages). Flushing...")
            self.producer.flush()
            self.publish_message(topic, payload, key) # Retry after flush
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")

    def flush(self, timeout=10.0):
        """Wait for all messages in the producer queue to be delivered."""
        logger.info("Flushing Kafka producer...")
        self.producer.flush(timeout)
