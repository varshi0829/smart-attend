#!/usr/bin/env bash
# ==============================================================================
# SmartAttend: Automated Service Manager
# This script handles LAN IP detection, SSL certificate rotation, 
# and service orchestration (Face, QR, and Attendance services).
# ==============================================================================

set -euo pipefail

# --- Configuration ---
ROOT_DIR="/home/cse/smart-attend"
KEY_FILE="$ROOT_DIR/key.pem"
CERT_FILE="$ROOT_DIR/cert.pem"
LOG_DIR="$ROOT_DIR/logs"

# Service Definitions: "Name | Directory | Port"
SERVICES=(
    "Face Service|face-service|5001"
    "QR Service|qr-service|5002"
    "Attendance Service|attendance-service|5003"
    "Gateway Service|gateway-service|8000"
)

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# --- 1. Detect Current LAN IP ---
# Grabs the primary local IP address
LAN_IP=$(hostname -I | awk '{print $1}')

if [[ -z "$LAN_IP" ]]; then
    echo "❌ Error: Could not detect LAN IP. Are you connected to a network?"
    exit 1
fi

echo "📡 Detected LAN IP: $LAN_IP"

# --- 2. Check & Handle SSL Certificates ---
REGENERATE_SSL=false

if [[ ! -f "$CERT_FILE" || ! -f "$KEY_FILE" ]]; then
    echo "🔑 SSL files missing."
    REGENERATE_SSL=true
else
    # Check if the current LAN IP is present in the existing certificate's Subject Alternative Names (SAN)
    # This prevents the "IP changed" camera error on mobile devices
    if ! openssl x509 -in "$CERT_FILE" -text -noout | grep -q "IP Address:$LAN_IP"; then
        echo "🔄 LAN IP changed or missing in certificate."
        REGENERATE_SSL=true
    fi
fi

if [ "$REGENERATE_SSL" = true ]; then
    echo "🛠️ Regenerating SSL certificate for IP: $LAN_IP..."
    rm -f "$KEY_FILE" "$CERT_FILE"
    
    openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
      -keyout "$KEY_FILE" -out "$CERT_FILE" \
      -subj "/CN=${LAN_IP}" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1,IP:${LAN_IP}" \
      2>/dev/null
      
    echo "✅ SSL Certificate updated successfully."
else
    echo "✅ Existing SSL certificate is valid for $LAN_IP."
fi

# --- 3. Stop Existing Services ---
echo "🛑 Stopping any previously running uvicorn processes..."
# This kills any process listening on our specific service ports
fuser -k 5001/tcp 5002/tcp 5003/tcp 8000/tcp 2>/dev/null || true
sleep 1

# --- 4. Start Services ---
echo "🚀 Starting services..."

for service_info in "${SERVICES[@]}"; do
    IFS="|" read -r NAME DIR PORT <<< "$service_info"
    
    echo "   ▶️ Starting $NAME on port $PORT..."
    
    (
        cd "$ROOT_DIR/$DIR"
        
        # Determine Python execution (Check for virtual environment)
        PYTHON_CMD="python3"
        if [[ -f "./venv/bin/python3" ]]; then
            PYTHON_CMD="./venv/bin/python3"
        fi
        
        # Start uvicorn in the background
        nohup $PYTHON_CMD -m uvicorn app.main:app \
            --host 0.0.0.0 \
            --port "$PORT" \
            --ssl-keyfile "$KEY_FILE" \
            --ssl-certfile "$CERT_FILE" \
            > "$LOG_DIR/${DIR}.log" 2>&1 &
    )
done

# --- 5. Print Summary ---
echo "===================================================="
echo "✨ All services have been started!"
echo "----------------------------------------------------"
echo "STUDENT APP:    https://$LAN_IP:8000/"
echo "INSTRUCTOR APP: https://$LAN_IP:8000/instructor"
echo "----------------------------------------------------"
echo "Logs are available in: $LOG_DIR"
echo "===================================================="
