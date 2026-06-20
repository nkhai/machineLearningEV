#!/bin/bash
# Script to auto-generate 10 files start_EV101.sh -> start_EV110.sh

for i in {1..10}; do
    NUM=$(printf "%02d" $i)
    CAR_ID="EV_1${NUM}"
    # Auto-vary the VIN suffix slightly for each vehicle
    VIN="1HGCM82633A0043${NUM}"
    FILE_NAME="start_${CAR_ID}.sh"

    cat <<EOF > "$FILE_NAME"
#!/bin/bash
# =========================
# EV STATIC CONFIG
# =========================
CAR_ID="$CAR_ID"
CAR_MODEL="VF8-1"
VIN="$VIN"
 
# =========================
# Network configuration
# =========================
BACKEND_BASE=8001
 
PORT=\$BACKEND_BASE
while lsof -i:\$PORT >/dev/null 2>&1; do
  PORT=\$((PORT+1))
  if [ \$PORT -eq 8005 ] || [ \$PORT -eq 8050 ]; then
    PORT=\$((PORT+1))
  fi
done
 
BACKEND_PORT=\$PORT
 
echo "=============================="
echo "Starting LangChain EV Backend..."
echo "Backend Port:  \$BACKEND_PORT"
echo "Car ID:        \$CAR_ID"
echo "Car Model:     \$CAR_MODEL"
echo "VIN:           \$VIN"
echo "=============================="
 
# =========================
# Start Backend
# =========================
cd .. || { echo "Cannot cd to parent folder"; exit 1; }
 
export EV_ID=\$CAR_ID
export CAR_MODEL=\$CAR_MODEL
export VIN=\$VIN
export BACKEND_PORT=\$BACKEND_PORT
 
uvicorn app:app --host 0.0.0.0 --port \$BACKEND_PORT --reload &
BACKEND_PID=\$!
 
# =========================
# Trap Ctrl+C to stop backend
# =========================
trap "echo '[INFO] Stopping LangChain EV backend...'; \\
      kill -TERM \$BACKEND_PID; \\
      exit" SIGINT SIGTERM
 
# =========================
# Show URL
# =========================
BACKEND_URL="http://localhost:\$BACKEND_PORT/api/history"
 
echo "=============================="
echo "Backend running at: \$BACKEND_URL"
echo "=============================="
 
# =========================
# Wait for backend
# =========================
wait \$BACKEND_PID
EOF

    chmod +x "$FILE_NAME"
    echo "Generated $FILE_NAME"
done