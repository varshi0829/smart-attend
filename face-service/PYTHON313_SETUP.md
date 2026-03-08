# Python 3.13 Compatible Face Recognition Setup

## Solution: DeepFace with Facenet

DeepFace works with Python 3.13 and provides real face recognition using Facenet model.

---

## Complete Setup Commands

```bash
# 1. Navigate to face-service
cd /home/cse/smart-attend/face-service

# 2. Remove old venv if exists
rm -rf venv

# 3. Create new venv with Python 3.13
python3 -m venv venv

# 4. Activate venv
source venv/bin/activate

# 5. Upgrade pip
pip install --upgrade pip

# 6. Install dependencies (takes 2-3 minutes)
pip install -r requirements.txt

# 7. Start Flask service
python app.py
```

**Expected output:**
```
 * Running on http://0.0.0.0:5001
```

---

## Test with Real Photos

### 1. Register Face
```bash
# Convert photo to base64
base64 -w 0 your_photo.jpg > photo.txt

# Register
curl -X POST http://localhost:5001/face/register \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"TEST_STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat photo.txt)\"
  }"
```

**Expected:**
```json
{
  "success": true,
  "message": "Face registered successfully",
  "studentId": "TEST_STUDENT_ID"
}
```

### 2. Verify Same Face (Should Pass)
```bash
curl -X POST http://localhost:5001/face/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"TEST_STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat photo.txt)\"
  }"
```

**Expected:**
```json
{
  "verified": true,
  "confidence": 0.95
}
```

### 3. Verify Different Face (Should Fail)
```bash
# Use different person's photo
base64 -w 0 other_person.jpg > other.txt

curl -X POST http://localhost:5001/face/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"studentId\": \"TEST_STUDENT_ID\",
    \"faceImage\": \"data:image/jpeg;base64,$(cat other.txt)\"
  }"
```

**Expected:**
```json
{
  "verified": false,
  "confidence": 0.35
}
```

---

## What Changed

### Library: DeepFace
- **Compatible:** Python 3.13 ✓
- **Model:** Facenet (128-dimensional embeddings)
- **Detection:** Automatic face detection
- **Matching:** Cosine similarity with 0.6 threshold

### Advantages
- Works on Python 3.13
- No compilation needed (unlike dlib)
- Fast installation
- Production-ready accuracy

---

## Troubleshooting

### Error: "No face detected in image"
- Ensure face is clearly visible
- Good lighting required
- Face should be front-facing
- Try different photo

### Slow first request
- First request downloads Facenet model (~100MB)
- Subsequent requests are fast
- Model cached in `~/.deepface/weights/`

### Installation issues
```bash
# If opencv fails, install system dependencies
sudo apt-get update
sudo apt-get install -y libgl1-mesa-glx libglib2.0-0

# Reinstall
pip install --no-cache-dir -r requirements.txt
```

---

## Performance

- **Registration:** 2-3 seconds (first time downloads model)
- **Verification:** 1-2 seconds
- **Accuracy:** High (Facenet is industry-standard)

---

## Backend Integration

✅ **No changes needed!**

- Endpoints: Same
- Request format: Same
- Response format: Same
- Port: 5001

Your backend at `http://localhost:5000` will work without any modifications.

---

## Quick Start (Copy-Paste)

```bash
cd /home/cse/smart-attend/face-service
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Done! Service runs on port 5001 with real face recognition on Python 3.13.
