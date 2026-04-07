#!/usr/bin/env python3
"""
Student Photo Organizer - ALL DEPARTMENTS
Organizes 2nd year (2024 batch) student photos for all departments.
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
TARGET_BATCH = "24"  # 2nd year students

# Supported image extensions
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']

# Department code mapping (from roll number pattern)
# Format: 24WH1A[DEPT_CODE][SECTION][ROLL]
# Examples:
#   24WH1A05XX = CSE (05 = CSE)
#   24WH1A04XX = ECE (04 = ECE)
#   24WH1A02XX = EEE (02 = EEE)
#   24WH1A66XX = AIML (66 = AIML)

DEPT_CODES = {
    '02': 'EEE',
    '04': 'ECE',
    '05': 'CSE',
    '66': 'AIML',
}


def normalize_roll(roll):
    """Normalize roll number: uppercase and strip spaces."""
    return roll.strip().upper() if roll else ""


def extract_dept_and_section(roll_number):
    """
    Extract department and section from roll number.
    Format: 24WH1A[DEPT_CODE][SECTION_NUM][STUDENT_NUM]
    Example: 24WH1A0527 = CSE-A (05=CSE, 2=Section, 7=Student)
    """
    roll = normalize_roll(roll_number)
    
    # Extract department code (positions 6-7)
    if len(roll) >= 8:
        dept_code = roll[6:8]
        dept = DEPT_CODES.get(dept_code, 'UNKNOWN')
        
        # Extract section number (position 8)
        if len(roll) >= 9:
            section_num = roll[8]
            # Map section number to letter (1=A, 2=B, etc.)
            if section_num.isdigit():
                section_letter = chr(ord('A') + int(section_num) - 1)
                section = f"{dept}-{section_letter}"
            else:
                section = f"{dept}-{section_num}"
        else:
            section = dept
        
        return dept, section
    
    return 'UNKNOWN', 'UNKNOWN'


def find_photo(roll_number, source_dir):
    """Find photo for given roll number in source directory."""
    roll_norm = normalize_roll(roll_number)
    
    if not os.path.exists(source_dir):
        return None
    
    # Get all files recursively
    all_files = []
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            all_files.append(os.path.join(root, file))
    
    # Priority 1: Exact filename match
    for ext in IMAGE_EXTENSIONS:
        exact_match = f"{roll_norm}{ext}"
        for file_path in all_files:
            if os.path.basename(file_path) == exact_match:
                return file_path
    
    # Priority 2: Case-insensitive match
    for file_path in all_files:
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext == roll_norm:
            return file_path
    
    # Priority 3: Roll number in filename
    for file_path in all_files:
        filename = os.path.basename(file_path).upper()
        if roll_norm in filename and any(filename.endswith(ext.upper()) for ext in IMAGE_EXTENSIONS):
            return file_path
    
    return None


def load_students_from_csv(csv_path, target_batch):
    """Load students from CSV, grouped by section."""
    students_by_section = defaultdict(list)
    
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                roll = row.get('rollnumber', '').strip()
                section = row.get('section', '').strip().upper()
                name = row.get('name', '').strip()
                
                if roll.startswith(target_batch):
                    students_by_section[section].append({
                        'roll': roll,
                        'name': name,
                        'section': section
                    })
    
    # Sort by roll number
    for section in students_by_section:
        students_by_section[section].sort(key=lambda x: x['roll'])
    
    return students_by_section


def discover_students_from_photos(source_dir, target_batch):
    """Discover students from photo filenames (for departments not in CSV)."""
    students_by_section = defaultdict(list)
    
    if not os.path.exists(source_dir):
        return students_by_section
    
    # Find all image files
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if any(file.upper().endswith(ext.upper()) for ext in IMAGE_EXTENSIONS):
                # Extract roll number from filename
                name_without_ext = os.path.splitext(file)[0]
                roll = normalize_roll(name_without_ext)
                
                # Check if it's target batch
                if roll.startswith(target_batch):
                    dept, section = extract_dept_and_section(roll)
                    
                    # Add to list if not already present
                    if not any(s['roll'] == roll for s in students_by_section[section]):
                        students_by_section[section].append({
                            'roll': roll,
                            'name': 'Unknown',
                            'section': section
                        })
    
    # Sort by roll number
    for section in students_by_section:
        students_by_section[section].sort(key=lambda x: x['roll'])
    
    return students_by_section


def organize_photos():
    """Main function to organize student photos."""
    print("=" * 60)
    print("Student Photo Organizer - ALL DEPARTMENTS (2024 Batch)")
    print("=" * 60)
    print()
    
    if not os.path.exists(SOURCE_PHOTOS):
        print(f"❌ Error: Source folder not found: {SOURCE_PHOTOS}")
        return
    
    print(f"📂 Source: {SOURCE_PHOTOS}")
    print(f"📄 CSV: {CSV_FILE}")
    print(f"📁 Output: {OUTPUT_BASE}")
    print()
    
    # Load students from CSV
    print("Loading students from CSV...")
    csv_students = load_students_from_csv(CSV_FILE, TARGET_BATCH)
    
    # Discover students from photos
    print("Discovering students from photos...")
    photo_students = discover_students_from_photos(SOURCE_PHOTOS, TARGET_BATCH)
    
    # Merge both sources (CSV takes priority for names)
    all_students = defaultdict(list)
    
    # Add CSV students
    for section, students in csv_students.items():
        all_students[section].extend(students)
    
    # Add photo-discovered students (if not in CSV)
    csv_rolls = set()
    for students in csv_students.values():
        csv_rolls.update(s['roll'] for s in students)
    
    for section, students in photo_students.items():
        for student in students:
            if student['roll'] not in csv_rolls:
                all_students[section].append(student)
    
    # Sort each section
    for section in all_students:
        all_students[section].sort(key=lambda x: x['roll'])
    
    total_students = sum(len(students) for students in all_students.values())
    print(f"✓ Found {total_students} students in {len(all_students)} sections")
    print()
    
    # Statistics
    stats = {
        'processed': 0,
        'copied': 0,
        'missing': 0,
        'missing_list': []
    }
    
    # Process each section
    for section in sorted(all_students.keys()):
        students = all_students[section]
        print(f"📋 Processing Section: {section} ({len(students)} students)")
        print("-" * 60)
        
        for student in students:
            roll = student['roll']
            name = student['name']
            stats['processed'] += 1
            
            # Find photo
            photo_path = find_photo(roll, SOURCE_PHOTOS)
            
            if photo_path:
                # Extract department from section (e.g., "CSE-A" -> "CSE")
                dept = section.split('-')[0] if '-' in section else section
                
                # Create output directory: dept/section/roll
                output_dir = os.path.join(OUTPUT_BASE, dept, section, roll)
                os.makedirs(output_dir, exist_ok=True)
                
                # Copy and rename photo
                output_file = os.path.join(output_dir, f"{roll}.jpg")
                shutil.copy2(photo_path, output_file)
                
                stats['copied'] += 1
                print(f"  ✓ {roll} ({name[:30]:30s}) → {dept}/{section}/{roll}/")
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
