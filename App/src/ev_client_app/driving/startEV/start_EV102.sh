# =========================
# EV STATIC CONFIG
# =========================
CAR_ID=EV_102
CAR_MODEL="VF8-1"
VIN="1HGCM82633A004353"
 
# =========================
# Network configuration
# =========================
BACKEND_BASE=8002
 
PORT=$BACKEND_BASE
while lsof -i:$PORT >/dev/null 2>&1; do
  PORT=$((PORT+1))
done
 
BACKEND_PORT=$PORT
 
echo "=============================="
echo "Starting EV Backend..."
echo "Backend Port:  $BACKEND_PORT"
echo "Car ID:        $CAR_ID"
echo "Car Model:     $CAR_MODEL"
echo "VIN:           $VIN"
echo "=============================="
 
# =========================
# Start Backend
# =========================
cd .. || { echo "Cannot cd to kafka folder"; exit 1; }
 
export EV_ID=$CAR_ID
export CAR_MODEL=$CAR_MODEL
export VIN=$VIN
export BACKEND_PORT=$BACKEND_PORT
 
uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
BACKEND_PID=$!
 
# =========================
# Trap Ctrl+C to stop backend
# =========================
trap "echo '[INFO] Stopping EV backend...'; \
      kill -TERM $BACKEND_PID; \
      exit" SIGINT SIGTERM
 
# =========================
# Show URL
# =========================
BACKEND_URL="http://localhost:$BACKEND_PORT/api/history"
 
echo "=============================="
echo "Backend running at: $BACKEND_URL"
echo "=============================="
 
# =========================
# Wait for backend
# =========================
wait $BACKEND_PID
