import os
import logging

# ── Legacy DeepFace settings (kept for fallback .pkl compatibility) ───────────
MODEL_NAME       = "ArcFace"          # used in health + debug responses
DETECTOR_BACKEND = "retinaface"       # legacy only
MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB payload limit

# ── InsightFace pipeline ──────────────────────────────────────────────────────
INSIGHTFACE_MODEL  = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
INSIGHTFACE_CTX_ID = int(os.getenv("INSIGHTFACE_CTX_ID", "0"))   # 0 = CPU, 1+ = GPU
DET_SIZE           = (640, 640)
DET_SCORE_THRESHOLD = float(os.getenv("DET_SCORE_THRESHOLD", "0.5"))
MIN_FACE_SIZE_PX    = int(os.getenv("MIN_FACE_SIZE_PX", "40"))    # pixels (W or H)

# ── Match threshold ───────────────────────────────────────────────────────────
# Cosine similarity on L2-normed 512-d ArcFace embeddings.
# InsightFace buffalo_l: same-person ≈ 0.4–0.8 / diff-person ≈ 0.0–0.25
THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.60"))

# ── Storage paths ─────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDINGS_DIR  = os.path.join(BASE_DIR, "embeddings")
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

# ── PostgreSQL / pgvector ─────────────────────────────────────────────────────
# Set DB_ENABLED=true and supply a proper DSN to activate the DB path.
# When DB is unavailable the service automatically falls back to .pkl files.
DB_ENABLED = False  # Forced safe mode: DB not yet installed
DB_DSN     = os.getenv(
    "DB_DSN",
    "postgresql://smartattend:smartattend@localhost:5432/smartattend_faces"
)
EMBEDDING_DIM  = 512            # ArcFace embedding dimension
DB_POOL_MINCONN = 1
DB_POOL_MAXCONN = 5

# ── Misc ──────────────────────────────────────────────────────────────────────
PRODUCTION_MODE      = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
ALLOW_MULTIPLE_FACES = False   # security requirement: one person per frame

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FaceService")