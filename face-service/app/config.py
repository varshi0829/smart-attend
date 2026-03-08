import os
import logging

# Face Recognition Settings
MODEL_NAME = "Facenet"
DETECTOR_BACKEND = "opencv"
THRESHOLD = 0.6  # Similarity threshold
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
