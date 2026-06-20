#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Infrastructure Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Load environment variables from .env file
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create a .env file based on the sample configuration."
    exit 1
fi

# Source .env file
export $(grep -v '^#' .env | xargs)

# Check if DATA_ROOT_PATH is set
if [ -z "$DATA_ROOT_PATH" ]; then
    echo -e "${RED}Error: DATA_ROOT_PATH is not set in .env file!${NC}"
    exit 1
fi

echo -e "${YELLOW}Using DATA_ROOT_PATH: $DATA_ROOT_PATH${NC}"
echo ""

# Function to create directory if it doesn't exist
create_directory() {
    local dir=$1
    if [ ! -d "$dir" ]; then
        echo -e "Creating directory: ${GREEN}$dir${NC}"
        mkdir -p "$dir"
    else
        echo -e "Directory already exists: ${YELLOW}$dir${NC}"
    fi
}

# Create all required directories
echo -e "${GREEN}[Step 1/4] Creating data directories...${NC}"
echo ""

# HDFS directories
create_directory "$DATA_ROOT_PATH/hdfs/namenode"
create_directory "$DATA_ROOT_PATH/hdfs/datanode-1"

# Kafka directories
create_directory "$DATA_ROOT_PATH/kafka"

# YARN directories
create_directory "$DATA_ROOT_PATH/yarn/nodemanager-1"

# PostgreSQL directory
create_directory "$DATA_ROOT_PATH/postgres"

# Airflow directories
create_directory "$DATA_ROOT_PATH/airflow/logs"
create_directory "$DATA_ROOT_PATH/airflow/config"

echo ""
echo -e "${GREEN}[Step 2/4] Setting permissions...${NC}"
echo ""

# Set ownership to UID 1000 and GID 100 (Hadoop/Kafka user)
echo "Setting ownership (1000:100) for data directories..."
if [ -w "$DATA_ROOT_PATH" ]; then
    chown -R 1000:100 "$DATA_ROOT_PATH" 2>/dev/null || echo -e "${YELLOW}⚠ Some files could not be changed (already owned by services)${NC}"
else
    echo "Trying with sudo..."
    sudo chown -R 1000:100 "$DATA_ROOT_PATH" 2>/dev/null || echo -e "${YELLOW}⚠ Some files could not be changed (already owned by services)${NC}"
fi

# Set permissions to 777 to avoid any permission issues
echo "Setting permissions (777) for data directories..."
if [ -w "$DATA_ROOT_PATH" ]; then
    chmod -R 777 "$DATA_ROOT_PATH" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
else
    echo "Trying with sudo..."
    sudo chmod -R 777 "$DATA_ROOT_PATH" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
fi

echo -e "${GREEN}Permissions updated (skipped locked files)${NC}"
echo ""

# Build Airflow custom image
echo -e "${GREEN}[Step 3/5] Building Airflow custom image...${NC}"
echo ""

# Check if image already exists
if docker image inspect apache/airflow:3.1.6-hdfs &>/dev/null; then
    echo -e "${YELLOW}✓ Airflow image already exists (apache/airflow:3.1.6-hdfs)${NC}"
    read -p "Do you want to rebuild it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${GREEN}Skipping build...${NC}"
    else
        echo "Building Airflow image with Kafka, HDFS, and PostgreSQL support..."
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        docker build -t apache/airflow:3.1.6-hdfs -f "$SCRIPT_DIR/docker/airflow/Dockerfile" "$SCRIPT_DIR/docker/airflow/"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ Airflow image rebuilt successfully!${NC}"
        else
            echo -e "${RED}✗ Failed to build Airflow image${NC}"
            exit 1
        fi
    fi
else
    echo "Building Airflow image with Kafka, HDFS, and PostgreSQL support..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    docker build -t apache/airflow:3.1.6-hdfs -f "$SCRIPT_DIR/docker/airflow/Dockerfile" "$SCRIPT_DIR/docker/airflow/"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Airflow image built successfully!${NC}"
    else
        echo -e "${RED}✗ Failed to build Airflow image${NC}"
        exit 1
    fi
fi

echo ""

# Verify critical configuration files exist
echo -e "${GREEN}[Step 4/5] Verifying configuration files...${NC}"
echo ""

HADOOP_CONFIGS=(
    "configs/hadoop/core-site.xml"
    "configs/hadoop/hdfs-site.xml"
    "configs/hadoop/yarn-site.xml"
    "configs/hadoop/mapred-site.xml"
)

missing_configs=0
for config in "${HADOOP_CONFIGS[@]}"; do
    if [ ! -f "$config" ]; then
        echo -e "${RED}✗ Missing: $config${NC}"
        missing_configs=$((missing_configs + 1))
    else
        echo -e "${GREEN}✓ Found: $config${NC}"
    fi
done

if [ $missing_configs -gt 0 ]; then
    echo -e "${RED}Error: Missing $missing_configs Hadoop configuration file(s)!${NC}"
    exit 1
fi


echo ""
echo -e "${GREEN}[Step 5/5] Starting services with Docker Compose...${NC}"
echo ""

# Start docker compose
docker compose up -d

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Services are starting up. You can check their status with:"
echo -e "${YELLOW}  docker compose ps${NC}"
echo ""
echo "To view logs:"
echo -e "${YELLOW}  docker compose logs -f [service_name]${NC}"
echo ""
echo "Available services (using network_mode: host):"
echo "  - Kafka Broker:    localhost:9092"
echo "  - Kafka Controller: localhost:9093"
echo "  - HDFS NameNode UI: localhost:9870"
echo "  - HDFS NameNode RPC: localhost:8020"
echo "  - YARN ResourceManager UI: localhost:8088"
echo "  - Redis:           localhost:6379"
echo "  - Airflow Web UI:  localhost:8080"
echo ""
echo "Available services (using bridge network):"
echo "  - PostgreSQL:      localhost:45432"
echo "  - pgAdmin:         localhost:46016"
echo ""
