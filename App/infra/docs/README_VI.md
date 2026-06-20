# On-Premise Lakehouse Platform

Hệ thống Lakehouse tương tự Databricks, triển khai on-premise với Docker Compose.

## 📋 Kiến trúc hệ thống

### Streaming Layer
- **Kafka Cluster**: 3 brokers (kafka-broker-1, kafka-broker-2, kafka-broker-3)
- **Zookeeper**: Quản lý Kafka cluster

### Storage Layer
- **HDFS NameNode**: Quản lý metadata
- **HDFS DataNode**: 2 nodes lưu trữ dữ liệu phân tán

### Compute Layer
- **Spark Master**: Quản lý Spark cluster
- **Spark Worker**: 2 workers xử lý dữ liệu
- **Delta Lake**: Lakehouse storage layer với ACID transactions

### Resource Management
- **YARN ResourceManager**: Quản lý tài nguyên cluster
- **YARN NodeManager**: 2 node managers

### Orchestration Layer
- **Airflow Web**: Giao diện web UI
- **Airflow Scheduler**: Lập lịch các DAG
- **Airflow Worker**: 2 workers thực thi tasks
- **Airflow Triggerer**: Xử lý deferrable operators

### Data Layer
- **PostgreSQL**: Database cho Airflow và Hive Metastore
- **Redis**: Cache và message broker cho Airflow

## 🚀 Cài đặt và Khởi động

### Yêu cầu hệ thống
- Docker 20.10+
- Docker Compose 2.0+
- RAM tối thiểu: 16GB
- Disk space: 50GB+
- CPU: 8 cores+

### Khởi động nhanh

```bash
cd /opt/eet_dp_ai_predictive/infra

# Cấp quyền thực thi cho scripts
chmod +x scripts/*.sh

# Chạy setup hoàn chỉnh (khởi động + khởi tạo)
./scripts/setup.sh
```

### Khởi động từng bước

```bash
# 1. Khởi động tất cả services
./scripts/start.sh

# 2. Chờ services khởi động (60-90 giây)
sleep 60

# 3. Khởi tạo HDFS directories
./scripts/init-hdfs.sh

# 4. Tạo Kafka topics
./scripts/create-kafka-topics.sh

# 5. Kiểm tra trạng thái
./scripts/check-status.sh
```

## 🌐 Truy cập Web UI

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow Web UI | http://localhost:8090 | ${AIRFLOW_ADMIN_USERNAME}/${AIRFLOW_ADMIN_PASSWORD} |
| Spark Master | http://localhost:8080 | - |
| HDFS NameNode | http://localhost:9870 | - |
| YARN ResourceManager | http://localhost:8088 | - |
| Spark Worker 1 | http://localhost:8081 | - |
| Spark Worker 2 | http://localhost:8082 | - |

## 🔌 Kết nối Services

### Kafka
```python
bootstrap_servers = [
    'kafka-broker-1:9092',
    'kafka-broker-2:9093',
    'kafka-broker-3:9094'
]
```

### HDFS
```python
hdfs_url = 'hdfs://namenode:8020'
```

### Spark Master
```python
spark_master = 'spark://spark-master:7077'
```

### PostgreSQL
```bash
Host: localhost
Port: 5432
User: ${POSTGRES_USER}
Password: ${POSTGRES_PASSWORD}
Databases: metastore, airflow, hive_metastore
```

### Redis
```bash
Host: localhost
Port: 6379
Password: ${REDIS_PASSWORD}
```

## 📝 Sử dụng

### 1. Chạy Spark Job

```bash
# Test Spark setup
./scripts/submit-spark-job.sh ../src/spark/test_spark_setup.py

# Kafka to Delta Lake streaming
./scripts/submit-spark-job.sh ../src/spark/kafka_to_delta.py

# Batch processing
./scripts/submit-spark-job.sh ../src/spark/delta_batch_processing.py
```

### 2. Producer/Consumer Kafka

```bash
# Chạy Kafka producer (trong container hoặc local)
docker exec -it kafka-broker-1 bash
cd /opt/src/kafka
python producer.py

# Chạy Kafka consumer
docker exec -it kafka-broker-1 bash
cd /opt/src/kafka
python consumer.py
```

### 3. Quản lý Airflow DAGs

1. Truy cập http://localhost:8090
2. Login với ${AIRFLOW_ADMIN_USERNAME}/${AIRFLOW_ADMIN_PASSWORD}
3. Kích hoạt DAG từ UI
4. Monitor task execution

### 4. Làm việc với HDFS

```bash
# List files
docker exec -it namenode hdfs dfs -ls /

# Create directory
docker exec -it namenode hdfs dfs -mkdir -p /user/data

# Upload file
docker exec -it namenode hdfs dfs -put /local/path /hdfs/path

# Download file
docker exec -it namenode hdfs dfs -get /hdfs/path /local/path

# Check HDFS status
docker exec -it namenode hdfs dfsadmin -report
```

## 🔧 Scripts quản lý

### Khởi động và Dừng

```bash
# Khởi động tất cả services
./scripts/start.sh

# Dừng tất cả services
./scripts/stop.sh

# Dừng và xóa volumes
cd /opt/eet_dp_ai_predictive/infra
docker-compose down -v
```

### Kiểm tra và Logs

```bash
# Kiểm tra trạng thái services
./scripts/check-status.sh

# Xem logs service cụ thể
./scripts/logs.sh spark-master
./scripts/logs.sh airflow-webserver
./scripts/logs.sh kafka-broker-1

# Xem logs với số dòng cụ thể
./scripts/logs.sh namenode 200
```

## 📂 Cấu trúc thư mục

```
eet_dp_ai_predictive/
├── infra/
│   ├── docker-compose.yaml       # Docker Compose configuration
│   ├── configs/                  # Configuration files
│   │   ├── spark/
│   │   │   ├── spark-defaults.conf
│   │   │   └── log4j2.properties
│   │   ├── hadoop/
│   │   │   ├── core-site.xml
│   │   │   ├── hdfs-site.xml
│   │   │   ├── yarn-site.xml
│   │   │   └── mapred-site.xml
│   │   ├── kafka/
│   │   │   └── server.properties
│   │   ├── postgres/
│   │   │   └── init-databases.sh
│   │   ├── redis/
│   │   │   └── redis.conf
│   │   └── airflow/
│   │       └── airflow.cfg
│   └── scripts/                  # Management scripts
│       ├── setup.sh              # Complete setup
│       ├── start.sh              # Start all services
│       ├── stop.sh               # Stop all services
│       ├── check-status.sh       # Check status
│       ├── logs.sh               # View logs
│       ├── submit-spark-job.sh   # Submit Spark jobs
│       ├── create-kafka-topics.sh # Create Kafka topics
│       └── init-hdfs.sh          # Initialize HDFS
└── src/
    ├── airflow/
    │   └── dags/                 # Airflow DAGs
    │       ├── lakehouse_etl_pipeline.py
    │       └── test_setup.py
    ├── spark/                    # Spark applications
    │   ├── kafka_to_delta.py
    │   ├── delta_batch_processing.py
    │   └── test_spark_setup.py
    └── kafka/                    # Kafka utilities
        ├── producer.py
        └── consumer.py
```

## 🎯 Ví dụ End-to-End

### Pipeline hoàn chỉnh: Kafka → Spark → Delta Lake → Airflow

1. **Tạo Kafka topic và gửi data**:
```bash
docker exec -it kafka-broker-1 bash
python /opt/src/kafka/producer.py
```

2. **Chạy Spark streaming job**:
```bash
./scripts/submit-spark-job.sh ../src/spark/kafka_to_delta.py
```

3. **Kích hoạt Airflow DAG**:
- Truy cập http://localhost:8090
- Kích hoạt DAG `lakehouse_etl_pipeline`
- Monitor execution

4. **Xem kết quả trong Delta Lake**:
```bash
docker exec -it spark-master pyspark
```
```python
df = spark.read.format("delta").load("hdfs://namenode:8020/delta/lakehouse/aggregated_data")
df.show()
```

## 🛠️ Troubleshooting

### Service không khởi động

```bash
# Kiểm tra logs
./scripts/logs.sh <service-name>

# Khởi động lại service cụ thể
docker-compose restart <service-name>

# Xem resource usage
docker stats
```

### HDFS SafeMode

```bash
# Thoát safemode
docker exec -it namenode hdfs dfsadmin -safemode leave
```

### Kafka connection issues

```bash
# Kiểm tra Kafka brokers
docker exec -it kafka-broker-1 kafka-broker-api-versions --bootstrap-server localhost:9092

# List topics
docker exec -it kafka-broker-1 kafka-topics --list --bootstrap-server localhost:9092
```

### Airflow connection issues

```bash
# Reset Airflow database
docker exec -it airflow-webserver airflow db reset

# Create admin user
docker exec -it airflow-webserver airflow users create \
    --username ${AIRFLOW_ADMIN_USERNAME} \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email ${AIRFLOW_ADMIN_EMAIL} \
    --password ${AIRFLOW_ADMIN_PASSWORD}
```

## 📊 Monitoring

### Resource Usage

```bash
# Docker stats
docker stats

# Disk usage
docker system df

# Volume usage
docker volume ls
```

### Health Checks

```bash
# Run health check script
./scripts/check-status.sh

# Check individual services
curl http://localhost:8090/health        # Airflow
curl http://localhost:9870/jmx           # HDFS
curl http://localhost:8088/cluster       # YARN
curl http://localhost:8080               # Spark
```

## 🔒 Security Notes

⚠️ **QUAN TRỌNG**: Cấu hình hiện tại dành cho môi trường development/testing.

Đối với production, cần:
- Thay đổi tất cả passwords mặc định
- Bật authentication và encryption
- Cấu hình network security
- Sử dụng secrets management
- Enable SSL/TLS
- Cấu hình firewall rules

## 📚 Tài liệu tham khảo

- [Apache Spark Documentation](https://spark.apache.org/docs/latest/)
- [Delta Lake Documentation](https://docs.delta.io/)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Hadoop Documentation](https://hadoop.apache.org/docs/stable/)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)

## 🤝 Đóng góp

Để đóng góp vào project:
1. Fork repository
2. Tạo feature branch
3. Commit changes
4. Push to branch
5. Tạo Pull Request

## 📄 License

MIT License
