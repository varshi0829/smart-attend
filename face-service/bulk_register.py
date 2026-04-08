"""
SmartAttend — Bulk Student Enrollment Script
Model: ArcFace | Detector: RetinaFace

Photos source: ../2024 Batch Photos/{DEPT}/{ROLL_NUMBER}.jpg
Output:        embeddings/{ROLL_NUMBER}.pkl

Run from face-service/ directory:
    ./venv/bin/python3 bulk_register.py

Options:
    --force    Overwrite existing .pkl files (default: skip already-enrolled)
    --roll     Enroll only one student: --roll 24WH1A0527
    --dry-run  List what would be enrolled without writing files
"""

import os
import sys
import pickle
import argparse
import numpy as np
from deepface import DeepFace

# ── Config (must match face-service/app/config.py) ──────────────────────────
MODEL_NAME       = "ArcFace"
DETECTOR_BACKEND = "retinaface"
PHOTOS_BASE_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "students", "CSE")
EMBEDDINGS_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings")
EXPECTED_DIM     = 512   # ArcFace produces 512-dim embeddings
# ─────────────────────────────────────────────────────────────────────────────

os.makedirs(EMBEDDINGS_DIR, exist_ok=True)


def get_all_photos():
    """
    Walk PHOTOS_BASE_DIR and return list of (roll_number, photo_path).

    Supports two structures automatically:
      1. Flat:    PHOTOS_BASE_DIR/{SECTION}/{ROLL}.jpg
      2. Nested:  PHOTOS_BASE_DIR/{SECTION}/{ROLL}/{ROLL}.jpg  (students/CSE layout)
    """
    photos = []
    if not os.path.exists(PHOTOS_BASE_DIR):
        print(f"[ERROR] Photos directory not found: {PHOTOS_BASE_DIR}")
        return photos

    for root, dirs, files in os.walk(PHOTOS_BASE_DIR):
        dirs.sort()
        for fname in sorted(files):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            roll_from_file   = os.path.splitext(fname)[0].strip().upper()
            roll_from_folder = os.path.basename(root).strip().upper()

            # Nested layout: parent folder name IS the roll number
            # e.g. .../CSE-A/24WH1A0501/24WH1A0501.jpg
            if roll_from_folder == roll_from_file:
                roll = roll_from_file
            # Flat layout: file name IS the roll number
            # e.g. .../CSE/24WH1A0501.jpg
            elif len(roll_from_file) >= 8 and roll_from_file[0].isdigit():
                roll = roll_from_file
            else:
                continue   # skip non-roll-number files

            photos.append((roll, os.path.join(root, fname)))

    return photos


def enroll_student(roll: str, photo_path: str, force: bool = False) -> str:
    """
    Generate ArcFace embedding for one student photo.
    Returns: 'enrolled', 'skipped', or 'failed'
    """
    out_path = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")

    if os.path.exists(out_path) and not force:
        return "skipped"

    try:
        result = DeepFace.represent(
            img_path=photo_path,
            model_name=MODEL_NAME,
            enforce_detection=True,
            detector_backend=DETECTOR_BACKEND
        )
    except Exception as e:
        print(f"  [FAIL] {roll}: DeepFace error — {e}")
        return "failed"

    if not result:
        print(f"  [FAIL] {roll}: no face detected in {os.path.basename(photo_path)}")
        return "failed"

    if len(result) > 1:
        print(f"  [WARN] {roll}: multiple faces detected, using first only")

    embedding = np.array(result[0]["embedding"], dtype=np.float32)

    if embedding.shape != (EXPECTED_DIM,):
        print(f"  [FAIL] {roll}: wrong embedding shape {embedding.shape}, expected ({EXPECTED_DIM},)")
        return "failed"

    # Store as a list (matcher.py supports multiple embeddings per student)
    data = {"studentId": roll, "embeddings": [embedding]}
    with open(out_path, "wb") as f:
        pickle.dump(data, f)

    return "enrolled"


def verify_embeddings():
    """Post-enrollment check: print shape of every .pkl file."""
    print("\n=== Embedding Verification ===")
    issues = []
    for fname in sorted(os.listdir(EMBEDDINGS_DIR)):
        if not fname.endswith(".pkl"):
            continue
        fpath = os.path.join(EMBEDDINGS_DIR, fname)
        with open(fpath, "rb") as f:
            data = pickle.load(f)
        if isinstance(data, dict):
            raw = data.get("embeddings", [data.get("embedding")])
        else:
            raw = data if isinstance(data, list) else [data]
        shapes = [np.array(e, dtype=np.float32).shape for e in raw if e is not None]
        ok = all(s == (EXPECTED_DIM,) for s in shapes)
        status = "OK " if ok else "BAD"
        print(f"  [{status}] {fname:<25} embeddings={len(shapes)} shapes={shapes}")
        if not ok:
            issues.append(fname)
    if issues:
        print(f"\n[WARNING] {len(issues)} file(s) still have wrong shape: {issues}")
    else:
        print(f"\nAll embeddings are {EXPECTED_DIM}-dim ArcFace compatible.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",   action="store_true", help="Overwrite existing .pkl files")
    parser.add_argument("--roll",    type=str, default=None, help="Enroll single roll number only")
    parser.add_argument("--dry-run", action="store_true", help="List what would be done, no writes")
    parser.add_argument("--verify",  action="store_true", help="Only run verification, no enrollment")
    args = parser.parse_args()

    if args.verify:
        verify_embeddings()
        return

    all_photos = get_all_photos()
    if not all_photos:
        print("[ERROR] No photos found. Check PHOTOS_BASE_DIR path.")
        return

    # Filter to single roll if requested
    if args.roll:
        target = args.roll.strip().upper()
        all_photos = [(r, p) for r, p in all_photos if r == target]
        if not all_photos:
            print(f"[ERROR] No photo found for roll number: {target}")
            return

    print(f"Model:     {MODEL_NAME}")
    print(f"Detector:  {DETECTOR_BACKEND}")
    print(f"Photos:    {PHOTOS_BASE_DIR}")
    print(f"Output:    {EMBEDDINGS_DIR}")
    print(f"Students:  {len(all_photos)}")
    print(f"Force:     {args.force}")
    print(f"Dry run:   {args.dry_run}")
    print()

    if args.dry_run:
        for roll, path in all_photos:
            out = os.path.join(EMBEDDINGS_DIR, f"{roll}.pkl")
            status = "EXISTS" if os.path.exists(out) else "NEW"
            print(f"  [{status}] {roll} <- {path}")
        return

    counts = {"enrolled": 0, "skipped": 0, "failed": 0}
    for i, (roll, photo_path) in enumerate(all_photos, 1):
        print(f"[{i:>4}/{len(all_photos)}] {roll} ...", end=" ", flush=True)
        result = enroll_student(roll, photo_path, force=args.force)
        counts[result] += 1
        print(result.upper())

    print(f"\n=== Done ===")
    print(f"Enrolled: {counts['enrolled']}")
    print(f"Skipped:  {counts['skipped']}  (use --force to overwrite)")
    print(f"Failed:   {counts['failed']}")

    verify_embeddings()


if __name__ == "__main__":
    main()
