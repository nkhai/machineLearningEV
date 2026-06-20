"""
Delta Lake Batch Processing Job
Reads data from Delta Lake, performs transformations, and writes results
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, avg, max, min, window
from delta import configure_spark_with_delta_pip
from delta.tables import DeltaTable

def create_spark_session():
    builder = SparkSession.builder \
        .appName("DeltaBatchProcessing") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .config("spark.hadoop.fs.defaultFS", "hdfs://namenode:8020")
    
    spark = configure_spark_with_delta_pip(builder).getOrCreate()
    return spark

def main():
    # Initialize Spark
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("INFO")
    
    # Delta Lake paths
    input_path = "hdfs://namenode:8020/delta/lakehouse/streaming_data"
    output_path = "hdfs://namenode:8020/delta/lakehouse/aggregated_data"
    
    print(f"Reading from Delta Lake: {input_path}")
    
    # Read from Delta Lake
    df = spark.read.format("delta").load(input_path)
    
    print(f"Total records: {df.count()}")
    df.printSchema()
    
    # Perform aggregations
    aggregated_df = df.groupBy(
        window(col("timestamp"), "1 hour")
    ).agg(
        count("*").alias("record_count"),
        avg("metric").alias("avg_metric"),
        max("metric").alias("max_metric"),
        min("metric").alias("min_metric")
    )
    
    # Show sample results
    print("Aggregated results:")
    aggregated_df.show(10, truncate=False)
    
    # Write results to Delta Lake
    print(f"Writing results to: {output_path}")
    aggregated_df.write \
        .format("delta") \
        .mode("overwrite") \
        .option("overwriteSchema", "true") \
        .save(output_path)
    
    # Optimize Delta table
    print("Optimizing Delta table...")
    delta_table = DeltaTable.forPath(spark, output_path)
    delta_table.optimize().executeCompaction()
    
    # Show table history
    print("\nDelta table history:")
    delta_table.history().show(5, truncate=False)
    
    # Vacuum old files (older than 7 days)
    print("\nVacuuming old files...")
    delta_table.vacuum(168)  # 168 hours = 7 days
    
    print("Batch processing completed successfully!")

if __name__ == "__main__":
    main()
