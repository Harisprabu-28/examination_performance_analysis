import os
import glob
import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash
from config import Config
from database import init_db, get_db_connection, calculate_exam_metrics

EXPECTED_COLUMNS = [
    'S.No',
    'Register No.',
    'Student Name',
    'Mobile No.',
    'Email ID',
    'Department',
    'Section',
    'Mathematics Mark',
    'English Mark',
    'Science Mark',
    'Computer Science Mark',
    'Database Management System Mark',
    'Web Technologies Mark'
]

SUBJECT_COLUMNS = [
    'Mathematics Mark',
    'English Mark',
    'Science Mark',
    'Computer Science Mark',
    'Database Management System Mark',
    'Web Technologies Mark'
]

def find_dataset_file():
    """Locates the Excel file in the project directory."""
    project_dir = Config.BASE_DIR
    target_filename = "IT_STUDENTS_DATASET.xlsx"
    target_path = os.path.join(project_dir, target_filename)
    
    if os.path.exists(target_path):
        return target_path
        
    xlsx_files = glob.glob(os.path.join(project_dir, "*.xlsx"))
    for f in xlsx_files:
        try:
            excel = pd.ExcelFile(f)
            if 'Student Dataset' in excel.sheet_names:
                return f
        except Exception:
            continue
            
    return None

def import_excel_dataset():
    """Imports 123 student records and marks from Excel into configured database (MySQL or SQLite)."""
    if Config.DB_TYPE == 'mysql':
        from import_mysql_dataset import import_mysql_dataset
        return import_mysql_dataset()

    print("=" * 65)
    print("REAL CLASS STUDENT DATASET IMPORT PROCESS (SQLite)")
    print("=" * 65)
    
    excel_path = find_dataset_file()
    if not excel_path:
        print("[!] ERROR: Real student dataset Excel file not found!")
        return False
        
    print(f"[*] Found Dataset File: {os.path.basename(excel_path)}")
    
    # Read Excel sheet
    try:
        df = pd.read_excel(excel_path, sheet_name='Student Dataset')
    except Exception as e:
        print(f"[!] ERROR: Failed to read 'Student Dataset' sheet: {e}")
        return False
        
    print(f"[*] Read {len(df)} rows from Excel sheet 'Student Dataset'.")
    
    # Validate Columns
    missing_cols = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    if missing_cols:
        print(f"[!] ERROR: Missing expected columns: {missing_cols}")
        return False
    print("[+] Column verification passed successfully.")
    
    # Ensure tables exist
    init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check for demo student records to purge (e.g. REG2024001..25)
    # We will purge students who are not in the real dataset
    excel_reg_numbers = set(df['Register No.'].astype(str).str.strip().str.upper())
    
    cursor.execute("SELECT id, register_number FROM students")
    db_students = cursor.fetchall()
    demo_students_to_remove = [s['id'] for s in db_students if s['register_number'].upper() not in excel_reg_numbers]
    
    if demo_students_to_remove:
        placeholders = ', '.join('?' for _ in demo_students_to_remove)
        cursor.execute(f"DELETE FROM marks WHERE student_id IN ({placeholders})", demo_students_to_remove)
        cursor.execute(f"DELETE FROM predictions WHERE student_id IN ({placeholders})", demo_students_to_remove)
        cursor.execute(f"DELETE FROM students WHERE id IN ({placeholders})", demo_students_to_remove)
        print(f"[*] Purged {len(demo_students_to_remove)} demo student records from database.")
        
    default_pwd_hash = generate_password_hash(Config.DEFAULT_STUDENT_PASSWORD)
    exam_name = "CIA 1 Examination"
    exam_type = "CIA1"
    academic_year = "2025-2026"
    
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    duplicate_rows = 0
    invalid_rows = 0
    
    seen_in_batch = set()
    
    for idx, row in df.iterrows():
        row_num = idx + 2 # Header is row 1 in Excel
        
        reg_no = str(row['Register No.']).strip().upper() if pd.notna(row['Register No.']) else ""
        name = str(row['Student Name']).strip() if pd.notna(row['Student Name']) else ""
        phone = str(row['Mobile No.']).split('.')[0].strip() if pd.notna(row['Mobile No.']) else ""
        email = str(row['Email ID']).strip() if pd.notna(row['Email ID']) else ""
        dept = str(row['Department']).strip() if pd.notna(row['Department']) else "Information Technology"
        sec = str(row['Section']).strip() if pd.notna(row['Section']) else "A"
        
        # Row Validation
        if not reg_no or reg_no == "NAN":
            print(f"[!] Row {row_num}: Missing Register Number. Skipped.")
            invalid_rows += 1
            skipped_count += 1
            continue
            
        if not name or name == "NAN":
            print(f"[!] Row {row_num}: Missing Student Name for Register No {reg_no}. Skipped.")
            invalid_rows += 1
            skipped_count += 1
            continue
            
        # Check duplicate within this batch
        if reg_no in seen_in_batch:
            print(f"[!] Row {row_num}: Duplicate Register No {reg_no} in Excel batch. Skipped.")
            duplicate_rows += 1
            skipped_count += 1
            continue
        seen_in_batch.add(reg_no)
        
        # Validate marks
        valid_marks = True
        marks = {}
        for sub_col in SUBJECT_COLUMNS:
            val = row[sub_col]
            try:
                score = float(val)
                if score < 0 or score > 100:
                    print(f"[!] Row {row_num}: Invalid mark {score} for {sub_col}. Must be 0-100.")
                    valid_marks = False
                    break
                marks[sub_col] = score
            except (ValueError, TypeError):
                print(f"[!] Row {row_num}: Non-numeric mark '{val}' for {sub_col}.")
                valid_marks = False
                break
                
        if not valid_marks:
            invalid_rows += 1
            skipped_count += 1
            continue
            
        math_score = marks['Mathematics Mark']
        eng_score = marks['English Mark']
        sci_score = marks['Science Mark']
        cs_score = marks['Computer Science Mark']
        db_score = marks['Database Management System Mark']
        web_score = marks['Web Technologies Mark']
        
        total, avg, perc, grade, result = calculate_exam_metrics(
            math_score, eng_score, sci_score, cs_score, db_score, web_score
        )
        
        # Check if student exists in database
        cursor.execute("SELECT id FROM students WHERE register_number = ?", (reg_no,))
        existing_student = cursor.fetchone()
        
        if existing_student:
            student_id = existing_student['id']
            cursor.execute('''
                UPDATE students 
                SET name = ?, email = ?, phone = ?, department = ?, section = ?
                WHERE id = ?
            ''', (name, email, phone, dept, sec, student_id))
            updated_count += 1
        else:
            cursor.execute('''
                INSERT INTO students (
                    register_number, name, email, phone, department, 
                    year, semester, section, date_of_birth, gender, password_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (reg_no, name, email, phone, dept, "3rd Year", "VI Semester", sec, "2003-01-01", "Not Specified", default_pwd_hash))
            student_id = cursor.lastrowid
            imported_count += 1
            
        # Insert or update CIA 1 marks record
        cursor.execute("SELECT id FROM marks WHERE student_id = ? AND (exam_type = 'CIA1' OR exam_name = ?)", (student_id, exam_name))
        existing_mark = cursor.fetchone()
        
        if existing_mark:
            cursor.execute('''
                UPDATE marks SET
                    exam_name = ?, exam_type = ?, academic_year = ?, mathematics = ?, english = ?, science = ?,
                    computer_science = ?, database_management = ?, web_technology = ?,
                    total_marks = ?, average = ?, percentage = ?, grade = ?, result = ?
                WHERE id = ?
            ''', (exam_name, exam_type, academic_year, math_score, eng_score, sci_score, cs_score, db_score, web_score,
                  total, avg, perc, grade, result, existing_mark['id']))
        else:
            cursor.execute('''
                INSERT INTO marks (
                    student_id, exam_name, exam_type, academic_year,
                    mathematics, english, science, computer_science, database_management, web_technology,
                    total_marks, average, percentage, grade, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, exam_name, exam_type, academic_year, math_score, eng_score, sci_score, cs_score, db_score, web_score,
                  total, avg, perc, grade, result))
                  
    conn.commit()
    
    # Verify final counts
    cursor.execute("SELECT COUNT(*) as c FROM students")
    total_db_students = cursor.fetchone()['c']
    
    cursor.execute("SELECT COUNT(*) as c FROM marks")
    total_db_marks = cursor.fetchone()['c']
    
    conn.close()
    
    print("\n" + "=" * 65)
    print("DATASET IMPORT SUMMARY REPORT")
    print("=" * 65)
    print(f"Total Rows in Excel File   : {len(df)}")
    print(f"Newly Imported Students    : {imported_count}")
    print(f"Updated Existing Students  : {updated_count}")
    print(f"Skipped / Invalid Rows     : {skipped_count}")
    print(f"Duplicate Register Numbers : {duplicate_rows}")
    print(f"Invalid Rows               : {invalid_rows}")
    print(f"Total Students in Database : {total_db_students}")
    print(f"Total Exam Records in DB   : {total_db_marks}")
    print("=" * 65)
    
    return True

if __name__ == '__main__':
    import_excel_dataset()
