#!/bin/bash
# start_system.sh — SmartAttend full system launcher
# Run from project root: ./start_system.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS="$ROOT/logs"
PYTHON="$(which python3)"

mkdir -p "$LOGS"

echo "======================================================"
echo "  SmartAttend — Starting All Services"
echo "  Root: $ROOT"
echo "======================================================"

# ── Kill anything already on these ports ──────────────────────────────────────
echo ""
echo "[1/6] Clearing ports 5000 5001 5002 5003 8001 8002..."
for port in 5000 5001 5002 5003 8001 8002; do
    pids=$(lsof -t -i:"$port" 2>/dev/null)
    if [ -n "$pids" ]; then
        kill -9 $pids 2>/dev/null
        echo "      Killed PID(s) $pids on port $port"
    fi
done
sleep 1

# ── Node Backend (port 5000) ───────────────────────────────────────────────────
echo ""
echo "[2/6] Starting Node backend (port 5000)..."
cd "$ROOT/backend"
nohup node server.js > "$LOGS/backend.log" 2>&1 &
echo "      PID=$!  |  tail -f logs/backend.log"
sleep 2

# ── Face Service (port 5001) ───────────────────────────────────────────────────
echo ""
echo "[3/6] Starting Face service (port 5001)..."
cd "$ROOT/face-service"
nohup "$PYTHON" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 5001 \
    > "$LOGS/face.log" 2>&1 &
echo "      PID=$!  |  tail -f logs/face.log"
sleep 3   # face service loads ML models — needs more time

# ── QR Service (port 5002) ────────────────────────────────────────────────────
echo ""
echo "[4/6] Starting QR service (port 5002)..."
cd "$ROOT/qr-service"
nohup "$PYTHON" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 5002 \
    > "$LOGS/qr.log" 2>&1 &
echo "      PID=$!  |  tail -f logs/qr.log"
sleep 1

# ── Attendance Service (port 5003) ────────────────────────────────────────────
echo ""
echo "[5/6] Starting Attendance service (port 5003)..."
cd "$ROOT/attendance-service"
nohup "$PYTHON" -m uvicorn app.main:app \
    --host 0.0.0.0 --port 5003 \
    > "$LOGS/attendance.log" 2>&1 &
echo "      PID=$!  |  tail -f logs/attendance.log"
sleep 1

# ── Frontends (ports 8001, 8002) ──────────────────────────────────────────────
echo ""
echo "[6/6] Starting frontends (ports 8001, 8002)..."
cd "$ROOT"

nohup npx --yes http-server frontend-student \
    -p 8001 -a 0.0.0.0 --cors \
    > "$LOGS/frontend-student.log" 2>&1 &
echo "      Student PID=$!  |  tail -f logs/frontend-student.log"

sleep 1

nohup npx --yes http-server frontend-instructor \
    -p 8002 -a 0.0.0.0 --cors \
    > "$LOGS/frontend-instructor.log" 2>&1 &
echo "      Instructor PID=$!  |  tail -f logs/frontend-instructor.log"

# ── Wait for everything to settle, then verify ───────────────────────────────
sleep 4

echo ""
echo "======================================================"
echo "  Status Check"
echo "======================================================"

all_ok=true
check() {
    local port=$1
    local name=$2
    if lsof -t -i:"$port" > /dev/null 2>&1; then
        echo "  [OK]   $name  →  port $port"
    else
        echo "  [FAIL] $name  →  port $port NOT running"
        all_ok=false
    fi
}

check 5000 "Node Backend       "
check 5001 "Face Service       "
check 5002 "QR Service         "
check 5003 "Attendance Service "
check 8001 "Frontend (Student) "
check 8002 "Frontend (Instructor)"

LAN_IP=$(hostname -I 2>/dev/null | awk '{print $1}')

echo ""
echo "======================================================"
echo "  Access URLs"
echo "======================================================"
echo "  Student Portal:    http://${LAN_IP}:8001"
echo "  Instructor Portal: http://${LAN_IP}:8002"
echo "  Backend API:       http://${LAN_IP}:5000"
echo "  Face API:          http://${LAN_IP}:5001/health"
echo "  QR API:            http://${LAN_IP}:5002/health"
echo "  Attendance API:    http://${LAN_IP}:5003/health"
echo ""
echo "  Logs: $LOGS/"
echo "======================================================"

if [ "$all_ok" = false ]; then
    echo ""
    echo "  Some services failed. Check logs above for errors."
    echo "  Tip: tail -f logs/<service>.log"
fi
