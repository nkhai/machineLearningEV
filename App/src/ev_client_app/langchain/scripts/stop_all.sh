#!/bin/bash
# stop_all.sh

echo "======================================"
echo "Initiating Emergency Stop for all EVs..."
echo "======================================"

# Kill shell script launch processes
pkill -f "start_EV_" 2>/dev/null

# Kill Python/Uvicorn processes running vehicle simulation
pkill -f "uvicorn app:app" 2>/dev/null

# Delete old log files to prepare for next run (Optional, you can remove this line if you want to keep logs)
# rm -f logs/EV_*.log

echo "======================================"
echo "All EV processes have been gracefully stopped!"
echo "======================================"