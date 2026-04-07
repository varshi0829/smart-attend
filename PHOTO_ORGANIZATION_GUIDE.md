# Photo Organization Script - Usage Guide

## Overview
This script organizes 2nd year (2024 batch) student photos into a structured directory by section and roll number.

---

## What It Does

### Input:
- **Source Photos:** `/home/cse/smart-attend/2024 Batch Photos/`
- **Student Data:** `/home/cse/smart-attend/backend/students.csv`

### Output:
Creates organized structure at `/home/cse/smart-attend/students/`:
```
students/
├── CSE-A/
│   ├── 24WH1A0501/
│   │   └── 24WH1A0501.jpg
│   ├── 24WH1A0502/
│   │   └── 24WH1A0502.jpg
│   └── ...
├── CSE-B/
│   └── ...
└── CSE-F/
    └── ...
```

---

## Matching Logic

1. **Normalize Roll Numbers:** Uppercase, trim spaces
2. **Search Priority:**
   - Exact match: `24WH1A0527.jpg`
   - Case-insensitive: `24wh1a0527.JPG`
   - Partial match: `24WH1A0527_photo.png`
3. **Copy & Rename:** All photos renamed to `{ROLLNUMBER}.jpg`
4. **Sort:** Students processed in roll number order within each section

---

## How to Run

### Basic Usage:
```bash
cd /home/cse/smart-attend
python3 organize_photos.py
```

### Expected Output:
```
============================================================
Student Photo Organizer - 2nd Year (2024 Batch)
============================================================

📂 Source: /home/cse/smart-attend/2024 Batch Photos
📄 CSV: /home/cse/smart-attend/backend/students.csv
📁 Output: /home/cse/smart-attend/students

Loading students from CSV...
✓ Found 378 students in 6 sections

📋 Processing Section: CSE-A (66 students)
------------------------------------------------------------
  ✓ 24WH1A0501 (SAJJA LAKSHMI RAJYAM        ) → CSE-A/24WH1A0501/
  ✓ 24WH1A0502 (JADAV SRIHARSHA             ) → CSE-A/24WH1A0502/
  ...

============================================================
SUMMARY
============================================================
Total Students Processed: 378
Photos Copied:            377
Photos Missing:           1

Missing Photos:
------------------------------------------------------------
  24WH1A05M5      KALPANA G                      (CSE-D)

✓ Output directory: /home/cse/smart-attend/students
============================================================
```

---

## Features

### ✅ Safe Operation
- **Copies** files (never deletes originals)
- Creates directories automatically
- Handles missing photos gracefully

### ✅ Robust Matching
- Case-insensitive filename matching
- Supports multiple image formats: `.jpg`, `.jpeg`, `.png`, `.JPG`, `.JPEG`, `.PNG`
- Searches recursively in source folder

### ✅ Organized Output
- Section-wise folders (CSE-A, CSE-B, etc.)
- Individual student folders by roll number
- Consistent naming: `{ROLLNUMBER}.jpg`

### ✅ Detailed Reporting
- Progress for each student
- Missing photos list
- Final summary statistics

---

## Verification

### Check Output Structure:
```bash
ls /home/cse/smart-attend/students/
# Output: CSE-A  CSE-B  CSE-C  CSE-D  CSE-E  CSE-F

ls /home/cse/smart-attend/students/CSE-A/ | head -5
# Output: 24WH1A0501  24WH1A0502  24WH1A0503  24WH1A0504  24WH1A0505

ls /home/cse/smart-attend/students/CSE-A/24WH1A0527/
# Output: 24WH1A0527.jpg
```

### Count Photos:
```bash
find /home/cse/smart-attend/students -name "*.jpg" | wc -l
# Output: 377 (number of photos copied)
```

---

## Configuration

Edit these variables in `organize_photos.py` if needed:

```python
SOURCE_PHOTOS = "/home/cse/smart-attend/2024 Batch Photos"
CSV_FILE = "/home/cse/smart-attend/backend/students.csv"
OUTPUT_BASE = "/home/cse/smart-attend/students"
TARGET_BATCH = "24"  # Roll numbers starting with "24"
```

---

## Troubleshooting

### No students found:
- Check `TARGET_BATCH` matches roll number prefix
- Verify CSV file exists and has correct format

### Photos not found:
- Check source folder path
- Verify photo filenames match roll numbers
- Check file extensions are supported

### Permission errors:
- Ensure write permissions on output directory
- Run with appropriate user permissions

---

## Test Results

**Latest Run:**
- **Total Students:** 378
- **Photos Copied:** 377 (99.7% success)
- **Missing Photos:** 1 (24WH1A05M5)
- **Sections:** 6 (CSE-A through CSE-F)

---

## Notes

- **Batch Focus:** Currently processes only 2024 batch (2nd year)
- **Safe:** Original photos remain untouched
- **Idempotent:** Can be run multiple times safely
- **Fast:** Processes 378 students in ~2 seconds

---

## Future Enhancements

To organize other years, modify `TARGET_BATCH`:
- 1st year (2025 batch): `TARGET_BATCH = "25"`
- 3rd year (2023 batch): `TARGET_BATCH = "23"`
- 4th year (2022 batch): `TARGET_BATCH = "22"`
