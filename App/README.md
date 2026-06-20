# On-Premise Lakehouse Platform (Databricks-like)

🏗️ A complete on-premise Data Lakehouse built with Docker Compose

This project provides a large-scale data processing platform similar to Databricks, including all components required for a modern Lakehouse.

## 🎯 Overview

This system offers a complete Lakehouse solution with:

- **Streaming**: Kafka with KRaft mode (no Zookeeper) for real-time data ingestion
- **Storage**: HDFS cluster for distributed storage
- **Resource Management**: YARN for cluster resource management
- **Orchestration**: Airflow 3.x with CeleryExecutor for workflow orchestration
- **Data Services**: PostgreSQL, Redis, and pgAdmin
- **Flexible Configuration**: Environment-based setup with HOST_NAME variable

## 🚀 Quick Start

```bash
# Change to the infra directory
cd /opt/eet_dp_ai_predictive/infra

# Configure environment (edit HOST_NAME and DATA_ROOT_PATH)
nano .env

# Run deployment
./deploy.sh
```

**Startup time**: ~2–3 minutes

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                       │
│  Airflow: API Server | Scheduler | DAG Processor |          │
│  Worker | Triggerer | Flower (monitoring)                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  RESOURCE MANAGEMENT                         │
│  YARN: ResourceManager + NodeManager                         │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌────────────────────┬────────────────────────────────────────┐
│   STORAGE LAYER    │        STREAMING LAYER                 │
│  HDFS: NameNode +  │   Kafka: KRaft Mode (No Zookeeper)    │
│  DataNode          │   Single Broker                        │
└────────────────────┴────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  PostgreSQL (Airflow) | Redis (Celery) | pgAdmin            │
└─────────────────────────────────────────────────────────────┘
```

## 🌐 Web UI Endpoints

| Service | URL | Credentials |
|---------|-----|-------------|
| 🎨 Airflow Web UI | http://localhost:8080 | airflow / airflow |
| 💾 HDFS NameNode UI | http://localhost:9870 | - |
| 📊 YARN ResourceManager | http://localhost:8088 | - |
| 🌸 Flower (Celery) | http://localhost:5555 | - |
| 🐘 pgAdmin | http://localhost:46016 | pgadmin@bosch.com / admin |

## 📦 Components

### Streaming Layer (Kafka)
- 🔴 **Kafka Broker** — KRaft mode (no Zookeeper dependency)
  - Port 9092: Client connections
  - Port 9093: Controller

### Storage Layer (HDFS)
- 🔵 **NameNode** — Metadata management (port 9870 UI, 8020 RPC)
- 🟡 **DataNode** — Distributed storage

### Resource Management (YARN)
- 📊 **ResourceManager** — Resource allocation (port 8088 UI)
- 💻 **NodeManager** — Node-level resource management

### Orchestration Layer (Airflow 3.x)
- 🎨 **API Server** — API endpoint (port 8080)
- ⏰ **Scheduler** — DAG scheduling
- 🔄 **DAG Processor** — DAG file processing
- 👷 **Worker** — Task execution (CeleryExecutor)
- 🎯 **Triggerer** — Async task handling
- 🌸 **Flower** — Celery monitoring (port 5555)

### Data Layer
- 🐘 **PostgreSQL** — Airflow metastore (port 45432)
- 🔴 **Redis** — Celery message broker (port 6379)
- 🔧 **pgAdmin** — Database management UI (port 46016)

## 📝 Basic Usage

### 1. Start the platform

```bash
cd /opt/eet_dp_ai_predictive/infra
docker compose up -d
```

### 2. Check service status

```bash
docker compose ps
```

### 3. Work with Kafka

```bash
# Create topic
docker exec -it kafka kafka-topics --create \
  --topic test-topic \
  --bootstrap-server localhost:9092 \
  --partitions 1 \
  --replication-factor 1

# List topics
docker exec -it kafka kafka-topics --list \
  --bootstrap-server localhost:9092

# Produce messages
docker exec -it kafka kafka-console-producer \
  --topic test-topic \
  --bootstrap-server localhost:9092

# Consume messages
docker exec -it kafka kafka-console-consumer \
  --topic test-topic \
  --bootstrap-server localhost:9092 \
  --from-beginning
```

### 4. Manage HDFS

```bash
# List files
docker exec -it namenode hdfs dfs -ls /

# Create directory
docker exec -it namenode hdfs dfs -mkdir -p /user/data

# Upload file
docker exec -it namenode hdfs dfs -put /local/file /hdfs/path

# Check HDFS status
docker exec -it namenode hdfs dfsadmin -report
```

### 5. Airflow DAGs

1. Visit: http://localhost:8080
2. Login: airflow / airflow
3. Add DAGs to `src/airflow/dags/`
4. Enable and trigger DAGs from UI
5. Monitor execution and logs

## 🗂️ Project Structure

```
eet_dp_ai_predictive/
├── infra/                          # Infrastructure layer
│   ├── docker-compose.yaml         # Docker Compose configuration
│   ├── deploy.sh                   # Deployment script
│   ├── .env                        # Environment variables
│   ├── storage.env.example         # Storage config example
│   ├── configs/                    # Configuration files
│   │   └── hadoop/                 # HDFS/YARN configs
│   │       ├── core-site.xml
│   │       ├── hdfs-site.xml
│   │       ├── yarn-site.xml
│   │       └── mapred-site.xml
│   ├── scripts/                    # Management scripts
│   │   └── replace-env-vars.sh     # Environment variable replacer
│   └── docs/                       # Documentation
│       ├── README_VI.md            # Vietnamese docs
│       └── DEPLOYMENT_SUMMARY.md   # Deployment summary
└── src/                            # Source code
    └── airflow/dags/               # Airflow DAGs
```

## 🔧 Management Commands

| Command | Description |
|--------|-------|
| `docker compose up -d` | Start all services |
| `docker compose down` | Stop all services |
| `docker compose ps` | Check status of services |
| `docker compose logs -f <service>` | View logs of a specific service |
| `docker compose restart <service>` | Restart a specific service |
| `./deploy.sh` | Deploy with full setup (first time) |
| `docker compose down -v` | Remove containers and volumes (DELETE DATA) |

## 📚 End-to-End Example

### Pipeline: Kafka → HDFS → Airflow Processing

```bash
# 1. Start the platform
cd /opt/eet_dp_ai_predictive/infra
./deploy.sh

# 2. Create Kafka topic
docker exec -it kafka kafka-topics --create \
  --topic data-stream \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1

# 3. Send test data to Kafka
docker exec -it kafka kafka-console-producer \
  --topic data-stream \
  --bootstrap-server localhost:9092
# Type messages and press Enter

# 4. Create HDFS directory
docker exec -it namenode hdfs dfs -mkdir -p /data/input

# 5. Create and enable Airflow DAG at http://localhost:8080

# 6. Monitor execution
docker compose logs -f airflow-scheduler
docker compose logs -f airflow-worker

# 7. Check HDFS output
docker exec -it namenode hdfs dfs -ls /data/output
```

## 🛠️ Troubleshooting

### Check logs
```bash
docker compose logs -f <service-name>
docker compose logs --tail 100 namenode
```

### Restart a service
```bash
docker compose restart <service-name>
```

### HDFS SafeMode
```bash
docker exec -it namenode hdfs dfsadmin -safemode leave
```

### Reset Airflow database
```bash
docker exec -it airflow-scheduler airflow db reset
```

### Check Kafka status
```bash
docker exec -it kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092
```

### Hostname issues
```bash
# Check HOST_NAME in .env
cat /opt/eet_dp_ai_predictive/infra/.env | grep HOST_NAME

# Verify hostname resolution
ping $(cat /opt/eet_dp_ai_predictive/infra/.env | grep HOST_NAME | cut -d'=' -f2)
```

### Permission issues
```bash
# Check data directory permissions
ls -la $DATA_ROOT_PATH

# Fix if needed
sudo chown -R 1000:100 $DATA_ROOT_PATH
sudo chmod -R 777 $DATA_ROOT_PATH
```

## 📊 Monitoring

```bash
# Docker stats
docker stats

# Disk usage
docker system df

# Check all services
docker compose ps

# Follow logs
docker compose logs -f

# Check specific service health
docker inspect <container-name> | grep -A 5 Health
```

## ⚙️ System Requirements

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 30GB+
- **CPU**: 4 cores minimum (8 cores recommended)
- **OS**: Linux (Ubuntu 20.04+, CentOS 7+, etc.)

### Important Notes
- Host mode networking requires Linux
- Configure `HOST_NAME` in `.env` to match your server hostname
- Set `DATA_ROOT_PATH` to a location with sufficient disk space

## 🔒 Security Notes

⚠️ Note: The current configuration targets development/testing.

For production:
- Change all default passwords
- Enable authentication & encryption
- Configure SSL/TLS
- Set up firewall rules
- Use secrets management

## 📖 Documentation

📄 Full documentation (Vietnamese): [./infra/docs/README_VI.md](./infra/docs/README_VI.md)  
📄 Quick Start Guide: [./QUICKSTART.md](./QUICKSTART.md)  
📄 Project Index: [./INDEX.md](./INDEX.md)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License

## 🙏 Acknowledgments

- Apache Kafka, Hadoop, Airflow communities
- Docker and Docker Compose
- Open source community

---

**Built with ❤️ for Data Engineering**

*Last Updated: January 23, 2026*

This section details the network configuration, including internal service communication and external port mappings. This is crucial for deployment, debugging, and configuring firewall rules.

All services are connected on a custom Docker bridge network named `lakehouse-network`, allowing them to communicate with each other using their service names.

### Internal Service Communication

Services within the Docker network communicate with each other using their container names and internal ports.

| Service           | Connects To         | Address (within Docker network)      |
| ----------------- | ------------------- | ------------------------------------ |
| **Kafka Brokers** | Zookeeper           | `zookeeper:2181`                     |
| **Hadoop Datanodes**| Namenode            | `namenode:8020`                      |
| **YARN Nodemanagers**| ResourceManager     | `resourcemanager:8032`                 |
| **Spark Workers** | Spark Master        | `spark://spark-master:7077`          |
| **Spark Apps**    | HDFS                | `hdfs://namenode:8020`               |
| **Airflow**       | PostgreSQL          | `postgres:5432`                      |
| **Airflow**       | Redis               | `redis:6379`                         |
| **All Services**  | Kafka Brokers       | `kafka-broker-1:9092`, `kafka-broker-2:9093`, etc. |

### External Port Mappings

The following ports are exposed to the host machine. If deploying on a cloud server, ensure your firewall or security group rules allow traffic on these external ports.

| Service                 | Internal Port | External Port (Host) | Purpose                               | URL for Access (if applicable)        |
| ----------------------- | ------------- | -------------------- | ------------------------------------- | ------------------------------------- |
| **Zookeeper**           | `2181`        | `46000`              | Client Connections                    | `localhost:46000`                     |
| **Kafka Broker 1**      | `19092`       | `46001`              | External Client Access                | `localhost:46001`                     |
| **Kafka Broker 2**      | `19093`       | `46002`              | External Client Access                | `localhost:46002`                     |
| **Kafka Broker 3**      | `19094`       | `46003`              | External Client Access                | `localhost:46003`                     |
| **HDFS Namenode**       | `9870`        | `46004`              | Web UI                                | `http://localhost:46004`              |
| **HDFS Datanode 1**     | `9864`        | `46005`              | Web UI                                | `http://localhost:46005`              |
| **HDFS Datanode 2**     | `9864`        | `46006`              | Web UI                                | `http://localhost:46006`              |
| **YARN ResourceManager**| `8088`        | `46007`              | Web UI                                | `http://localhost:46007`              |
| **YARN Nodemanager 1**  | `8042`        | `46008`              | Web UI                                | `http://localhost:46008`              |
| **YARN Nodemanager 2**  | `8042`        | `46009`              | Web UI                                | `http://localhost:46009`              |
| **Spark Master**        | `8080`        | `46010`              | Web UI                                | `http://localhost:46010`              |
| **Spark Worker 1**      | `8081`        | `46011`              | Web UI                                | `http://localhost:46011`              |
| **Spark Worker 2**      | `8081`        | `46012`              | Web UI                                | `http://localhost:46012`              |
| **PostgreSQL**          | `5432`        | `46013`              | Database Client Access                | `localhost:46013`                     |
| **Redis**               | `6379`        | `46014`              | Redis Client Access                   | `localhost:46014`                     |
| **Airflow Webserver**   | `8080`        | `46015`              | Web UI                                | `http://localhost:46015`              |