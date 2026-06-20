"""
Kafka Producer Example
Sends test messages to Kafka topics
"""
from kafka import KafkaProducer
from kafka.errors import KafkaError
import json
import time
from datetime import datetime
import random

def create_producer():
    """Create Kafka producer with retry logic"""
    brokers = [
        'kafka-broker-1:9092',
        'kafka-broker-2:9093',
        'kafka-broker-3:9094'
    ]
    
    producer = KafkaProducer(
        bootstrap_servers=brokers,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        acks='all',  # Wait for all replicas to acknowledge
        retries=3,
        max_in_flight_requests_per_connection=1
    )
    
    return producer

def generate_sample_data():
    """Generate sample data for testing"""
    return {
        'id': f"msg_{int(time.time())}_{random.randint(1000, 9999)}",
        'timestamp': datetime.now().isoformat(),
        'value': f"sample_value_{random.randint(1, 100)}",
        'metric': random.randint(1, 1000)
    }

def main():
    print("Starting Kafka Producer...")
    
    producer = create_producer()
    topic = 'lakehouse_input'
    
    print(f"Sending messages to topic: {topic}")
    print("Press Ctrl+C to stop")
    
    message_count = 0
    
    try:
        while True:
            # Generate and send message
            message = generate_sample_data()
            
            future = producer.send(topic, value=message)
            
            try:
                # Wait for send to complete
                record_metadata = future.get(timeout=10)
                message_count += 1
                
                if message_count % 10 == 0:
                    print(f"Sent {message_count} messages. Latest: {message['id']}")
                    print(f"  Topic: {record_metadata.topic}")
                    print(f"  Partition: {record_metadata.partition}")
                    print(f"  Offset: {record_metadata.offset}")
                
            except KafkaError as e:
                print(f"Error sending message: {e}")
            
            # Wait before sending next message
            time.sleep(1)
            
    except KeyboardInterrupt:
        print(f"\n\nStopping producer. Total messages sent: {message_count}")
    
    finally:
        producer.flush()
        producer.close()
        print("Producer closed.")

if __name__ == "__main__":
    main()
