# =========================
# EV STATIC CONFIG 
# =========================
CAR_ID=EV_008
CAR_NAME="MODEL 1"
VIN="SALWR2KF5FA123456"

# =========================
# Network configuration
# =========================
BACKEND_BASE=8008
FRONTEND_OFFSET=1000

PORT=$BACKEND_BASE
while lsof -i:$PORT >/dev/null 2>&1; do
  PORT=$((PORT+1))
done

BACKEND_PORT=$PORT
FRONTEND_PORT=$((BACKEND_PORT + FRONTEND_OFFSET))

echo "=============================="
echo "Starting EV instance..."
echo "Backend Port:  $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo "Car ID:        $CAR_ID"
echo "Car Name:      $CAR_NAME"
echo "VIN:           $VIN"
echo "=============================="

# =========================
# Start Backend 
# =========================
cd .. || { echo "Cannot cd to kafka folder"; exit 1; }

export EV_ID=$CAR_ID
export CAR_NAME=$CAR_NAME
export VIN=$VIN
export BACKEND_PORT=$BACKEND_PORT

setsid uvicorn main:app --host 0.0.0.0 --port $BACKEND_PORT --reload &
BACKEND_PID=$!

cd startEV

# =========================
# Start Frontend 
# =========================
UI_DIR="../../plotlydash"
cd $UI_DIR || { echo "Cannot cd $UI_DIR"; exit 1; }

setsid python3 user.py \
    --port $FRONTEND_PORT \
    --car_id $CAR_ID \
    --car_name "$CAR_NAME" \
    --vin "$VIN" &
FRONTEND_PID=$!

cd - >/dev/null

# =========================
# Trap Ctrl+C to stop everything
# =========================
trap "echo '[INFO] Stopping EV instance...'; \
      kill -TERM -- -$BACKEND_PID; \
      kill -TERM -- -$FRONTEND_PID; \
      exit" SIGINT SIGTERM

# =========================
# Open browser
# =========================
FRONTEND_URL="http://localhost:$FRONTEND_PORT"

echo "=============================="
echo "EV UI running at: $FRONTEND_URL"
echo "=============================="

if grep -qi microsoft /proc/version; then
    cmd.exe /C start "" "$FRONTEND_URL"
elif command -v xdg-open >/dev/null; then
    xdg-open "$FRONTEND_URL"
elif command -v open >/dev/null; then
    open "$FRONTEND_URL"
fi

# =========================
# Wait for backend and frontend
# =========================
wait $BACKEND_PID $FRONTEND_PID