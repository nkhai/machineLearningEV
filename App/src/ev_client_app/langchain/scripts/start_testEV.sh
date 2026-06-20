#!/bin/bash
# =========================
# EV STATIC CONFIG
# =========================
CAR_ID="EV_066"
CAR_MODEL="SimuProB-066"
VIN="1HGCM82633A004366"
 
# =========================
# Network configuration
# =========================
BACKEND_BASE=8066
FRONTEND_OFFSET=1000 # Add offset for Frontend port
 
PORT=$BACKEND_BASE
while lsof -i:$PORT >/dev/null 2>&1; do
  PORT=$((PORT+1))
  if [ $PORT -eq 8005 ] || [ $PORT -eq 8050 ]; then
    PORT=$((PORT+1))
  fi
done
 
BACKEND_PORT=$PORT
FRONTEND_PORT=$((BACKEND_PORT + FRONTEND_OFFSET)) # Calculate Frontend port
 
echo "=============================="
echo "Starting LangChain EV Instance..."
echo "Backend Port:  $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo "Car ID:        $CAR_ID"
echo "Car Model:     $CAR_MODEL"
echo "VIN:           $VIN"
echo "=============================="
 
# =========================
# Start Backend
# =========================
export EV_ID=$CAR_ID
export CAR_MODEL=$CAR_MODEL
export VIN=$VIN
export BACKEND_PORT=$BACKEND_PORT
 
# Use setsid to group processes, ensuring clean Uvicorn shutdown when using kill
setsid uvicorn app:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
BACKEND_PID=$!

# =========================
# Start Frontend
# =========================
CURRENT_DIR=$(pwd)
UI_DIR="../../plotlydash"
cd $UI_DIR || { echo "Cannot cd $UI_DIR"; exit 1; }

setsid python3 user.py \
    --port $FRONTEND_PORT \
    --car_id $CAR_ID \
    --car_name "$CAR_MODEL" \
    --vin "$VIN" &
FRONTEND_PID=$!

# Return to the script's root directory
cd "$CURRENT_DIR" >/dev/null
 
# =========================
# Trap Ctrl+C to stop everything
# =========================
# Kill via Process Group (-- -$PID) to clean up all child processes spawned
trap "echo '[INFO] Stopping LangChain EV instance...'; \
      kill -TERM -- -$BACKEND_PID; \
      kill -TERM -- -$FRONTEND_PID; \
      exit" SIGINT SIGTERM
 
# =========================
# Show URLs & Open Browser
# =========================
BACKEND_URL="http://localhost:$BACKEND_PORT/api/history"
FRONTEND_URL="http://localhost:$FRONTEND_PORT"
 
echo "=============================="
echo "Backend running at:  $BACKEND_URL"
echo "Frontend running at: $FRONTEND_URL"
echo "=============================="

# Auto-open browser
if grep -qi microsoft /proc/version; then
    cmd.exe /C start "" "$FRONTEND_URL"
elif command -v xdg-open >/dev/null; then
    xdg-open "$FRONTEND_URL"
elif command -v open >/dev/null; then
    open "$FRONTEND_URL"
fi
 
# =========================
# Wait for backend & frontend
# =========================
wait $BACKEND_PID $FRONTEND_PID