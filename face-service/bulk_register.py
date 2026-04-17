"""
SmartAttend — Bulk Student Enrollment
Model: InsightFace buffalo_l (ArcFace + SCRFD)

Photos source: ../students/CSE/{SECTION}/{ROLL_NUMBER}/
               ../students/CSE/{SECTION}/{ROLL_NUMBER}.jpg
Output:        embeddings/{ROLL_NUMBER}.pkl  (+ optional DB write)

Run from face-service/ directory:
    ./venv/bin/python3 bulk_register.py

Options:
    --force     Overwrite existing .pkl files (default: skip already-enrolled)
    --roll      Enroll only one student: --roll 24WH1A0527
    --dry-run   List what would be enrolled without writing files
    --db        Also write to PostgreSQL (requires DB_ENABLED + DB_DSN in env)
    --verify    Only verify existing .pkl files, no enrollment
"""

import os
import sys
import pickle
import argparse
import numpy as np

# ── Config ────────────────────────────────────────────────────────────────────
EXPECTED_DIM     = 512          # ArcFace 512-d
PHOTOS_BASE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "students", "CSE")
EMBEDDINGS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings")
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

# InsightFace lazy singleton ─────────────────────────────────────────────────
_face_app = None

def get_face_app():
    global _face_app
    if _face_app is not None:
        return _face_app
    from insightface.app import FaceAnalysis
    print("Loading InsightFace buffalo_l …")
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_thresh=0.5, det_size=(640, 640))
    _face_app = app
    print("InsightFace ready.\n")
    return app


def get_all_photos():
    """
    Walk PHOTOS_BASE_DIR and return list of (roll_number, photo_path).
    Supports flat and nested layouts (same as original bulk_register.py).
    """
    photos = []
    if not os.path.exists(PHOTOS_BASE_DIR):
        print(f"[ERROR] Photos directory not found: {PHOTOS_BASE_DIR}")
        return photos

    for root, dirs, files in os.walk(PHOTOS_BASE_DIR):
        dirs.sort()
        for fname in sorted(files):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            stem        = os.path.splitext(fname)[0].strip().upper()
            parent_name = os.path.basename(root).strip().upper()

            if parent_name == stem:            # nested: .../CSE-A/24WH1A0501/24WH1A0501.jpg
                roll = stem
            elif len(stem) >= 8 and stem[0].isdigit():   # flat: .../CSE-A/24WH1A0501.jpg
                roll = stem
            else:
                continue

            photos.append((roll, os.path.join(root, fname)))

    return photos


def enroll_student(roll: str, photo_path: str, force: bool = False, write_db: bool = False) -> str:
    """
    Generate InsightFace buffalo_l embedding for one student photo.
    Returns: 'enrolled' | 'skipped' | 'failed'
    """
    import cv2
    out_path = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")

    if os.path.exists(out_path) and not force:
        return "skipped"

    # ── Decode image ─────────────────────────────────────────────────────────
    img = cv2.imread(photo_path)
    if img is None:
        print(f"  [FAIL] {roll}: cannot read image {os.path.basename(photo_path)}")
        return "failed"

    # ── Detect + embed ────────────────────────────────────────────────────────
    app   = get_face_app()
    faces = app.get(img)

    if not faces:
        print(f"  [FAIL] {roll}: no face detected in {os.path.basename(photo_path)}")
        return "failed"

    if len(faces) > 1:
        print(f"  [WARN] {roll}: {len(faces)} faces detected, using highest confidence")
        faces = sorted(faces, key=lambda f: float(f.det_score), reverse=True)[:1]

    face = faces[0]
    if float(face.det_score) < 0.5:
        print(f"  [FAIL] {roll}: low detection confidence {face.det_score:.2f}")
        return "failed"

    embedding = np.array(face.normed_embedding, dtype=np.float32)

    if embedding.shape != (EXPECTED_DIM,):
        print(f"  [FAIL] {roll}: unexpected embedding shape {embedding.shape}")
        return "failed"

    # ── Persist ───────────────────────────────────────────────────────────────
    data = {"studentId": roll, "embeddings": [embedding], "model": "insightface_buffalo_l", "version": 2}
    with open(out_path, "wb") as f:
        pickle.dump(data, f)

    # Optional DB write
    if write_db:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from app.db_store import save_embedding, deactivate_embeddings
            deactivate_embeddings(roll)
            saved = save_embedding(roll, embedding, source="insightface_buffalo_l")
            if not saved:
                print(f"  [WARN] {roll}: DB write failed; .pkl saved OK")
        except Exception as exc:
            print(f"  [WARN] {roll}: DB write error: {exc}")

    return "enrolled"


def verify_embeddings():
    """
    Sanity check all .pkl files.
    Prints a clean summary line only — no per-file output.
    Validation logic is unchanged; only the printing is condensed.
    """
    total   = 0
    valid   = 0
    invalid = []

    for fname in sorted(os.listdir(EMBEDDINGS_DIR)):
        if not fname.endswith(".pkl") or fname.endswith(".pkl.bak"):
            continue
        total += 1
        fpath = os.path.join(EMBEDDINGS_DIR, fname)
        try:
            with open(fpath, "rb") as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                raw = data.get("embeddings", [data.get("embedding")])
            else:
                raw = data if isinstance(data, list) else [data]
            shapes = [np.array(e, dtype=np.float32).shape for e in raw if e is not None]
            if shapes and all(s == (EXPECTED_DIM,) for s in shapes):
                valid += 1
            else:
                invalid.append(fname)
        except Exception:
            invalid.append(fname)

    if not invalid:
        print(f"✅ Embeddings: VERIFIED ({valid}/{total})")
    else:
        print(f"❌ Embeddings: FAILED ({valid}/{total})")
        print("\nInvalid files:")
        for f in invalid:
            print(f"  - {f}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Bulk enroll students using InsightFace buffalo_l")
    parser.add_argument("--force",   action="store_true", help="Overwrite existing .pkl files")
    parser.add_argument("--roll",    type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--db",      action="store_true", help="Also write to PostgreSQL")
    parser.add_argument("--verify",  action="store_true", help="Only verify, no enrollment")
    args = parser.parse_args()

    if args.verify:
        verify_embeddings()
        return

    all_photos = get_all_photos()
    if not all_photos:
        print("[ERROR] No photos found. Check PHOTOS_BASE_DIR.")
        return

    if args.roll:
        target     = args.roll.strip().upper()
        all_photos = [(r, p) for r, p in all_photos if r == target]
        if not all_photos:
            print(f"[ERROR] No photo found for {target}")
            return

    print(f"Model     : InsightFace buffalo_l (ArcFace + SCRFD)")
    print(f"Photos    : {PHOTOS_BASE_DIR}")
    print(f"Output    : {EMBEDDINGS_DIR}")
    print(f"Students  : {len(all_photos)}")
    print(f"Force     : {args.force}")
    print(f"Dry run   : {args.dry_run}")
    print(f"Write DB  : {args.db}")
    print()

    if args.dry_run:
        for roll, path in all_photos:
            out    = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")
            status = "EXISTS" if os.path.exists(out) else "NEW"
            print(f"  [{status}] {roll} <- {path}")
        return

    counts = {"enrolled": 0, "skipped": 0, "failed": 0}
    for i, (roll, photo_path) in enumerate(all_photos, 1):
        print(f"[{i:>4}/{len(all_photos)}] {roll} …", end=" ", flush=True)
        result = enroll_student(roll, photo_path, force=args.force, write_db=args.db)
        counts[result] += 1
        print(result.upper())

    print(f"\n=== Done ===")
    print(f"Enrolled : {counts['enrolled']}")
    print(f"Skipped  : {counts['skipped']}  (--force to overwrite)")
    print(f"Failed   : {counts['failed']}")

    verify_embeddings()


if __name__ == "__main__":
    main()