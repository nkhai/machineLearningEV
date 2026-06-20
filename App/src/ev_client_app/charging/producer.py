import threading
import json
import time
import traceback
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable, NodeNotReadyError

from llm_generate import generate_ev_data
from state import add_log

# ===========================
# CONFIG
# ===========================
KAFKA_BROKERS = ["hc1-c-0003u.hc.apac.bosch.com:9092"]
TELEMETRY_TOPIC = "ev.battery.telemetry_v3"
# STATUS_TOPIC = "ev.vehicle.status"
RECORD_INTERVAL_SECONDS = 3

KAFKA_SCHEMA_FIELDS = [
    "id",
    "id_segment",
    "volt_V",
    "current_A",
    "soc_pct",
    "max_single_volt_V",
    "min_single_volt_V",
    "max_temp_C",
    "min_temp_C",
    "timestamp_s",
    "avg_speed_kmh",
    "hvac_active",
    "payload_kg",
    "regenerative_braking_Ah",
    "motor_rpm",
    "gear_position",
    "accelerator_pedal_pct",
    "brake_pedal_pct",
    "charger_connected",
    "label",
    "car_id",
    "car_model",
    "mileage_km",
    "actual_max_capacity_Ah",
    "nominal_capacity_Ah"
]

# ===========================
# KAFKA HELPERS
# ===========================
def create_producer(max_retries: int = 10, base_delay: float = 2.0) -> KafkaProducer:
    for attempt in range(1, max_retries + 1):
        try:
            add_log("INFO", "kafka", f"[Producer] Connecting to Kafka (attempt {attempt}/{max_retries})")
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BROKERS,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
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

def create_topic_if_not_exists(topic_name: str):
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

# ===========================
# PRODUCER LOOP
# ===========================
def producer_loop(car_id: str, car_model: str, stop_event: threading.Event, get_label_fn):

    add_log("INFO", "producer", f"EV {car_id} producer starting")

    producer = create_producer()
    if producer:
        create_topic_if_not_exists(TELEMETRY_TOPIC)

    try:
        record_gen = generate_ev_data(
            car_id=car_id,
            car_model=car_model,
            nominal_capacity=100.0,
            get_label_fn=get_label_fn
        )

        while not stop_event.is_set():
            try:
                record = next(record_gen)
            except StopIteration:
                add_log("DEBUG", "producer", f"EV {car_id} generator exhausted")
                break

            # =========================
            # TYPE SANITIZATION
            # =========================
            for k, v in record.items():
                if isinstance(v, (int, float, bool)):
                    continue
                try:
                    record[k] = float(v)
                except:
                    pass

            # =========================
            # FINAL PAYLOAD (FULL FIELDS)
            # =========================
            kafka_record = record  

            # ensure JSON-safe types
            for k, v in kafka_record.items():
                if not isinstance(v, (int, float, str, bool, list, dict)):
                    kafka_record[k] = str(v)

            # =========================
            # SEND TO KAFKA
            # =========================
            if producer:
                try:
                    producer.send(
                        TELEMETRY_TOPIC,
                        key=str(car_id).encode("utf-8"),
                        value=kafka_record
                    )

                    # producer.send(
                    #     # STATUS_TOPIC,
                    #     key=str(car_id).encode("utf-8"),
                    #     value=kafka_record
                    # )

                except Exception as e:
                    add_log("ERROR", "kafka", f"EV {car_id} send error: {e}")

            # =========================
            # LOGGING
            # =========================
            add_log(
                "INFO",
                "producer",
                f"EV={car_id} ts={record.get('timestamp_s')} "
                f"soc={record.get('soc_pct')} "
                f"segment={record.get('id_segment')}"
            )

            time.sleep(RECORD_INTERVAL_SECONDS)

    except Exception:
        add_log("ERROR", "producer", f"EV {car_id} crashed:\n{traceback.format_exc()}")

    finally:
        if producer:
            producer.flush()
            producer.close()

        add_log("INFO", "producer", f"EV {car_id} producer stopped")
