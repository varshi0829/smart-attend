from docx import Document
import csv
import re

doc = Document('/home/cse/smart-attend/Faculty/ECE/2025-26-I SEM-Faculty workload-V2 (1).docx')
table = doc.tables[0]

output_rows = []

for row in table.rows[1:]:
    cells = [c.text.strip() for c in row.cells]
    s_no, name, designation = cells[0], cells[1], cells[2]
    theory1, theory2 = cells[3], cells[4]
    lab1, lab2 = cells[5], cells[6]
    
    # Clean name
    name_clean = re.sub(r'\[.*?\]', '', name).replace('\n', ' ').strip()
    name_normalized = name_clean.lower()
    if not name_clean:
        continue
    
    # Parse class assignments
    for class_str, class_type in [(theory1, 'Theory'), (theory2, 'Theory'), (lab1, 'Lab'), (lab2, 'Lab')]:
        if not class_str:
            continue
        
        lines = class_str.replace('\n', ' ').split()
        lines = [l for l in lines if l]
        
        if len(lines) >= 2:
            subject_code = lines[0]
            subject_acronym = lines[0]
            class_info = ' '.join(lines[1:])
            
            # Parse year
            year = 1
            semester = 1
            if 'IV' in class_info:
                year = 4
                semester = 7
            elif 'III' in class_info:
                year = 3
                semester = 5
            elif 'II' in class_info:
                year = 2
                semester = 3
            elif 'I ' in class_info or class_info.startswith('I '):
                year = 1
                semester = 1
            
            # Parse section
            section = ''
            section_match = re.search(r'([A-Z])\s*$', class_info)
            if section_match:
                section = section_match.group(1)
            
            # class_str for reference
            class_str_ref = f"{year} ECE {section}" if section else f"{year} ECE"
            
            output_rows.append({
                'teacher_name': name_clean,
                'teacher_name_normalized': name_normalized,
                'department': 'ECE',
                'year': year,
                'semester': semester,
                'section': section,
                'subject_code': subject_code,
                'subject_acronym': subject_acronym,
                'subject_name': subject_code,
                'class_type': class_type,
                'class_str': class_str_ref,
                'source_confidence': 'medium',
                'source_notes': 'extracted from workload docx'
            })

# Write CSV matching CSE format
csv_path = '/home/cse/smart-attend/Faculty/ECE/faculty_class_assignments.csv'
fieldnames = ['teacher_name', 'teacher_name_normalized', 'department', 'year', 'semester', 
            'section', 'subject_code', 'subject_acronym', 'subject_name', 'class_type', 
            'class_str', 'source_confidence', 'source_notes']

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(output_rows)

print(f"Wrote {len(output_rows)} assignments")
print(f"CSV: {csv_path}")

# Show unique teachers
teachers = set(r['teacher_name'] for r in output_rows)
print(f"Unique teachers: {len(teachers)}")