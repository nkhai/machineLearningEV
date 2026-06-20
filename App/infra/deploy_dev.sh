#!/bin/bash

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Airflow Development Deployment${NC}"
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

# Create required directories for Airflow
echo -e "${GREEN}[Step 1/4] Creating Airflow data directories...${NC}"
echo ""

# PostgreSQL directory
mkdir -p "$DATA_ROOT_PATH/postgres"
echo -e "✓ Created: ${GREEN}$DATA_ROOT_PATH/postgres${NC}"

# Airflow directories
mkdir -p "$DATA_ROOT_PATH/airflow/logs"
mkdir -p "$DATA_ROOT_PATH/airflow/config"
echo -e "✓ Created: ${GREEN}$DATA_ROOT_PATH/airflow/logs${NC}"
echo -e "✓ Created: ${GREEN}$DATA_ROOT_PATH/airflow/config${NC}"

echo ""

# Set permissions
echo -e "${GREEN}[Step 2/4] Setting permissions...${NC}"
echo ""

echo "Setting permissions for Airflow directories..."
if [ -w "$DATA_ROOT_PATH/airflow" ]; then
    chmod -R 777 "$DATA_ROOT_PATH/airflow" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
else
    echo "Trying with sudo..."
    sudo chmod -R 777 "$DATA_ROOT_PATH/airflow" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
fi

if [ -w "$DATA_ROOT_PATH/postgres" ]; then
    chmod -R 777 "$DATA_ROOT_PATH/postgres" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
else
    echo "Trying with sudo..."
    sudo chmod -R 777 "$DATA_ROOT_PATH/postgres" 2>/dev/null || echo -e "${YELLOW}⚠ Some permissions could not be set${NC}"
fi

echo -e "${GREEN}✓ Permissions updated (skipped locked files)${NC}"
echo ""

# Build Airflow custom image
echo -e "${GREEN}[Step 3/4] Building Airflow custom image...${NC}"
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

# Start Airflow services
echo -e "${GREEN}[Step 4/4] Starting Airflow services...${NC}"
echo ""

# Stop existing Airflow services if running
echo "Stopping existing Airflow services (if any)..."
docker compose stop postgres redis airflow-init airflow-apiserver airflow-scheduler airflow-dag-processor airflow-worker airflow-triggerer pgadmin 2>/dev/null || true

echo ""
echo "Starting Airflow services..."
docker compose up -d postgres redis pgadmin

echo "Waiting for database to be ready..."
sleep 5

docker compose up -d airflow-init

echo "Waiting for Airflow initialization..."
sleep 10

docker compose up -d airflow-apiserver airflow-scheduler airflow-dag-processor airflow-worker airflow-triggerer

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Deployment completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Airflow services are starting up. You can check their status with:"
echo -e "${YELLOW}  docker compose ps${NC}"
echo ""
echo "To view logs:"
echo -e "${YELLOW}  docker compose logs -f airflow-scheduler${NC}"
echo -e "${YELLOW}  docker compose logs -f airflow-worker${NC}"
echo ""
echo "Available services:"
echo "  - PostgreSQL:      localhost:45432"
echo "  - pgAdmin:         http://localhost:46016"
echo "  - Redis:           localhost:6379"
echo "  - Airflow Web UI:  http://localhost:8080 (airflow/airflow)"
echo ""
