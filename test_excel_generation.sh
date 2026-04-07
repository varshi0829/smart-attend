#!/bin/bash
# Test Excel Generation After Session End

echo "=== Excel Generation Test ==="
echo ""

# Configuration
INSTRUCTOR_ID="INST_001"
CLASS_NAME="CSE-A"
QR_API="https://127.0.0.1:5002"
ATTENDANCE_API="https://127.0.0.1:5003"

echo "Step 1: Starting session..."
START_RESPONSE=$(curl -sk -X POST "$QR_API/session/start" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\",\"class_name\":\"$CLASS_NAME\"}")

SESSION_ID=$(echo $START_RESPONSE | grep -o '"session_id":"[^"]*' | cut -d'"' -f4)

if [ -z "$SESSION_ID" ]; then
  echo "❌ Failed to start session"
  echo "Response: $START_RESPONSE"
  exit 1
fi

echo "✅ Session started: $SESSION_ID"
echo ""

echo "Step 2: Waiting 3 seconds..."
sleep 3
echo ""

echo "Step 3: Stopping session (should trigger Excel)..."
STOP_RESPONSE=$(curl -sk -X POST "$QR_API/session/stop" \
  -H "Content-Type: application/json" \
  -d "{\"instructor_id\":\"$INSTRUCTOR_ID\"}")

echo "Response: $STOP_RESPONSE"
echo ""

echo "Step 4: Waiting 5 seconds for Excel generation..."
sleep 5
echo ""

echo "Step 5: Checking if Excel file exists..."
REPORTS_DIR="./attendance-service/reports"
SESSION_PREFIX="${SESSION_ID:0:8}"

if ls $REPORTS_DIR/*$SESSION_PREFIX*.xlsx 1> /dev/null 2>&1; then
  echo "✅ Excel file found:"
  ls -lh $REPORTS_DIR/*$SESSION_PREFIX*.xlsx
else
  echo "❌ Excel file NOT found in $REPORTS_DIR"
  echo "Files in reports directory:"
  ls -lh $REPORTS_DIR/ 2>/dev/null || echo "Directory doesn't exist"
fi
echo ""

echo "Step 6: Testing download endpoint..."
curl -sk "$ATTENDANCE_API/attendance/session/$SESSION_ID/download-report" \
  -o "test_download.xlsx"

if [ -f "test_download.xlsx" ]; then
  SIZE=$(stat -f%z "test_download.xlsx" 2>/dev/null || stat -c%s "test_download.xlsx" 2>/dev/null)
  if [ "$SIZE" -gt 1000 ]; then
    echo "✅ Download successful (${SIZE} bytes)"
    rm test_download.xlsx
  else
    echo "❌ Downloaded file too small (${SIZE} bytes)"
  fi
else
  echo "❌ Download failed"
fi
echo ""

echo "=== Test Complete ==="
echo ""
echo "Check logs:"
echo "  tail -f logs/qr-service.log"
echo "  tail -f logs/attendance-service.log"
