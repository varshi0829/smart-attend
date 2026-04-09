#!/usr/bin/env python3
"""
migrate_embeddings.py
=====================
SmartAttend — Face Embedding Migration to InsightFace + PostgreSQL

What it does
------------
For each student:
  1. Tries to re-generate embeddings from the original photo using InsightFace
     buffalo_l (preferred — guarantees model consistency).
  2. Falls back to importing the existing .pkl embedding directly if no photo
     is found (embedding may be DeepFace-era; accuracy is lower, but the
     student stays in the system).
  3. Writes the embedding to PostgreSQL student_face_embeddings table.
  4. Updates (or creates) the .pkl file with the same InsightFace embedding,
     so the .pkl fallback path also uses the new model after migration.

Important
---------
  • Existing .pkl files are NEVER deleted — originals are backed up first.
  • Run this script once, after PostgreSQL + pgvector are set up.
  • Re-running is safe: --force re-processes every student,
    default skips students already in DB.

Usage
-----
  cd face-service
  ./venv/bin/python3 migrate_embeddings.py [--force] [--roll 24WH1A0501] [--dry-run] [--skip-db]

Options
-------
  --force      Re-generate even if student already exists in DB / .pkl
  --roll ROLL  Process a single student only
  --dry-run    Print what would happen, write nothing
  --skip-db    Regenerate .pkl only (no DB write — useful before DB is set up)
  --no-backup  Skip creating .pkl_bak backup files
"""

import os
import sys
import pickle
import shutil
import argparse
import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
EMBEDDINGS_DIR = os.path.join(SCRIPT_DIR, "embeddings")
PHOTOS_BASE    = os.path.join(SCRIPT_DIR, "..", "students", "CSE")
EXPECTED_DIM   = 512

# Add the face-service package to sys.path so we can import app.*
sys.path.insert(0, SCRIPT_DIR)

# ── InsightFace (lazy import so --dry-run and --skip-db work without it) ──────
_insight_app = None

def get_face_app():
    global _insight_app
    if _insight_app is not None:
        return _insight_app
    from insightface.app import FaceAnalysis
    import cv2   # noqa — triggers proper cv2 import inside insightface
    print("[INIT] Loading InsightFace buffalo_l …")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_thresh=0.5, det_size=(640, 640))
    _insight_app = app
    print("[INIT] InsightFace ready.\n")
    return app


def embed_from_photo(photo_path: str):
    """
    Generate a 512-d normed embedding from a photo file using InsightFace.
    Returns np.ndarray(512,) or None on failure.
    """
    import cv2
    img = cv2.imread(photo_path)
    if img is None:
        print(f"  [WARN] Cannot read image: {photo_path}")
        return None

    app   = get_face_app()
    faces = app.get(img)
    if not faces:
        print(f"  [WARN] No face detected in: {os.path.basename(photo_path)}")
        return None
    if len(faces) > 1:
        print(f"  [WARN] Multiple faces in {os.path.basename(photo_path)} — using highest-confidence one.")
        faces = sorted(faces, key=lambda f: float(f.det_score), reverse=True)[:1]

    emb = np.array(faces[0].normed_embedding, dtype=np.float32)
    if emb.shape != (EXPECTED_DIM,):
        print(f"  [WARN] Wrong embedding shape {emb.shape} for {photo_path}")
        return None
    return emb


def find_photo(roll: str):
    """
    Search for a student photo under PHOTOS_BASE.
    Supports flat: PHOTOS_BASE/SECTION/ROLL.jpg
    and nested:    PHOTOS_BASE/SECTION/ROLL/ROLL.jpg
    """
    if not os.path.isdir(PHOTOS_BASE):
        return None
    for root, dirs, files in os.walk(PHOTOS_BASE):
        dirs.sort()
        for fname in files:
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            stem = os.path.splitext(fname)[0].strip().upper()
            if stem == roll:
                return os.path.join(root, fname)
    return None


def load_pkl_embedding(roll: str):
    """Load first valid embedding from existing .pkl file."""
    path = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            raw = data.get("embeddings", [data.get("embedding")])
        elif isinstance(data, (list, tuple)):
            raw = list(data)
        else:
            raw = [data]
        for item in raw:
            if item is None:
                continue
            arr = np.array(item, dtype=np.float32)
            if arr.size == EXPECTED_DIM:
                return arr.reshape(EXPECTED_DIM)
    except Exception as exc:
        print(f"  [WARN] Failed to read .pkl for {roll}: {exc}")
    return None


def save_pkl(roll: str, embedding: np.ndarray, source: str, backup: bool = True):
    """Overwrite .pkl with a fresh InsightFace embedding (backup original first)."""
    path = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")
    if backup and os.path.exists(path):
        bak = path + ".bak"
        if not os.path.exists(bak):
            shutil.copy2(path, bak)
    data = {"studentId": roll, "embeddings": [embedding], "model": source, "version": 2}
    with open(path, "wb") as f:
        pickle.dump(data, f)


def already_in_db(roll: str) -> bool:
    """Return True if at least one active embedding exists in DB for this student."""
    try:
        from app.db_store import load_embeddings
        rows = load_embeddings(roll)
        return rows is not None and len(rows) > 0
    except Exception:
        return False


def save_to_db(roll: str, embedding: np.ndarray, source: str) -> bool:
    """Deactivate old rows and insert fresh embedding into DB."""
    try:
        from app.db_store import deactivate_embeddings, save_embedding
        deactivate_embeddings(roll)
        return save_embedding(roll, embedding, source=source)
    except Exception as exc:
        print(f"  [ERROR] DB write failed for {roll}: {exc}")
        return False


# ── Main loop ─────────────────────────────────────────────────────────────────

def get_all_rolls():
    """Return sorted list of roll numbers from existing .pkl files."""
    return sorted(
        os.path.splitext(f)[0].upper()
        for f in os.listdir(EMBEDDINGS_DIR)
        if f.endswith(".pkl") and not f.endswith(".pkl.bak")
    )


def process_student(roll: str, args) -> str:
    """
    Attempt migration for one student.
    Returns: 'photo_migrated' | 'pkl_imported' | 'skipped' | 'failed'
    """
    if not args.force and not args.skip_db:
        if already_in_db(roll):
            return "skipped"

    # ── Try photo first ───────────────────────────────────────────────────────
    photo = find_photo(roll)
    if photo:
        emb = embed_from_photo(photo)
        if emb is not None:
            source = "insightface_buffalo_l"
            if not args.dry_run:
                if not args.skip_db:
                    ok_db = save_to_db(roll, emb, source)
                    if not ok_db:
                        print(f"  [WARN] DB write failed for {roll}; .pkl updated anyway.")
                if args.backup:
                    save_pkl(roll, emb, source, backup=True)
            return "photo_migrated"
        # photo exists but embed failed — fall through to pkl import

    # ── Fallback: import existing .pkl ───────────────────────────────────────
    emb = load_pkl_embedding(roll)
    if emb is None:
        return "failed"
    source = "legacy_import"
    if not args.dry_run:
        if not args.skip_db:
            save_to_db(roll, emb, source)
        # .pkl stays as-is (it's the source of truth for this case)
    return "pkl_imported"


def main():
    parser = argparse.ArgumentParser(description="Migrate face embeddings to InsightFace + pgvector")
    parser.add_argument("--force",    action="store_true", help="Re-process even if already in DB")
    parser.add_argument("--roll",     type=str, default=None, help="Migrate one roll number only")
    parser.add_argument("--dry-run",  action="store_true", help="Print plan without writing")
    parser.add_argument("--skip-db",  action="store_true", help="Regenerate .pkl only (no DB write)")
    parser.add_argument("--no-backup",action="store_true", help="Skip .pkl.bak backups")
    args = parser.parse_args()
    args.backup = not args.no_backup

    print("=" * 60)
    print(" SmartAttend — Face Embedding Migration")
    print("=" * 60)
    print(f" Embeddings dir : {EMBEDDINGS_DIR}")
    print(f" Photos base    : {PHOTOS_BASE}")
    print(f" Force          : {args.force}")
    print(f" Skip DB        : {args.skip_db}")
    print(f" Dry run        : {args.dry_run}")
    print(f" Backup .pkl    : {args.backup}")
    print()

    rolls = get_all_rolls()
    if args.roll:
        target = args.roll.strip().upper()
        rolls = [r for r in rolls if r == target]
        if not rolls:
            print(f"[ERROR] Roll number {target} not found in {EMBEDDINGS_DIR}")
            return

    if not rolls:
        print("[ERROR] No .pkl files found in embeddings directory.")
        return

    print(f"Students to process: {len(rolls)}\n")

    # ── 1. DB Safety Check ───────────────────────────────────────────────────
    if not args.skip_db and not args.dry_run:
        from app.db_store import is_available, init
        init()  # Ensure pool is initialised
        if not is_available():
            print("[ERROR] PostgreSQL is not available (or DB_ENABLED=false).")
            print("        Cannot migrate to DB. Check your connection / setup_postgres.sh.")
            print("        To proceed with .pkl regeneration ONLY, use --skip-db.")
            sys.exit(1)
        print("[OK] PostgreSQL connection verified.\n")

    counts = {"photo_migrated": 0, "pkl_imported": 0, "skipped": 0, "failed": 0}

    for i, roll in enumerate(rolls, 1):
        print(f"[{i:>4}/{len(rolls)}] {roll} … ", end="", flush=True)
        result = process_student(roll, args)
        counts[result] += 1
        icon = {"photo_migrated": "✓ photo", "pkl_imported": "↑ pkl-import",
                "skipped": "– skip", "failed": "✗ FAIL"}
        print(icon.get(result, result))

    print()
    print("=" * 60)
    print(" Migration Summary")
    print("=" * 60)
    print(f"  Photo re-generated : {counts['photo_migrated']}")
    print(f"  Imported from .pkl : {counts['pkl_imported']}  ← legacy model, lower accuracy")
    print(f"  Already in DB      : {counts['skipped']}")
    print(f"  Failed             : {counts['failed']}")
    print()

    if counts["pkl_imported"] > 0:
        print("[WARN] Some students were imported from old .pkl files (DeepFace model).")
        print("       Their photos may produce lower match accuracy until photos are added.")
        print("       Re-run with --force once photos are available.\n")

    if counts["failed"] > 0:
        print("[ERROR] Some students failed completely. Check output above.\n")
    else:
        print("[OK] Migration complete. Run the face service — it will use InsightFace + pgvector.\n")


if __name__ == "__main__":
    main()