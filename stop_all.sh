#!/bin/bash

echo "🛑 Stopping SmartAttend services..."

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
pkill -f "uvicorn" > /dev/null 2>&1
pkill -f "http-server" > /dev/null 2>&1

echo "✅ All services stopped."
