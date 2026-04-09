#!/bin/bash

# Navigate to project root
cd "$(dirname "$0")" || exit 1

# Set LAN IP for remote access
export SMARTATTEND_LAN_IP="$(hostname -I | awk '{print $1}')"

echo "------------------------------------------"
echo "🚀 Starting SmartAttend System..."
echo "📍 LAN IP: $SMARTATTEND_LAN_IP"
echo "------------------------------------------"

# Ensure clean state by stopping any existing instances first
./stop_all.sh > /dev/null 2>&1

echo "📦 Starting Backend Services (Ports: 5001, 5002, 5003)..."
./start_services.sh &

# Wait for backend models and sockets to initialize
sleep 5

echo "🌐 Starting Frontends (Ports: 8001, 8002)..."
./start_frontends.sh

echo "------------------------------------------"
echo "🔍 Running Face-Service Verification..."
echo "------------------------------------------"

cd ~/smart-attend/face-service || exit 1

# Verify embeddings
echo "[CHECK] Verifying embeddings..."
./venv/bin/python3 bulk_register.py --verify
VERIFY_STATUS=$?

if [ $VERIFY_STATUS -ne 0 ]; then
    echo "❌ Embedding verification failed!"
    echo "⚠️ System may not work correctly."
    exit 1
fi
echo "✅ Embeddings verified successfully."

# Print config
echo "[CHECK] Config values..."
./venv/bin/python3 -c "
from app import config
print('DB_ENABLED =', config.DB_ENABLED)
print('THRESHOLD =', config.THRESHOLD)
"

cd ~/smart-attend || exit 1

# Health checks
echo "[CHECK] Service health..."

curl -k https://127.0.0.1:5001/health || echo "❌ Face-service failed"
curl -k https://127.0.0.1:5002/health || echo "❌ QR-service failed"
curl -k https://127.0.0.1:5003/health || echo "❌ Attendance-service failed"

echo "[CHECK] Recent face-service logs:"
tail -n 10 ~/smart-attend/logs/face-service.log 2>/dev/null || echo "No logs found"

echo "------------------------------------------"
echo "✅ System ready!"
echo "👨‍🏫 Instructor: http://$SMARTATTEND_LAN_IP:8002"
echo "🎓 Student:    http://$SMARTATTEND_LAN_IP:8001"
echo "------------------------------------------"
