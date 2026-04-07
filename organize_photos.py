#!/usr/bin/env python3
"""
Student Photo Organizer
Organizes 2nd year (2024 batch) student photos by section from CSV data.
"""

import os
import csv
import shutil
from pathlib import Path
from collections import defaultdict

# Configuration
SOURCE_PHOTOS = "/home/cse/smart-attend/2024 Batch Photos"
CSV_FILE = "/home/cse/smart-attend/backend/students.csv"
OUTPUT_BASE = "/home/cse/smart-attend/students"
TARGET_BATCH = "24"  # 2nd year students (roll numbers start with 24)

# Supported image extensions
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']


def normalize_roll(roll):
    """Normalize roll number: uppercase and strip spaces."""
    return roll.strip().upper() if roll else ""


def find_photo(roll_number, source_dir):
    """
    Find photo for given roll number in source directory.
    Priority: exact match > case-insensitive match > first valid image
    """
    roll_norm = normalize_roll(roll_number)
    
    # Check if source directory exists
    if not os.path.exists(source_dir):
        return None
    
    # Get all files in source directory (including subdirectories)
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
    
    # Priority 1: Exact filename match (any extension)
    for ext in IMAGE_EXTENSIONS:
        exact_match = f"{roll_norm}{ext}"
        for file_path in all_files:
            if os.path.basename(file_path) == exact_match:
                return file_path
    
    # Priority 2: Case-insensitive match in filename
    for file_path in all_files:
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext == roll_norm:
            return file_path
    
    # Priority 3: Roll number appears in filename
    for file_path in all_files:
        filename = os.path.basename(file_path).upper()
        if roll_norm in filename and any(filename.endswith(ext.upper()) for ext in IMAGE_EXTENSIONS):
            return file_path
    
    return None


def load_students_from_csv(csv_path, target_batch):
    """Load 2nd year students from CSV, grouped by section."""
    students_by_section = defaultdict(list)
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            roll = row.get('rollnumber', '').strip()
            section = row.get('section', '').strip().upper()
            name = row.get('name', '').strip()
            
            # Filter for 2024 batch (2nd year)
            if roll.startswith(target_batch):
                students_by_section[section].append({
                    'roll': roll,
                    'name': name,
                    'section': section
                })
    
    # Sort students by roll number within each section
    for section in students_by_section:
        students_by_section[section].sort(key=lambda x: x['roll'])
    
    return students_by_section


def organize_photos():
    """Main function to organize student photos."""
    print("=" * 60)
    print("Student Photo Organizer - 2nd Year (2024 Batch)")
    print("=" * 60)
    print()
    
    # Validate paths
    if not os.path.exists(SOURCE_PHOTOS):
        print(f"❌ Error: Source folder not found: {SOURCE_PHOTOS}")
        return
    
    if not os.path.exists(CSV_FILE):
        print(f"❌ Error: CSV file not found: {CSV_FILE}")
        return
    
    print(f"📂 Source: {SOURCE_PHOTOS}")
    print(f"📄 CSV: {CSV_FILE}")
    print(f"📁 Output: {OUTPUT_BASE}")
    print()
    
    # Load students from CSV
    print("Loading students from CSV...")
    students_by_section = load_students_from_csv(CSV_FILE, TARGET_BATCH)
    
    total_students = sum(len(students) for students in students_by_section.values())
    print(f"✓ Found {total_students} students in {len(students_by_section)} sections")
    print()
    
    # Statistics
    stats = {
        'processed': 0,
        'copied': 0,
        'missing': 0,
        'missing_list': []
    }
    
    # Process each section
    for section in sorted(students_by_section.keys()):
        students = students_by_section[section]
        print(f"📋 Processing Section: {section} ({len(students)} students)")
        print("-" * 60)
        
        for student in students:
            roll = student['roll']
            name = student['name']
            stats['processed'] += 1
            
            # Find photo
            photo_path = find_photo(roll, SOURCE_PHOTOS)
            
            if photo_path:
                # Create output directory structure
                output_dir = os.path.join(OUTPUT_BASE, section, roll)
                os.makedirs(output_dir, exist_ok=True)
                
                # Copy and rename photo
                output_file = os.path.join(output_dir, f"{roll}.jpg")
                shutil.copy2(photo_path, output_file)
                
                stats['copied'] += 1
                print(f"  ✓ {roll} ({name[:30]:30s}) → {section}/{roll}/")
            else:
                stats['missing'] += 1
                stats['missing_list'].append((roll, name, section))
                print(f"  ✗ {roll} ({name[:30]:30s}) → PHOTO NOT FOUND")
        
        print()
    
    # Print summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total Students Processed: {stats['processed']}")
    print(f"Photos Copied:            {stats['copied']}")
    print(f"Photos Missing:           {stats['missing']}")
    print()
    
    if stats['missing_list']:
        print("Missing Photos:")
        print("-" * 60)
        for roll, name, section in stats['missing_list']:
            print(f"  {roll:15s} {name[:30]:30s} ({section})")
        print()
    
    print(f"✓ Output directory: {OUTPUT_BASE}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        organize_photos()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
