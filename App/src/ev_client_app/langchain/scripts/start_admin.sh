#!/bin/bash

# 1. Save current directory
CURRENT_DIR=$(pwd)

# 2. Set PYTHONPATH
export PYTHONPATH="$CURRENT_DIR:$CURRENT_DIR/.."

# ==========================================
# 3. FIX DATABASE ERROR: Read .env file from infra directory
# ==========================================
ENV_PATH="../../../infra/.env"
if [ -f "$ENV_PATH" ]; then
    echo "[INFO] Found and loaded config from $ENV_PATH"
    set -a
    source "$ENV_PATH"
    set +a
else
    echo "[ERROR] .env file not found at $ENV_PATH!"
    exit 1
fi
# ==========================================

# 4. Cleanup function
cleanup() {
    echo ""
    echo "[INFO] Shutting down Admin server..."
    if [[ ! -z "$BACKEND_PID" ]]; then
        kill -TERM -- -$BACKEND_PID 2>/dev/null
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "=============================="
echo "Starting Admin Instance..."
echo "Admin Server Port:  9050"
echo "=============================="

# ==========================================
# 5. CLEAN UP OLD PROCESSES (ANTI-ZOMBIE)
# ==========================================
echo "[INFO] Checking for existing processes on port 9050..."
fuser -k 9050/tcp 2>/dev/null
sleep 1 

# 6. Switch to plotlydash directory to run admin_server.py
cd ../../plotlydash || { echo "Cannot cd to plotlydash folder"; exit 1; }

echo "Starting Admin server on port 9050..."
PYTHONPATH="$CURRENT_DIR:$CURRENT_DIR/.." setsid uvicorn admin_server:app --host 0.0.0.0 --port 9050 &
BACKEND_PID=$!

# 7. Auto-open browser
FRONTEND_URL="http://localhost:9050"
echo "=============================="
echo "Admin UI running at: $FRONTEND_URL"
echo "=============================="

if grep -qi microsoft /proc/version; then
    cmd.exe /C start "" "$FRONTEND_URL" 2>/dev/null
elif command -v xdg-open >/dev/null; then
    xdg-open "$FRONTEND_URL"
elif command -v open >/dev/null; then
    open "$FRONTEND_URL"
fi

# Wait for process to run
wait $BACKEND_PID