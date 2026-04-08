import os
import logging

# Face Recognition Settings
MODEL_NAME = "ArcFace"
DETECTOR_BACKEND = "retinaface"
THRESHOLD = 0.45  # Optimized for ArcFace Cosine Similarity
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB Payload Limit
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
ALLOW_MULTIPLE_FACES = False # Security requirement

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDINGS_DIR = os.path.join(BASE_DIR, "embeddings")

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FaceService")

# Ensure directory exists
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
