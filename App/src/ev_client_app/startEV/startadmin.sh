#!/bin/bash

cd ..

# Thiết lập PYTHONPATH
export PYTHONPATH=$(pwd)

cleanup() {
    echo "Shutting down Admin backend and Dash UI..."
    if [[ ! -z "$BACKEND_PID" ]]; then
        kill $BACKEND_PID
    fi
    if [[ ! -z "$FRONTEND_PID" ]]; then
        kill $FRONTEND_PID
    fi
    exit 0
}

trap cleanup SIGINT

echo "Starting Admin backend on port 8050..."
uvicorn admin_main:app --host 0.0.0.0 --port 8050 --reload &
BACKEND_PID=$!

cd ../plotlydash

echo "Starting Admin frontend on port 9050..."
python3 admin.py &
FRONTEND_PID=$!

wait $BACKEND_PID
wait $FRONTEND_PID