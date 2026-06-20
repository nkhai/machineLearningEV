#!/bin/bash
# start_all.sh

# Create log directory if it doesn't exist
mkdir -p logs

echo "======================================"
echo "Initializing Fleet of 10 EV Agents (Sequential Safe-Boot)..."
echo "======================================"

for i in {1..11}; do
    # Skip EV_105 as agreed
    if [ "$i" -eq 5 ]; then
        echo "[$i/11] Skipping EV_105..."
        continue
    fi

    NUM=$(printf "%02d" $i)
    CAR="EV_1${NUM}"
    
    echo "--------------------------------------"
    echo "[$i/11] Starting $CAR in background..."
    
    # Activate vehicle
    nohup ./scripts/start_${CAR}.sh > logs/${CAR}.log 2>&1 &
    
    echo " -> Waiting for $CAR to fully boot up..."
    
    # Loop waiting for successful startup signal (Max 45 seconds/vehicle to prevent script hangs)
    TIMEOUT=45
    ELAPSED=0
    while ! grep -q "Application startup complete" logs/${CAR}.log; do
        sleep 1
        ELAPSED=$((ELAPSED+1))
        
        # If 45 seconds pass without seeing successful log, warn and proceed
        if [ $ELAPSED -ge $TIMEOUT ]; then
            echo " -> [WARNING] $CAR took too long to start. Proceeding anyway..."
            break
        fi
    done
    
    # If loop ends before timeout means boot was successful
    if [ $ELAPSED -lt $TIMEOUT ]; then
        echo " -> [SUCCESS] $CAR is up and running!"
    fi

    echo " -> Waiting 3 seconds before releasing the next car..."
    sleep 3
done

echo "======================================"
echo "All EVs have been dispatched!"
echo "Use 'tail -f logs/EV_101.log' to monitor."
echo "======================================"