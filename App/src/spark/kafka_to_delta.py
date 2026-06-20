"""
Kafka to Delta Lake Streaming Job
Reads data from Kafka and writes to Delta Lake in HDFS
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType
from delta import configure_spark_with_delta_pip

# Create Spark Session with Delta Lake support
def create_spark_session():
    builder = SparkSession.builder \
        .appName("KafkaToDeltaLake") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:8020") \
        .config("spark.sql.streaming.checkpointLocation", "hdfs://namenode:8020/spark-checkpoints")
    
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    return spark

def main():
    # Initialize Spark
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("INFO")
    
    # Define schema for incoming Kafka messages
    schema = StructType([
        StructField("id", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("value", StringType(), True),
        StructField("metric", IntegerType(), True)
    ])
    
    # Kafka configuration
    kafka_brokers = "kafka-broker-1:9092,kafka-broker-2:9093,kafka-broker-3:9094"
    kafka_topic = "lakehouse_input"
    
    # Read from Kafka
    df = spark \
        .readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", kafka_brokers) \
        .option("subscribe", kafka_topic) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parse Kafka messages
    parsed_df = df.select(
        from_json(col("value").cast("string"), schema).alias("data"),
        col("timestamp").alias("kafka_timestamp")
    ).select("data.*", "kafka_timestamp")
    
    # Add processing timestamp
    enriched_df = parsed_df.withColumn("processed_at", current_timestamp())
    
    # Delta Lake path in HDFS
    delta_path = "hdfs://namenode:8020/delta/lakehouse/streaming_data"
    
    # Write to Delta Lake
    query = enriched_df \
        .writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("checkpointLocation", "hdfs://namenode:8020/spark-checkpoints/streaming_data") \
        .option("path", delta_path) \
        .start()
    
    print(f"Streaming job started. Writing to {delta_path}")
    print("Query ID:", query.id)
    print("Query Name:", query.name)
    
    # Wait for termination
    query.awaitTermination()

if __name__ == "__main__":
    main()
