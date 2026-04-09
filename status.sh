#!/bin/bash

echo "Checking SmartAttend services..."

ss -tulnp | grep 5001 > /dev/null && echo "✅ Face-service running" || echo "❌ Face-service NOT running"
ss -tulnp | grep 5002 > /dev/null && echo "✅ QR-service running" || echo "❌ QR-service NOT running"
ss -tulnp | grep 5003 > /dev/null && echo "✅ Attendance-service running" || echo "❌ Attendance-service NOT running"
ss -tulnp | grep 8001 > /dev/null && echo "✅ Student frontend running" || echo "❌ Student frontend NOT running"
ss -tulnp | grep 8002 > /dev/null && echo "✅ Instructor frontend running" || echo "❌ Instructor frontend NOT running"
