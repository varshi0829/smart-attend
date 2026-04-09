
import sys
import os
import cv2
import numpy as np
import pickle
import traceback

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
from app import config
config.DB_ENABLED = False  # Ensure DB is disabled for this test
config.THRESHOLD = 0.6     # Ensure threshold is 0.6

from app.face_pipeline import extract_embedding
from app.matcher import load_student_embeddings, verify_face_match

def test_pipeline():
    print("=== Testing Face Service Safe Mode ===")
    
    # 1. Test Valid Student
    print("\n[TEST 1] Valid Student Match")
    roll = "24WH1A0501"
    photo_path = "photos/24WH1A0501/Dataset-lakshmi-1.jpeg"
    full_photo_path = os.path.join("..", photo_path)
    
    img = cv2.imread(full_photo_path)
    if img is None:
        print(f"FAILED: Could not read {full_photo_path}")
    else:
        # Extract live embedding
        res = extract_embedding(img)
        if res["status"] != "ok":
            print(f"FAILED: Embedding extraction failed: {res['message']}")
        else:
            live_emb = res["embedding"]
            # Load stored
            stored, err, msg = load_student_embeddings(roll)
            if not stored:
                print(f"FAILED: Could not load stored embeddings for {roll}: {msg}")
            else:
                is_match, score, err_code, _, _ = verify_face_match(live_emb, stored)
                print(f"Result: Match={is_match}, Score={score:.4f}, Error={err_code}")
                # If this fails, it might be because the .pkl contains DeepFace embeddings
                # and we are extracting InsightFace embeddings.
                if not is_match and score < 0.6:
                    print("NOTE: Match failed, possibly due to model mismatch (DeepFace in .pkl vs InsightFace live)")

    # 2. Test Wrong Student
    print("\n[TEST 2] Wrong Student (Mismatch)")
    # Using 24WH1A0501 photo but checking against 24WH1A0525
    roll_wrong = "24WH1A0525"
    stored_wrong, err, msg = load_student_embeddings(roll_wrong)
    if stored_wrong:
        is_match, score, err_code, _, _ = verify_face_match(live_emb, stored_wrong)
        print(f"Result: Match={is_match}, Score={score:.4f}, Error={err_code}")
        if not is_match:
            print("OK: Correctly rejected.")
        else:
            print("FAILED: Wrong student matched!")

    # 3. Test No Face
    print("\n[TEST 3] No Face")
    blank_img = np.zeros((100, 100, 3), dtype=np.uint8)
    res_no = extract_embedding(blank_img)
    print(f"Result: Status={res_no['status']}, Message={res_no['message']}")
    if res_no["status"] == "no_face":
        print("OK: Correctly detected no face.")

    # 4. Test Fallback (Simulated failure)
    print("\n[TEST 4] Fallback Logic")
    from app import face_pipeline
    original_app = face_pipeline._face_app
    face_pipeline._face_app = None
    face_pipeline._init_error = "Simulated InsightFace Failure"
    
    print("Attempting extraction with InsightFace 'failed'...")
    res_fallback = extract_embedding(img)
    print(f"Result: Status={res_fallback['status']}, Message={res_fallback['message']}")
    if "fallback" in res_fallback["message"].lower() or res_fallback["status"] == "ok":
        print("OK: Fallback worked (or at least didn't crash).")
    
    # Restore
    face_pipeline._face_app = original_app
    face_pipeline._init_error = None

if __name__ == "__main__":
    test_pipeline()
