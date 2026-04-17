#!/bin/bash

# Navigate to project root
cd "$(dirname "$0")" || exit 1

# Set LAN IP for remote access
export SMARTATTEND_LAN_IP="$(hostname -I | awk '{print $1}')"

echo "------------------------------------------"
echo "🚀 Starting SmartAttend System..."
echo "------------------------------------------"
echo ""

# Ensure clean state by stopping any existing instances first
./stop_all.sh > /dev/null 2>&1

# Start backend services quietly
./start_services.sh > /dev/null 2>&1 &

# Start frontends quietly
./start_frontends.sh > /dev/null 2>&1 &

# ── Embedding verification ─────────────────────────────────────────────────────
echo "[CHECK] Verifying embeddings..."
cd ~/smart-attend/face-service || exit 1

VERIFY_OUT=$(./venv/bin/python3 bulk_register.py --verify 2>&1)
VERIFY_STATUS=$?

echo "$VERIFY_OUT"

if [ $VERIFY_STATUS -ne 0 ]; then
    echo ""
    echo "⚠️  System may not work correctly — fix the above before demo."
fi

cd ~/smart-attend || exit 1

# ── Service health checks (with retry) ────────────────────────────────────────
echo ""
echo "[CHECK] Service health..."

_check_service() {
    local label="$1"
    local url="$2"
    local port="$3"

    for attempt in 1 2 3 4 5; do
        if curl -sk --max-time 3 "$url" 2>/dev/null | grep -q '"status"'; then
            echo "✅ $label OK"
            return 0
        fi
        sleep 3
    done

    echo "❌ $label failed to start on port $port"
    echo "   Reason: no response after 5 attempts — check logs/${label,,}-service.log"
    return 1
}

_check_service "Face-service"       "https://127.0.0.1:5001/health" "5001"
_check_service "QR-service"         "https://127.0.0.1:5002/health" "5002"
_check_service "Attendance-service" "https://127.0.0.1:5003/health" "5003"

echo ""
echo "------------------------------------------"
echo "✅ System ready!"
echo "   👨‍🏫 Instructor: https://$SMARTATTEND_LAN_IP:8000/instructor"
echo "   🎓 Student:    https://$SMARTATTEND_LAN_IP:8000/"
echo "------------------------------------------"
