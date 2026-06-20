# Quick Start Guide - Lakehouse Platform

## ⚡ Khởi động trong 3 phút

### Bước 1: Cấu hình môi trường
```bash
cd /opt/eet_dp_ai_predictive/infra
# Chỉnh sửa file .env
nano .env
```

Đảm bảo các biến sau được cấu hình:
```bash
HOST_NAME=hc1-c-0003u.hc.apac.bosch.com  # Hostname của server
DATA_ROOT_PATH=/mnt/external_ssd/eet_dp_lakehouse_data  # Đường dẫn lưu data
AIRFLOW_UID=50000  # User ID cho Airflow
```

### Bước 2: Khởi động hệ thống
```bash
./deploy.sh
```

Chờ 2-3 phút để tất cả services khởi động.

### Bước 3: Kiểm tra trạng thái
```bash
docker compose ps
```

Tất cả services nên ở trạng thái "Up" hoặc "healthy"

### Bước 4: Truy cập Web UIs

| Service | URL | Login |
|---------|-----|-------|
| Airflow | http://localhost:8080 | airflow/airflow |
| HDFS NameNode | http://localhost:9870 | - |
| YARN ResourceManager | http://localhost:8088 | - |
| pgAdmin | http://localhost:46016 | pgadmin@bosch.com/admin |
| Flower (Celery) | http://localhost:5555 | - |

### Bước 5: Test hệ thống

#### Test HDFS
```bash
# Kiểm tra HDFS Web UI
firefox http://localhost:9870

# Tạo thư mục test
docker exec -it namenode hdfs dfs -mkdir -p /user/test
docker exec -it namenode hdfs dfs -ls /user
```

#### Test Kafka
```bash
# Tạo topic
docker exec -it kafka kafka-topics --create \
  --topic test-topic \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1

# List topics
docker exec -it kafka kafka-topics --list \
  --bootstrap-server localhost:9092
```

#### Test Airflow
1. Mở http://localhost:8080
2. Login với airflow/airflow
3. Kiểm tra các DAGs có sẵn
4. Kích hoạt và test run một DAG

### Bước 6: Chạy Pipeline với Airflow

```bash
# 1. Truy cập Airflow UI
firefox http://localhost:8080

# 2. Tạo DAG mới trong src/airflow/dags/

# 3. Kích hoạt DAG từ UI

# 4. Monitor execution
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-worker
```

## 📊 Components Overview

```
✅ Kafka (Streaming)       - Single broker với KRaft mode
✅ HDFS (Storage)          - 1 NameNode + 1 DataNode
✅ YARN (Resources)        - 1 ResourceManager + 1 NodeManager
✅ Airflow (Orchestration) - Complete CeleryExecutor setup
✅ PostgreSQL (Data)       - Airflow metastore
✅ Redis (Cache)           - Celery broker
✅ pgAdmin (Management)    - Database admin UI
```

## 🛠️ Common Commands

### Xem logs
```bash
docker compose logs -f namenode
docker compose logs -f airflow-scheduler
docker compose logs -f kafka
```

### Restart service
```bash
docker compose restart <service-name>
```

### Stop all services
```bash
docker compose down
```

### Start specific services
```bash
docker compose up -d kafka namenode datanode-1
```

### Clean up (xóa tất cả data)
```bash
docker compose down -v
```

## 📱 Service Ports

### Host Mode (Direct localhost access)
| Port | Service |
|------|---------|
| 6379 | Redis |
| 8020 | HDFS NameNode RPC |
| 8080 | Airflow Web UI |
| 8088 | YARN ResourceManager UI |
| 9092 | Kafka Broker |
| 9093 | Kafka Controller |
| 9870 | HDFS NameNode UI |

### Bridge Network
| Port | Service |
|------|---------|
| 45432 | PostgreSQL |
| 46016 | pgAdmin |
| 5555 | Flower (Celery Monitor) |

## 🔍 Troubleshooting

### Service không khởi động?
```bash
# Xem logs
docker compose logs -f <service-name>

# Restart
docker compose restart <service-name>

# Rebuild và restart
docker compose up -d --force-recreate <service-name>
```

### Out of memory?
- Tăng Docker memory limit (Settings → Resources)
- Minimum: 8GB RAM, Recommended: 16GB

### HDFS SafeMode?
```bash
docker exec -it namenode hdfs dfsadmin -safemode leave
```

### Kafka connection timeout?
```bash
# Check Kafka status
docker exec -it kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092
```

### Hostname resolution issues?
```bash
# Kiểm tra HOST_NAME trong .env
cat .env | grep HOST_NAME

# Test hostname
ping $HOST_NAME
```

### Permission denied?
```bash
# Check data directory permissions
ls -la $DATA_ROOT_PATH

# Fix permissions (if needed)
sudo chown -R 1000:100 $DATA_ROOT_PATH
sudo chmod -R 777 $DATA_ROOT_PATH
```

## 📚 Next Steps

1. **Customize configurations**: 
   - Edit `.env` for environment variables
   - Modify Hadoop configs in `infra/configs/hadoop/`
2. **Add your DAGs**: `src/airflow/dags/`
3. **Monitor services**: Use Web UIs listed above
4. **Scale resources**: Adjust Docker resources as needed

## 💡 Tips

- Monitor resource usage: `docker stats`
- Check disk space: `docker system df`
- View all containers: `docker compose ps`
- Follow logs: `docker compose logs -f <service>`
- Exec into container: `docker exec -it <container> bash`

## 🆘 Need Help?

1. Check documentation: `infra/docs/README_VI.md`
2. View service logs: `docker compose logs -f <service>`
3. Check status: `docker compose ps`
4. Verify environment: `cat .env`

## 🔧 Maintenance Commands

```bash
# Backup data
tar -czf backup.tar.gz $DATA_ROOT_PATH

# Clean up unused Docker resources
docker system prune -a

# Reset everything (WARNING: Deletes all data)
docker compose down -v
./deploy.sh
```

---

Happy Data Engineering! 🚀

*Last Updated: January 23, 2026*
