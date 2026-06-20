# 📋 Project Index - Lakehouse Platform

## 📁 Complete File Structure

```
eet_dp_ai_predictive/
│
├── 📄 README.md                          # Main project documentation
├── 📄 QUICKSTART.md                      # Quick start guide (5 minutes)
├── 📄 Makefile                           # Make commands for management
├── 📄 .gitignore                         # Git ignore rules
│
├── 📂 infra/                             # Infrastructure layer
│   │
│   ├── 📄 docker-compose.yaml            # Services configuration
│   ├── 📄 deploy.sh                      # Deployment script
│   ├── 📄 .env                           # Environment variables
│   ├── 📄 storage.env.example            # Storage config example
│   │
│   ├── 📂 configs/                       # Configuration files
│   │   │
│   │   └── 📂 hadoop/
│   │       ├── core-site.xml             # Hadoop core settings
│   │       ├── hdfs-site.xml             # HDFS configuration
│   │       ├── yarn-site.xml             # YARN configuration
│   │       ├── mapred-site.xml           # MapReduce settings
│   │       └── capacity-scheduler.xml    # YARN capacity scheduler
│   │
│   ├── 📂 scripts/                       # Management scripts
│   │   └── replace-env-vars.sh           # 🔧 Environment variable replacer
│   │
│   └── 📂 docs/                          # Documentation
│       ├── README_VI.md                  # Vietnamese documentation
│       └── DEPLOYMENT_SUMMARY.md         # Deployment summary
│
└── 📂 src/                               # Source code
    │
    ├── 📄 requirements.txt               # Python dependencies
    │
    ├── 📂 airflow/dags/                  # Airflow DAG definitions
    │   ├── lakehouse_etl_pipeline.py     # Complete ETL pipeline DAG
    │   └── test_setup.py                 # Test DAG for verification
    │
    ├── 📂 spark/                         # Spark applications
    │   ├── kafka_to_delta.py             # Streaming: Kafka → Delta Lake
    │   ├── delta_batch_processing.py     # Batch processing with Delta
    │   └── test_spark_setup.py           # Spark connectivity test
    │
    └── 📂 kafka/                         # Kafka utilities
        ├── producer.py                   # Kafka message producer
        └── consumer.py                   # Kafka message consumer
```

---

## 📊 Services Overview

### Streaming Layer (1 container)
- `kafka` - Kafka broker with KRaft mode (no Zookeeper)
  - Port 9092: Client connections
  - Port 9093: Controller

### Storage Layer (2 containers)
- `namenode` - HDFS NameNode
  - Port 9870: Web UI
  - Port 8020: RPC
- `datanode-1` - HDFS DataNode

### Resource Management (2 containers)
- `resourcemanager` - YARN ResourceManager
  - Port 8088: Web UI
- `nodemanager-1` - YARN NodeManager

### Orchestration Layer (7 containers)
- `airflow-init` - Airflow initialization (one-time)
- `airflow-apiserver` - Airflow API server
  - Port 8080: API endpoint
- `airflow-scheduler` - DAG scheduler
- `airflow-dag-processor` - DAG processor
- `airflow-worker` - Celery worker
- `airflow-triggerer` - Deferrable operator handler
- `flower` - Celery monitoring (optional)
  - Port 5555: Web UI

### Data Layer (3 containers)
- `postgres` - PostgreSQL database
  - Port 45432: Database connection
- `pgadmin` - PostgreSQL admin UI
  - Port 46016: Web UI
- `redis` - Redis cache
  - Port 6379: Redis connection

---

## 🎯 Quick Commands Reference

### Using Deploy Script
```bash
cd infra/
./deploy.sh              # Complete deployment with setup
```

### Using Docker Compose
```bash
cd infra/
docker compose up -d            # Start all services
docker compose ps               # Check status
docker compose logs -f <name>   # Follow logs
docker compose down             # Stop all services
docker compose down -v          # Stop and remove volumes
```

### Environment Configuration
```bash
# Edit .env file to configure:
# - HOST_NAME: Server hostname
# - DATA_ROOT_PATH: Data storage location
# - AIRFLOW_UID: Airflow user ID
```

---

## 🌐 Web UIs & Endpoints

| Service | URL | Port | Login |
|---------|-----|------|-------|
| Airflow Web UI | http://localhost:8080 | 8080 | airflow/airflow |
| HDFS NameNode UI | http://localhost:9870 | 9870 | - |
| YARN ResourceManager | http://localhost:8088 | 8088 | - |
| pgAdmin | http://localhost:46016 | 46016 | pgadmin@bosch.com/admin |
| Flower (Celery) | http://localhost:5555 | 5555 | - |

### Network Configuration
- **Host mode**: Kafka, HDFS, YARN, Redis, Airflow (all use localhost directly)
- **Bridge network**: PostgreSQL, pgAdmin
- **HOST_NAME variable**: Configurable in `.env` for hostname references

---

## 📚 Documentation Map

1. **Getting Started**
   - [README.md](./README.md) - Main overview
   - [QUICKSTART.md](./QUICKSTART.md) - 5-minute start guide

2. **Comprehensive Guides**
   - [infra/docs/README_VI.md](./infra/docs/README_VI.md) - Complete Vietnamese guide
   - [infra/docs/DEPLOYMENT_SUMMARY.md](./infra/docs/DEPLOYMENT_SUMMARY.md) - Deployment summary

3. **Configuration**
   - [infra/configs/](./infra/configs/) - All configuration files
   - [infra/configs/.env.template](./infra/configs/.env.template) - Environment variables

4. **Scripts**
   - [infra/scripts/](./infra/scripts/) - All management scripts

5. **Code Examples**
   - [src/airflow/dags/](./src/airflow/dags/) - Airflow DAG examples
   - [src/spark/](./src/spark/) - Spark application examples
   - [src/kafka/](./src/kafka/) - Kafka utilities

---

## 🔑 Key Features

✅ **Streaming**: Kafka with KRaft mode (no Zookeeper dependency)
✅ **Storage**: HDFS distributed storage
✅ **Resources**: YARN resource management
✅ **Orchestration**: Airflow 3.x with CeleryExecutor
✅ **Data**: PostgreSQL for metastore, Redis for caching
✅ **Monitoring**: Web UIs for all services
✅ **Configuration**: Environment variable based setup
✅ **Network**: Host mode for better performance
✅ **Flexible**: Configurable hostname via HOST_NAME variable

---

## 🚀 Typical Workflows

### 1. First Time Setup
```bash
cd infra/
# Configure .env file with HOST_NAME and DATA_ROOT_PATH
./deploy.sh
# Wait 2-3 minutes
docker compose ps
```

### 2. Daily Operations
```bash
cd infra/
docker compose up -d              # Start services
docker compose ps                 # Check health
docker compose logs -f <service>  # Debug issues
docker compose down               # Stop services
```

### 3. Development Workflow
```bash
# Edit DAGs in src/airflow/dags/
cd infra/
docker compose restart airflow-scheduler airflow-dag-processor
# Access Airflow UI at http://localhost:8080
```

### 4. Troubleshooting
```bash
docker compose ps                        # Check all services
docker compose logs -f namenode          # Check HDFS logs
docker compose logs -f airflow-scheduler # Check Airflow logs
docker stats                             # Check resources
```

---

## 📈 Next Steps After Setup

1. ✅ Configure .env: Set `HOST_NAME` and `DATA_ROOT_PATH`
2. ✅ Run deployment: `./infra/deploy.sh`
3. ✅ Verify status: `docker compose ps`
4. ✅ Access Airflow UI: http://localhost:8080 (airflow/airflow)
5. ✅ Check HDFS UI: http://localhost:9870
6. ✅ Check YARN UI: http://localhost:8088
7. ✅ Test Kafka connection: `localhost:9092`
8. ✅ Enable Airflow DAGs and run pipelines

---

## 🆘 Help & Support

### Documentation
- Main README: [README.md](./README.md)
- Quick Start: [QUICKSTART.md](./QUICKSTART.md)
- Full Docs: [infra/docs/README_VI.md](./infra/docs/README_VI.md)

### Commands
```bash
docker compose ps                      # Check system health
docker compose logs -f <service>       # View logs
docker compose restart <service>       # Restart service
```

### Common Issues
- Out of memory → Increase Docker memory to 8GB+
- Service not starting → Check logs: `docker compose logs -f <service>`
- HDFS SafeMode → `docker exec -it namenode hdfs dfsadmin -safemode leave`
- Hostname issues → Check `HOST_NAME` in `.env` file
- Permission denied → Check `DATA_ROOT_PATH` permissions

### Environment Variables
Key variables in `.env`:
- `HOST_NAME`: Server hostname (e.g., hc1-c-0003u.hc.apac.bosch.com)
- `DATA_ROOT_PATH`: Data storage path
- `AIRFLOW_UID`: Airflow user ID (default: 50000)
- `PGADMIN_DEFAULT_PASSWORD`: pgAdmin password

---

**Total Services**: 15 containers
**Setup Time**: ~2-3 minutes
**Documentation**: Vietnamese + English

**Status**: ✅ Ready for Production Use (with security hardening)

---

*Last Updated: January 23, 2026*
