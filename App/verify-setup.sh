#!/bin/bash
# Verification script to check if all files are in place

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         Lakehouse Platform - Setup Verification                 ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

ERRORS=0

# Function to check file existence
check_file() {
    if [ -f "$1" ]; then
        echo "✅ $1"
    else
        echo "❌ MISSING: $1"
        ((ERRORS++))
    fi
}

# Function to check directory
check_dir() {
    if [ -d "$1" ]; then
        echo "✅ $1/"
    else
        echo "❌ MISSING: $1/"
        ((ERRORS++))
    fi
}

# Function to check executable
check_executable() {
    if [ -x "$1" ]; then
        echo "✅ $1 (executable)"
    elif [ -f "$1" ]; then
        echo "⚠️  $1 (not executable - run: chmod +x $1)"
    else
        echo "❌ MISSING: $1"
        ((ERRORS++))
    fi
}

echo "=== Core Files ==="
check_file "README.md"
check_file "QUICKSTART.md"
check_file "INDEX.md"
check_file "Makefile"
check_file ".gitignore"
echo ""

echo "=== Infrastructure ==="
check_file "infra/docker-compose.yaml"
check_dir "infra/configs"
check_dir "infra/scripts"
check_dir "infra/docs"
echo ""

echo "=== Configuration Files ==="
check_file "infra/configs/spark/spark-defaults.conf"
check_file "infra/configs/spark/log4j2.properties"
check_file "infra/configs/hadoop/core-site.xml"
check_file "infra/configs/hadoop/hdfs-site.xml"
check_file "infra/configs/hadoop/yarn-site.xml"
check_file "infra/configs/hadoop/mapred-site.xml"
check_file "infra/configs/kafka/server.properties"
check_file "infra/configs/postgres/init-databases.sh"
check_file "infra/configs/redis/redis.conf"
check_file "infra/configs/airflow/airflow.cfg"
check_file "infra/configs/.env.template"
echo ""

echo "=== Management Scripts ==="
check_executable "infra/scripts/setup.sh"
check_executable "infra/scripts/start.sh"
check_executable "infra/scripts/stop.sh"
check_executable "infra/scripts/check-status.sh"
check_executable "infra/scripts/logs.sh"
check_executable "infra/scripts/submit-spark-job.sh"
check_executable "infra/scripts/create-kafka-topics.sh"
check_executable "infra/scripts/init-hdfs.sh"
echo ""

echo "=== Documentation ==="
check_file "infra/docs/README_VI.md"
check_file "infra/docs/DEPLOYMENT_SUMMARY.md"
echo ""

echo "=== Source Code ==="
check_dir "src/airflow/dags"
check_dir "src/spark"
check_dir "src/kafka"
check_file "src/requirements.txt"
echo ""

echo "=== Airflow DAGs ==="
check_file "src/airflow/dags/lakehouse_etl_pipeline.py"
check_file "src/airflow/dags/test_setup.py"
echo ""

echo "=== Spark Applications ==="
check_file "src/spark/kafka_to_delta.py"
check_file "src/spark/delta_batch_processing.py"
check_file "src/spark/test_spark_setup.py"
echo ""

echo "=== Kafka Utilities ==="
check_file "src/kafka/producer.py"
check_file "src/kafka/consumer.py"
echo ""

echo "════════════════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL FILES PRESENT AND VERIFIED!"
    echo ""
    echo "🚀 Ready to start! Run:"
    echo "   cd infra"
    echo "   ./scripts/setup.sh"
    echo ""
    echo "Or use Make:"
    echo "   make setup"
else
    echo "❌ ERRORS FOUND: $ERRORS file(s) missing or incorrect"
    echo ""
    echo "Please check the missing files above."
fi
echo "════════════════════════════════════════════════════════════════════"
