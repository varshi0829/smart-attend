from flask import Flask, request, jsonify
import base64
import numpy as np
import os
import pickle
from deepface import DeepFace
import cv2

app = Flask(__name__)

# Storage directory for face embeddings
EMBEDDINGS_DIR = 'embeddings'
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

def decode_base64_image(base64_str):
    """Decode base64 string to image array"""
    if ',' in base64_str:
        base64_str = base64_str.split(',')[1]
    
    img_bytes = base64.b64decode(base64_str)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return img

def extract_face_embedding(image_array):
    """Extract face embedding using DeepFace (Facenet)"""
    try:
        embeddings = DeepFace.represent(
            img_path=image_array,
            model_name="Facenet",
            enforce_detection=True,
            detector_backend='opencv'
        )
        if len(embeddings) == 0:
            return None
        return np.array(embeddings[0]['embedding'])
    except Exception as e:
        print(f"Extraction error: {e}")
        return None

def cosine_similarity(emb1, emb2):
    """Calculate cosine similarity between two embeddings"""
    dot_product = np.dot(emb1, emb2)
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0

@app.route('/face/register', methods=['POST'])
def register_face():
    try:
        data = request.json
        student_id = data.get('studentId')
        face_image = data.get('faceImage')
        
        if not student_id or not face_image:
            return jsonify({'error': 'studentId and faceImage required'}), 400
        
        image_array = decode_base64_image(face_image)
        new_embedding = extract_face_embedding(image_array)
        
        if new_embedding is None:
            return jsonify({'error': 'No face detected'}), 400

        # Load existing or create new
        embedding_path = os.path.join(EMBEDDINGS_DIR, f'{student_id}.pkl')
        student_data = {'studentId': student_id, 'embeddings': []}
        
        if os.path.exists(embedding_path):
            with open(embedding_path, 'rb') as f:
                student_data = pickle.load(f)
        
        student_data['embeddings'].append(new_embedding)
        
        with open(embedding_path, 'wb') as f:
            pickle.dump(student_data, f)
        
        return jsonify({
            'success': True,
            'count': len(student_data['embeddings']),
            'studentId': student_id
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/face/verify', methods=['POST'])
def verify_face():
    try:
        data = request.json
        student_id = data.get('studentId')
        face_image = data.get('faceImage')
        
        embedding_path = os.path.join(EMBEDDINGS_DIR, f'{student_id}.pkl')
        if not os.path.exists(embedding_path):
            return jsonify({'verified': False, 'error': 'No face registered'}), 200
        
        with open(embedding_path, 'rb') as f:
            student_data = pickle.load(f)
        
        image_array = decode_base64_image(face_image)
        current_embedding = extract_face_embedding(image_array)
        
        if current_embedding is None:
            return jsonify({'verified': False, 'error': 'No face detected'}), 200

        # Compare against all stored embeddings and pick BEST score
        similarities = [cosine_similarity(current_embedding, emb) for emb in student_data['embeddings']]
        best_score = max(similarities) if similarities else 0.0
        
        THRESHOLD = 0.6
        return jsonify({
            'verified': bool(best_score >= THRESHOLD),
            'confidence': float(best_score)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
