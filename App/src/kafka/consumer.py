"""
Kafka Consumer Example
Reads messages from Kafka topics
"""
from kafka import KafkaConsumer
from kafka.errors import KafkaError
import json
import sys

def create_consumer(topic, group_id='lakehouse_consumer_group'):
    """Create Kafka consumer"""
    brokers = [
        'kafka-broker-1:9092',
        'kafka-broker-2:9093',
        'kafka-broker-3:9094'
    ]
    
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=brokers,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id=group_id,
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    return consumer

def main():
    topic = 'lakehouse_input'
    
    print(f"Starting Kafka Consumer for topic: {topic}")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    consumer = create_consumer(topic)
    
    message_count = 0
    
    try:
        for message in consumer:
            message_count += 1
            
            print(f"\n[Message #{message_count}]")
            print(f"  Topic: {message.topic}")
            print(f"  Partition: {message.partition}")
            print(f"  Offset: {message.offset}")
            print(f"  Timestamp: {message.timestamp}")
            print(f"  Value: {json.dumps(message.value, indent=2)}")
            print("-" * 50)
            
    except KeyboardInterrupt:
        print(f"\n\nStopping consumer. Total messages consumed: {message_count}")
    
    except KafkaError as e:
        print(f"Kafka error: {e}")
        sys.exit(1)
    
    finally:
        consumer.close()
        print("Consumer closed.")

if __name__ == "__main__":
    main()
