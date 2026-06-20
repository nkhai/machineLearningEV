"""
Shared Kafka client utilities.

Usage:
    from services.kafka import create_producer, create_consumer, create_topic_if_not_exists
"""

import time
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable, NodeNotReadyError

from core.constants import KAFKA_BROKERS
from core.state import add_log


def create_producer(max_retries: int = 10, base_delay: float = 2.0) -> KafkaProducer:
    """Create a Kafka producer with retry logic."""
    for attempt in range(1, max_retries + 1):
        try:
            add_log("INFO", "kafka", f"[Producer] Connecting to Kafka (attempt {attempt}/{max_retries})")
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKERS,
                value_serializer=lambda v: __import__("json").dumps(v).encode("utf-8"),
                retries=5,
                request_timeout_ms=10000,
                linger_ms=50,
            )
            add_log("INFO", "kafka", "[Producer] Connected to Kafka broker")
            return producer
        except NoBrokersAvailable:
            delay = base_delay * attempt
            add_log("WARN", "kafka", f"Kafka broker not ready, retry {attempt}/{max_retries} in {delay}s")
            time.sleep(delay)
    add_log("ERROR", "kafka", "Cannot connect to Kafka after retries")
    return None


def create_consumer(topic: str, group_id: str) -> KafkaConsumer:
    """Create a Kafka consumer for the given topic."""
    import json
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=KAFKA_BROKERS,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            key_deserializer=lambda x: x.decode("utf-8") if x else None,
        )
        add_log("INFO", "consumer", f"Connected to Kafka topic: {topic}")
        return consumer
    except NoBrokersAvailable:
        add_log("ERROR", "consumer", "Cannot connect to Kafka broker")
        return None


def create_topic_if_not_exists(topic_name: str):
    """Create a Kafka topic if it doesn't already exist."""
    try:
        admin = KafkaAdminClient(bootstrap_servers=KAFKA_BROKERS)
        admin.create_topics([NewTopic(topic_name, num_partitions=3, replication_factor=1)])
        add_log("INFO", "kafka", f"Topic '{topic_name}' created")
        admin.close()
    except TopicAlreadyExistsError:
        add_log("INFO", "kafka", f"Topic '{topic_name}' already exists")
    except NodeNotReadyError:
        add_log("WARN", "kafka", "Node not ready, topic may not exist yet")
    except Exception as e:
        add_log("ERROR", "kafka", f"Failed to create topic: {e}")
