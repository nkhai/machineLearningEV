"""
Test Spark connectivity and Delta Lake setup
"""
from pyspark.sql import SparkSession
from delta import configure_spark_with_delta_pip
import sys

def test_spark_setup():
    print("=" * 50)
    print("Testing Spark Setup")
    print("=" * 50)
    
    try:
        # Create Spark session
        builder = SparkSession.builder \
            .appName("TestSparkSetup") \
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        
        spark = configure_spark_with_delta_pip(builder).getOrCreate()
        
        print("✓ Spark Session created successfully")
        print(f"  Spark Version: {spark.version}")
        print(f"  Master: {spark.sparkContext.master}")
        
        # Test DataFrame operations
        data = [
            ("Alice", 34, 1000),
            ("Bob", 45, 1500),
            ("Charlie", 28, 800),
        ]
        columns = ["name", "age", "salary"]
        
        df = spark.createDataFrame(data, columns)
        print("\n✓ DataFrame created successfully")
        df.show()
        
        # Test Delta Lake write
        test_path = "/tmp/delta_test_table"
        print(f"\n✓ Testing Delta Lake write to {test_path}")
        df.write.format("delta").mode("overwrite").save(test_path)
        
        # Test Delta Lake read
        print("✓ Testing Delta Lake read")
        df_read = spark.read.format("delta").load(test_path)
        df_read.show()
        
        print("\n" + "=" * 50)
        print("All tests passed successfully! ✓")
        print("=" * 50)
        
        spark.stop()
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_spark_setup())
