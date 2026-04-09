import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
import os
import math

# DB Connection
DB_DSN = "postgresql://cse:cse@localhost:5432/smartattend_db"

def clean_value(val):
    """Convert NaN/None to None for PostgreSQL compatibility"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    return str(val).strip() if val else None

def normalize_name(name):
    """Normalize teacher name: trim whitespace for comparison"""
    if name is None:
        return None
    return name.strip()

def import_students(csv_path, department):
    """Import students from CSV"""
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    print(f"Importing {department} students...")
    students_df = pd.read_csv(csv_path)
    student_data = []
    for _, row in students_df.iterrows():
        roll = row['rollnumber']
        name = row['name']
        email = row['email']
        section = row['section']
        # Infer year from roll number (24WH1A05 -> 1st year)
        year = 1
        student_data.append((roll, name, email, department, year, section))

    execute_values(cur, 
        "INSERT INTO students (roll_number, name, email, department, year, section) VALUES %s ON CONFLICT (roll_number) DO UPDATE SET name=EXCLUDED.name, email=EXCLUDED.email, section=EXCLUDED.section",
        student_data)
    print(f"Imported {len(student_data)} {department} students.")
    
    conn.commit()
    cur.close()
    conn.close()

def import_teachers_assignments(csv_path, department):
    """Import teachers and assignments from CSV"""
    conn = psycopg2.connect(DB_DSN)
    cur = conn.cursor()
    
    print(f"Importing {department} teachers...")
    assignments_df = pd.read_csv(csv_path)
    
    # Get unique teacher names from source
    teacher_names = assignments_df['teacher_name'].drop_duplicates().tolist()
    teacher_inserted = 0
    teacher_reused = 0
    teacher_map = {}
    
    for t_name in teacher_names:
        normalized = normalize_name(t_name)
        cur.execute("SELECT teacher_id FROM teachers WHERE LOWER(TRIM(name)) = LOWER(%s)", (normalized,))
        res = cur.fetchone()
        if res:
            teacher_id = res[0]
            teacher_reused += 1
        else:
            dept_row = assignments_df[assignments_df['teacher_name'] == t_name].iloc[0]
            dept = clean_value(dept_row['department'])
            cur.execute("INSERT INTO teachers (name, department, role) VALUES (%s, %s, 'teacher') RETURNING teacher_id", (normalized, dept))
            teacher_id = cur.fetchone()[0]
            teacher_inserted += 1
        teacher_map[normalized] = teacher_id

    print(f"{department} Teachers: {teacher_inserted} inserted, {teacher_reused} reused")

    # Import Assignments
    print(f"Importing {department} assignments...")
    assignment_set = set()
    for _, row in assignments_df.iterrows():
        t_name = normalize_name(row['teacher_name'])
        dept = clean_value(row['department'])
        year = row['year']
        section = clean_value(row['section'])
        subject = clean_value(row['subject_name'])
        code = clean_value(row['subject_code'])
        ctype = clean_value(row['class_type'])
        
        teacher_id = teacher_map.get(t_name)
        if not teacher_id:
            continue
        
        assignment_set.add((teacher_id, dept, year, section, subject, code, ctype))
    
    assignment_data = list(assignment_set)
    
    for row in assignment_data:
        teacher_id, dept, year, section, subject, code, ctype = row
        cur.execute("""
            SELECT 1 FROM faculty_class_assignments 
            WHERE teacher_id = %s AND department = %s AND year = %s 
            AND (section = %s OR (section IS NULL AND %s IS NULL)) 
            AND (subject = %s OR (subject IS NULL AND %s IS NULL)) 
            AND (course_code = %s OR (course_code IS NULL AND %s IS NULL)) 
            AND (class_type = %s OR (class_type IS NULL AND %s IS NULL))
        """, (teacher_id, dept, year, section, section, subject, subject, code, code, ctype, ctype))
        
        if cur.fetchone():
            continue
        
        cur.execute("""
            INSERT INTO faculty_class_assignments 
            (teacher_id, department, year, section, subject, course_code, class_type) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (teacher_id, dept, year, section, subject, code, ctype))

    print(f"{department} Assignments: {len(assignment_data)} unique rows")

    conn.commit()
    cur.close()
    conn.close()

def import_data():
    # Import CSE students
    import_students('backend/students_csv/students_cse.csv', 'CSE')
    
    # Import ECE students
    import_students('backend/students_csv/students_ece.csv', 'ECE')
    
    # Import CSE faculty/assignments (if CSV exists)
    if os.path.exists('Faculty/CSE/faculty_class_assignments.csv'):
        import_teachers_assignments('Faculty/CSE/faculty_class_assignments.csv', 'CSE')
    
    # Import ECE faculty/assignments (if CSV exists)
    if os.path.exists('Faculty/ECE/faculty_class_assignments.csv'):
        import_teachers_assignments('Faculty/ECE/faculty_class_assignments.csv', 'ECE')
    
    print("\nImport complete!")

if __name__ == "__main__":
    import_data()