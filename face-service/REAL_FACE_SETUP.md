# Real Face Recognition - Setup & Testing

## Install & Run

### 1. Install System Dependencies (Ubuntu/Debian)
```bash
sudo apt-get update
sudo apt-get install -y cmake libopenblas-dev liblapack-dev libx11-dev libgtk-3-dev
```

### 2. Install Python Dependencies
```bash
cd face-service
pip install -r requirements.txt
```

**Note:** Installation may take 5-10 minutes as it compiles dlib.

### 3. Start Flask Service
```bash
python app.py
```

Service runs on: http://localhost:5001

---

## What Changed

### Before (Weak)
- Simple byte comparison
- No actual face detection
- Unreliable matching

### After (Real)
- Uses `face_recognition` library (built on dlib)
- Detects faces in images
- Extracts 128-dimensional face encodings
- Compares using Euclidean distance
- Threshold: 0.4 confidence (0.6 distance)

---

## Manual Testing

### Test 1: Register Face with Real Photo
```bash
# Take a photo and convert to base64
base64 -w 0 your_photo.jpg > photo_base64.txt

# Register (replace STUDENT_ID)
curl -X POST http://localhost:5001/face/register \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat photo_base64.txt)\"
  }"
```

**Expected:**
```json
{
  "success": true,
  "message": "Face registered successfully",
  "studentId": "..."
}
```

**If no face detected:**
```json
{
  "error": "No face detected in image"
}
```

---

### Test 2: Verify with SAME Photo (Should Pass)
```bash
# Use same photo
curl -X POST http://localhost:5001/face/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat photo_base64.txt)\"
  }"
```

**Expected:**
```json
{
  "verified": true,
  "confidence": 0.85
}
```

---

### Test 3: Verify with DIFFERENT Person (Should Fail)
```bash
# Use different person's photo
base64 -w 0 other_person.jpg > other_base64.txt

curl -X POST http://localhost:5001/face/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat other_base64.txt)\"
  }"
```

**Expected:**
```json
{
  "verified": false,
  "confidence": 0.25
}
```

---

### Test 4: Verify with SAME Person, Different Angle (Should Pass)
```bash
# Take another photo of same person from different angle
base64 -w 0 your_photo2.jpg > photo2_base64.txt

curl -X POST http://localhost:5001/face/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat photo2_base64.txt)\"
  }"
```

**Expected:**
```json
{
  "verified": true,
  "confidence": 0.65
}
```

---

## Quick Photo Capture (Linux)

### Using Webcam
```bash
# Install fswebcam if needed
sudo apt-get install fswebcam

# Capture photo
fswebcam -r 640x480 --no-banner test_face.jpg

# Convert to base64
base64 -w 0 test_face.jpg > test_face_base64.txt
```

### Using Phone Camera
1. Take photo with phone
2. Transfer to computer
3. Convert: `base64 -w 0 photo.jpg > photo_base64.txt`

---

## Integration with Backend

**No changes needed!** Backend already sends:
```json
{
  "studentId": "...",
  "faceImage": "data:image/jpeg;base64,..."
}
```

Flask returns:
```json
{
  "verified": true/false,
  "confidence": 0.0-1.0
}
```

---

## Confidence Thresholds

| Confidence | Meaning |
|-----------|---------|
| 0.7 - 1.0 | Very high match (same person, similar conditions) |
| 0.4 - 0.7 | Good match (same person, different conditions) |
| 0.0 - 0.4 | No match (different person) |

**Current threshold:** 0.4 (balanced for MVP)

---

## Troubleshooting

### Error: "No face detected in image"
- Ensure face is clearly visible
- Good lighting
- Face not too small in frame
- Try different angle

### Error: dlib installation fails
```bash
# Install build tools
sudo apt-get install build-essential cmake
pip install dlib
pip install face-recognition
```

### Low confidence for same person
- Ensure consistent lighting
- Face should be front-facing
- Remove glasses/masks if possible
- Register with multiple angles

---

## Performance

- Registration: ~1-2 seconds per image
- Verification: ~1-2 seconds per image
- Suitable for college attendance (not high-frequency)

---

## Backend Integration Status

✅ Endpoints unchanged  
✅ Request format unchanged  
✅ Response format unchanged  
✅ Port 5001 unchanged  
✅ All Phase 1B rules preserved  

Just restart Flask service with new code!
