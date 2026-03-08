import cv2
import numpy as np
from deepface import DeepFace
from .config import MODEL_NAME, DETECTOR_BACKEND, logger

def process_uploaded_image(image_bytes: bytes):
    """Convert raw bytes to OpenCV image array with error handling."""
    try:
        if not image_bytes:
            return None
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            logger.error("[UTILS] OpenCV failed to decode image buffer.")
        return img
    except Exception as e:
        logger.error(f"[UTILS] Image decoding failed: {e}")
        return None

def get_embedding(img_array):
    """
    Extract face embedding with strict single-face enforcement.
    Returns: {"status": "ok" | "no_face" | "multiple_faces" | "decode_error" | "error", "embedding": np.array, "message": str}
    """
    if img_array is None:
        return {"status": "decode_error", "embedding": None, "message": "Failed to decode image data."}

    try:
        logger.info(f"[UTILS] Running DeepFace representation using {MODEL_NAME}...")
        results = DeepFace.represent(
            img_path=img_array,
            model_name=MODEL_NAME,
            enforce_detection=True,
            detector_backend=DETECTOR_BACKEND
        )

        if not results:
            logger.warning("[UTILS] DeepFace returned empty results.")
            return {"status": "no_face", "embedding": None, "message": "No face detected."}

        if len(results) > 1:
            logger.warning(f"[UTILS] Multiple faces detected: {len(results)}")
            return {"status": "multiple_faces", "embedding": None, "message": "Multiple faces detected. Only one person should be in the frame."}

        # Success - Single face
        embedding = np.array(results[0]["embedding"], dtype=np.float32)
        logger.info(f"[UTILS] Successfully generated embedding with shape {embedding.shape}")
        return {
            "status": "ok",
            "embedding": embedding,
            "message": "Face embedding generated successfully."
        }

    except ValueError as e:
        msg = str(e)
        if "Face could not be detected" in msg:
            logger.warning("[UTILS] Face detection failed.")
            return {"status": "no_face", "embedding": None, "message": "No face detected."}
        logger.error(f"[UTILS] DeepFace ValueError: {msg}")
        return {"status": "error", "embedding": None, "message": f"Detection error: {msg}"}
    except Exception as e:
        logger.error(f"[UTILS] Unexpected DeepFace error: {e}")
        return {"status": "error", "embedding": None, "message": "Internal face processing error."}
