#!/bin/bash
# stop_system.sh — SmartAttend clean shutdown
# Run from project root: ./stop_system.sh

echo "======================================================"
echo "  SmartAttend — Stopping All Services"
echo "======================================================"

PORTS=(5000 5001 5002 5003 8001 8002)

for port in "${PORTS[@]}"; do
    pids=$(lsof -t -i:"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        kill -15 $pids 2>/dev/null   # graceful SIGTERM first
        sleep 0.5
        # force-kill anything still alive
        survivors=$(lsof -t -i:"$port" 2>/dev/null)
        if [ -n "$survivors" ]; then
            kill -9 $survivors 2>/dev/null
        fi
        echo "  [STOPPED] port $port"
    else
        echo "  [CLEAR]   port $port (nothing was running)"
    fi
done

# Clean up any orphaned processes by name (won't kill unrelated processes
# because we match specific command patterns)
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "  [KILLED] stray uvicorn processes" || true
pkill -f "http-server frontend-" 2>/dev/null && echo "  [KILLED] stray http-server processes" || true

echo ""
echo "  All services stopped."
echo "======================================================"
