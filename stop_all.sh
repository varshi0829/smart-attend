#!/bin/bash

echo "------------------------------------------"
echo "🛑 Stopping SmartAttend Services..."
echo "------------------------------------------"

# Ports to target
PORTS=(5001 5002 5003 8001 8002)

for PORT in "${PORTS[@]}"; do
    PIDS=$(lsof -t -i:$PORT)
    if [ -n "$PIDS" ]; then
        echo "Stopping processes on port $PORT..."
        # Attempt graceful termination first
        kill $PIDS 2>/dev/null
        sleep 1
        # Force kill any remaining processes
        kill -9 $PIDS 2>/dev/null
    fi
done

# Cleanup any remaining uvicorn or http-server orphans
pkill -f "uvicorn app.main:app" || true
pkill -f "http-server" || true

echo "[OK] All services stopped."
