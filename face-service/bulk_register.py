import os
import pickle
import numpy as np
import cv2
from deepface import DeepFace
from tqdm import tqdm

PHOTOS_DIR = '../photos'
EMBEDDINGS_DIR = 'embeddings'
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

def process_photos():
    if not os.path.exists(PHOTOS_DIR):
        print(f"Error: {PHOTOS_DIR} directory not found.")
        return

    student_folders = [f for f in os.listdir(PHOTOS_DIR) if os.path.isdir(os.path.join(PHOTOS_DIR, f))]
    
    print(f"Found {len(student_folders)} students. Starting bulk registration...")

    for student_id in tqdm(student_folders, desc="Processing Students"):
        save_path = os.path.join(EMBEDDINGS_DIR, f'{student_id}.pkl')
        if os.path.exists(save_path):
            continue

        student_path = os.path.join(PHOTOS_DIR, student_id)
        image_files = [f for f in os.listdir(student_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'))]
        
        embeddings = []
        for img_name in image_files:
            img_path = os.path.join(student_path, img_name)
            try:
                # Extract embedding directly from file
                result = DeepFace.represent(
                    img_path=img_path,
                    model_name="Facenet",
                    enforce_detection=True,
                    detector_backend='opencv'
                )
                if result:
                    embeddings.append(np.array(result[0]['embedding']))
            except Exception as e:
                print(f"Skipping {img_path}: {e}")

        if embeddings:
            save_path = os.path.join(EMBEDDINGS_DIR, f'{student_id}.pkl')
            data = {'studentId': student_id, 'embeddings': embeddings}
            with open(save_path, 'wb') as f:
                pickle.dump(data, f)

    print("\nBulk registration complete.")

if __name__ == "__main__":
    process_photos()
