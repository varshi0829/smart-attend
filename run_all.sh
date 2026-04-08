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
echo "✅ System ready!"
echo "👨‍🏫 Instructor: http://$SMARTATTEND_LAN_IP:8002"
echo "🎓 Student:    http://$SMARTATTEND_LAN_IP:8001"
echo "------------------------------------------"
