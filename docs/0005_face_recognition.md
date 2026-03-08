# Face Recognition Module
# Kaggle-Style Dataset-Based Implementation

---

## 5.1 Overview

The face recognition system uses a **dataset-based embedding approach** identical to implementations commonly found in Kaggle notebooks. This is NOT a cloud API or proprietary service.

**Core Approach:**
1. Store student face images in structured folders
2. Extract embeddings using pre-trained models (FaceNet)
3. Compare live face embeddings with stored embeddings
4. Use similarity threshold for verification

---

## 5.2 Dataset Structure

### 5.2.1 Folder Organization

```
dataset/
├── student_001_john_doe/
│   ├── img1.jpg
│   ├── img2.jpg
│   ├── img3.jpg
│   ├── img4.jpg
│   └── img5.jpg
├── student_002_jane_smith/
│   ├── img1.jpg
│   ├── img2.jpg
│   ├── img3.jpg
│   ├── img4.jpg
│   └── img5.jpg
├── student_003_alice_johnson/
│   ├── img1.jpg
│   ├── img2.jpg
│   └── img3.jpg
└── student_004_bob_williams/
    ├── img1.jpg
    ├── img2.jpg
    ├── img3.jpg
    └── img4.jpg
```

### 5.2.2 Dataset Requirements

**Folder Naming:**
- Format: `student_<ID>_<name>`
- Example: `student_001_john_doe`
- Must be unique per student

**Image Requirements:**
- Minimum: 3 images per student
- Recommended: 5 images per student
- Format: JPG, PNG
- Resolution: 640x480 or higher
- Quality: Clear, well-lit, full face visible
- Variety: Different angles, expressions, lighting

**Image Collection Guidelines:**
- Capture front-facing images
- Include slight head rotations (left, right)
- Vary facial expressions (neutral, smile)
- Ensure good lighting conditions
- No obstructions (hands, objects)
- Clear background preferred

---

## 5.3 Face Recognition Pipeline

### 5.3.1 Two-Phase Operation

**Phase 1: Enrollment (One-time)**
```
Load Images → Detect Faces → Extract Embeddings → Store in Database
```

**Phase 2: Verification (Every attendance)**
```
Capture Live Image → Detect Face → Extract Embedding → Compare → Verify
```

---

## 5.4 Detailed Implementation

### 5.4.1 Step 1: Load Dataset

**Purpose:** Read all student images from dataset folder

**Python Code:**
```python
import os
import cv2

def load_dataset(dataset_path):
    """
    Load all student images from dataset folder
    
    Args:
        dataset_path: Path to dataset folder
        
    Returns:
        List of dicts with student_id and images
    """
    students_data = []
    
    # Iterate through student folders
    for folder_name in os.listdir(dataset_path):
        folder_path = os.path.join(dataset_path, folder_name)
        
        # Skip if not a directory
        if not os.path.isdir(folder_path):
            continue
        
        # Extract student ID from folder name
        # Format: student_001_john_doe
        parts = folder_name.split('_')
        student_id = parts[1] if len(parts) > 1 else folder_name
        
        # Load all images
        images = []
        for img_file in os.listdir(folder_path):
            if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                img_path = os.path.join(folder_path, img_file)
                img = cv2.imread(img_path)
                
                if img is not None:
                    images.append(img)
        
        if len(images) > 0:
            students_data.append({
                'student_id': student_id,
                'name': '_'.join(parts[2:]) if len(parts) > 2 else '',
                'images': images
            })
    
    return students_data
```

**Output Example:**
```python
[
    {
        'student_id': '001',
        'name': 'john_doe',
        'images': [<numpy.ndarray>, <numpy.ndarray>, ...]
    },
    {
        'student_id': '002',
        'name': 'jane_smith',
        'images': [<numpy.ndarray>, <numpy.ndarray>, ...]
    }
]
```

---

### 5.4.2 Step 2: Preprocess Images

**Purpose:** Prepare images for face detection

**Python Code:**
```python
def preprocess_image(image):
    """
    Preprocess image for face detection
    
    Args:
        image: OpenCV image (BGR format)
        
    Returns:
        Preprocessed image (RGB format)
    """
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Resize to standard size (optional)
    # image_rgb = cv2.resize(image_rgb, (640, 480))
    
    return image_rgb
```

---

### 5.4.3 Step 3: Face Detection

**Purpose:** Detect and extract face region from image

**Using MTCNN (Recommended):**

```python
from mtcnn import MTCNN
import numpy as np

# Initialize detector (do this once)
detector = MTCNN()

def detect_face(image):
    """
    Detect face in image using MTCNN
    
    Args:
        image: RGB image (numpy array)
        
    Returns:
        Face image (cropped) or None if no face detected
    """
    # Detect faces
    results = detector.detect_faces(image)
    
    if len(results) == 0:
        return None
    
    # Get first face (assuming one person per image)
    face_data = results[0]
    x, y, width, height = face_data['box']
    
    # Add padding around face
    padding = 20
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(image.shape[1], x + width + padding)
    y2 = min(image.shape[0], y + height + padding)
    
    # Extract face region
    face_img = image[y1:y2, x1:x2]
    
    return face_img
```

**Alternative: Using OpenCV Haar Cascades (Faster but less accurate):**

```python
# Load Haar cascade
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

def detect_face_haar(image):
    """
    Detect face using Haar Cascade
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    if len(faces) == 0:
        return None
    
    x, y, w, h = faces[0]
    face_img = image[y:y+h, x:x+w]
    
    return face_img
```

---

### 5.4.4 Step 4: Extract Face Embeddings

**Purpose:** Convert face image to 512-dimensional vector

**Using FaceNet (keras-facenet):**

```python
from keras_facenet import FaceNet

# Initialize FaceNet model (do this once)
embedder = FaceNet()

def extract_embedding(face_img):
    """
    Extract face embedding using FaceNet
    
    Args:
        face_img: Face image (RGB)
        
    Returns:
        512-dimensional embedding vector
    """
    # Resize to FaceNet input size (160x160)
    face_resized = cv2.resize(face_img, (160, 160))
    
    # Normalize pixel values
    face_normalized = face_resized.astype('float32')
    
    # Expand dimensions for batch processing
    face_batch = np.expand_dims(face_normalized, axis=0)
    
    # Extract embedding
    embedding = embedder.embeddings(face_batch)
    
    # Return as 1D array
    return embedding[0]
```

**Using DeepFace Library:**

```python
from deepface import DeepFace

def extract_embedding_deepface(face_img):
    """
    Extract embedding using DeepFace
    """
    # DeepFace expects image path or numpy array
    embedding_obj = DeepFace.represent(
        img_path=face_img,
        model_name='Facenet',
        enforce_detection=False
    )
    
    # Extract embedding array
    embedding = np.array(embedding_obj[0]['embedding'])
    
    return embedding
```

**Embedding Properties:**
- Dimension: 512 (FaceNet) or 128 (some models)
- Type: Float32 array
- Range: Typically -1 to 1 (normalized)
- Same person → Similar embeddings
- Different people → Dissimilar embeddings

**Example Embedding:**
```python
array([0.123, -0.456, 0.789, 0.234, -0.567, ..., 0.891])
# 512 values total
```

---

### 5.4.5 Step 5: Store Embeddings

**Purpose:** Save embeddings to database for later comparison

**MongoDB Schema:**
```javascript
{
  _id: ObjectId("..."),
  studentId: "001",
  embeddings: [
    [0.123, -0.456, 0.789, ...],  // from img1.jpg
    [0.145, -0.423, 0.801, ...],  // from img2.jpg
    [0.134, -0.441, 0.795, ...]   // from img3.jpg
  ],
  createdAt: ISODate("2026-03-07T..."),
  updatedAt: ISODate("2026-03-07T...")
}
```

**Python Code:**
```python
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
client = MongoClient('mongodb://localhost:27017/')
db = client['attendance_system']
face_collection = db['face_data']

def store_student_embeddings(student_id, images):
    """
    Process images and store embeddings
    
    Args:
        student_id: Student ID
        images: List of face images
        
    Returns:
        Success status
    """
    embeddings = []
    
    for img in images:
        # Preprocess
        img_rgb = preprocess_image(img)
        
        # Detect face
        face = detect_face(img_rgb)
        
        if face is None:
            print(f"No face detected in image for student {student_id}")
            continue
        
        # Extract embedding
        embedding = extract_embedding(face)
        
        # Convert to list for MongoDB storage
        embeddings.append(embedding.tolist())
    
    if len(embeddings) == 0:
        return False
    
    # Store in database
    face_collection.update_one(
        {'studentId': student_id},
        {
            '$set': {
                'embeddings': embeddings,
                'updatedAt': datetime.now()
            },
            '$setOnInsert': {
                'createdAt': datetime.now()
            }
        },
        upsert=True
    )
    
    return True
```

**Enrollment Process:**
```python
def enroll_all_students(dataset_path):
    """
    Enroll all students from dataset
    """
    students_data = load_dataset(dataset_path)
    
    for student in students_data:
        print(f"Enrolling student {student['student_id']}...")
        success = store_student_embeddings(
            student['student_id'],
            student['images']
        )
        
        if success:
            print(f"✓ Student {student['student_id']} enrolled")
        else:
            print(f"✗ Failed to enroll student {student['student_id']}")
```

---

### 5.4.6 Step 6: Compute Similarity

**Purpose:** Compare two face embeddings

**Cosine Similarity (Recommended):**

```python
def cosine_similarity(embedding1, embedding2):
    """
    Compute cosine similarity between two embeddings
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Similarity score (0 to 1, higher = more similar)
    """
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    # Compute dot product
    dot_product = np.dot(vec1, vec2)
    
    # Compute norms
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    # Compute cosine similarity
    similarity = dot_product / (norm1 * norm2)
    
    return similarity
```

**Euclidean Distance:**

```python
def euclidean_distance(embedding1, embedding2):
    """
    Compute Euclidean distance between embeddings
    
    Returns:
        Distance (lower = more similar)
    """
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    distance = np.linalg.norm(vec1 - vec2)
    
    return distance
```

**Similarity Interpretation:**

| Cosine Similarity | Interpretation |
|-------------------|----------------|
| 0.8 - 1.0 | Very high similarity (same person) |
| 0.6 - 0.8 | High similarity (likely same person) |
| 0.4 - 0.6 | Medium similarity (uncertain) |
| 0.0 - 0.4 | Low similarity (different person) |

---

### 5.4.7 Step 7: Verify Identity

**Purpose:** Check if live face matches stored student data

**Complete Verification Function:**

```python
def verify_face(student_id, live_image, threshold=0.6):
    """
    Verify if live face matches student's registered face
    
    Args:
        student_id: Student ID to verify against
        live_image: Live captured image
        threshold: Similarity threshold (default 0.6)
        
    Returns:
        Dict with verification result
    """
    # Step 1: Preprocess live image
    img_rgb = preprocess_image(live_image)
    
    # Step 2: Detect face
    face = detect_face(img_rgb)
    
    if face is None:
        return {
            'verified': False,
            'confidence': 0.0,
            'reason': 'No face detected in image'
        }
    
    # Step 3: Extract embedding from live face
    live_embedding = extract_embedding(face)
    
    # Step 4: Retrieve stored embeddings
    face_data = face_collection.find_one({'studentId': student_id})
    
    if not face_data or 'embeddings' not in face_data:
        return {
            'verified': False,
            'confidence': 0.0,
            'reason': 'No face data registered for this student'
        }
    
    stored_embeddings = face_data['embeddings']
    
    # Step 5: Compare with all stored embeddings
    similarities = []
    for stored_embedding in stored_embeddings:
        similarity = cosine_similarity(live_embedding, stored_embedding)
        similarities.append(similarity)
    
    # Step 6: Get maximum similarity
    max_similarity = max(similarities)
    avg_similarity = np.mean(similarities)
    
    # Step 7: Apply threshold
    if max_similarity >= threshold:
        return {
            'verified': True,
            'confidence': float(max_similarity),
            'avg_confidence': float(avg_similarity),
            'message': 'Face verified successfully'
        }
    else:
        return {
            'verified': False,
            'confidence': float(max_similarity),
            'avg_confidence': float(avg_similarity),
            'reason': f'Similarity {max_similarity:.2f} below threshold {threshold}'
        }
```

---

## 5.5 Threshold Configuration

### 5.5.1 Threshold Selection

**Recommended Threshold: 0.6**

**Threshold Trade-offs:**

| Threshold | Security | User Experience | Use Case |
|-----------|----------|-----------------|----------|
| 0.4 | Low | Excellent | Testing only |
| 0.5 | Medium | Good | Lenient system |
| 0.6 | High | Good | **Recommended** |
| 0.7 | Very High | Fair | High security |
| 0.8 | Extreme | Poor | Maximum security |

### 5.5.2 Threshold Tuning

**Process:**
1. Collect test data (genuine attempts + imposter attempts)
2. Test multiple thresholds
3. Calculate metrics:
   - True Accept Rate (TAR)
   - False Accept Rate (FAR)
   - False Reject Rate (FRR)
4. Choose threshold that balances FAR and FRR

**Python Code:**
```python
def tune_threshold(test_data):
    """
    Find optimal threshold
    
    test_data format:
    [
        {'student_id': '001', 'image': img, 'is_genuine': True},
        {'student_id': '001', 'image': img2, 'is_genuine': False},
        ...
    ]
    """
    thresholds = np.arange(0.3, 0.9, 0.05)
    results = []
    
    for threshold in thresholds:
        true_accepts = 0
        false_accepts = 0
        true_rejects = 0
        false_rejects = 0
        
        for test in test_data:
            result = verify_face(
                test['student_id'],
                test['image'],
                threshold
            )
            
            if test['is_genuine']:
                if result['verified']:
                    true_accepts += 1
                else:
                    false_rejects += 1
            else:
                if result['verified']:
                    false_accepts += 1
                else:
                    true_rejects += 1
        
        tar = true_accepts / (true_accepts + false_rejects)
        far = false_accepts / (false_accepts + true_rejects)
        frr = false_rejects / (true_accepts + false_rejects)
        
        results.append({
            'threshold': threshold,
            'TAR': tar,
            'FAR': far,
            'FRR': frr
        })
    
    return results
```

---

## 5.6 Flask API Implementation

### 5.6.1 Flask Server Setup

```python
from flask import Flask, request, jsonify
import base64
import numpy as np
import cv2

app = Flask(__name__)

# Initialize models (once at startup)
detector = MTCNN()
embedder = FaceNet()

def decode_base64_image(base64_string):
    """Convert base64 string to OpenCV image"""
    img_data = base64.b64decode(base64_string)
    nparr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    return img
```

### 5.6.2 Face Registration Endpoint

```python
@app.route('/face/register', methods=['POST'])
def register_face():
    """
    Register student face
    
    Request body:
    {
        "student_id": "001",
        "images": ["base64_img1", "base64_img2", ...]
    }
    """
    try:
        data = request.json
        student_id = data['student_id']
        images_base64 = data['images']
        
        # Decode images
        images = [decode_base64_image(img) for img in images_base64]
        
        # Store embeddings
        success = store_student_embeddings(student_id, images)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Face registered successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to detect faces in images'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
```

### 5.6.3 Face Verification Endpoint

```python
@app.route('/face/verify', methods=['POST'])
def verify_face_endpoint():
    """
    Verify student face
    
    Request body:
    {
        "student_id": "001",
        "image": "base64_encoded_image"
    }
    """
    try:
        data = request.json
        student_id = data['student_id']
        image_base64 = data['image']
        
        # Decode image
        image = decode_base64_image(image_base64)
        
        # Verify face
        result = verify_face(student_id, image, threshold=0.6)
        
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({
            'verified': False,
            'reason': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## 5.7 Error Handling

### 5.7.1 Common Errors

**No Face Detected:**
```python
{
    'verified': False,
    'reason': 'No face detected in image',
    'action': 'retry',
    'suggestion': 'Ensure your face is clearly visible and well-lit'
}
```

**Multiple Faces:**
```python
{
    'verified': False,
    'reason': 'Multiple faces detected',
    'action': 'retry',
    'suggestion': 'Ensure only you are in the frame'
}
```

**Low Confidence:**
```python
{
    'verified': False,
    'confidence': 0.45,
    'reason': 'Similarity below threshold',
    'action': 'retry',
    'suggestion': 'Try better lighting or different angle'
}
```

**No Registered Data:**
```python
{
    'verified': False,
    'reason': 'No face data registered',
    'action': 'register',
    'suggestion': 'Please register your face first'
}
```

### 5.7.2 Retry Logic

```python
MAX_ATTEMPTS = 3

def verify_with_retry(student_id, image, attempt=1):
    """Verify with retry mechanism"""
    result = verify_face(student_id, image)
    
    if result['verified']:
        return result
    
    if attempt >= MAX_ATTEMPTS:
        return {
            'verified': False,
            'reason': 'Maximum attempts exceeded',
            'action': 'contact_admin',
            'attempts': attempt
        }
    
    result['attempts_remaining'] = MAX_ATTEMPTS - attempt
    result['action'] = 'retry'
    
    return result
```

---

## 5.8 Performance Metrics

**Target Performance:**
- Face detection: < 200ms
- Embedding extraction: < 500ms
- Similarity computation: < 50ms
- Total verification time: < 1 second

**Accuracy Targets:**
- True Accept Rate: > 95%
- False Accept Rate: < 1%
- False Reject Rate: < 5%

