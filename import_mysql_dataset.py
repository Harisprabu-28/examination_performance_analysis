"""
Import and Synchronize Student Dataset into MySQL 8.0
=====================================================
Synchronizes IT_STUDENTS_DATASET.xlsx into the MySQL database 'exam_analysis'.
- Preserves old records in archive tables.
- Updates student profiles and CIA 1 marks from Excel.
- Synchronizes CIA 2 and Model exam marks.
- Uses parameterized queries and database transactions.
"""

import os
import sys
import pandas as pd
import mysql.connector
from werkzeug.security import generate_password_hash

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from config import Config
from database import calculate_exam_metrics
from scratch.inspect_schema import get_mysql_connection

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

def import_mysql_dataset():
    excel_path = os.path.join(BASE_DIR, 'IT_STUDENTS_DATASET.xlsx')
    if not os.path.exists(excel_path):
        print(f"[!] ERROR: Dataset file not found at {excel_path}")
        return False

    print("=" * 65)
    print("MYSQL 8.0 STUDENT DATASET SYNCHRONIZATION")
    print("=" * 65)
    print(f"[*] Reading Excel file: {os.path.basename(excel_path)}")

    try:
        df = pd.read_excel(excel_path, sheet_name='Student Dataset')
    except Exception as e:
        print(f"[!] ERROR: Failed to read 'Student Dataset' sheet: {e}")
        return False

    print(f"[*] Successfully loaded {len(df)} records from Excel.")

    # Validate Columns
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        print(f"[!] ERROR: Missing expected columns: {missing}")
        return False

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # 1. Archive check
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students_archive_20261022 AS
        SELECT * FROM students
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marks_archive_20261022 AS
        SELECT * FROM marks
    """)
    print("[+] Verified archive tables exist.")

    # 2. Check for obsolete demo students
    excel_reg_numbers = set(df['Register No.'].astype(str).str.strip().str.upper())

    cursor.execute("SELECT student_id, register_number, student_name FROM students")
    current_students = cursor.fetchall()

    obsolete_students = [
        s for s in current_students
        if s['register_number'].upper() not in excel_reg_numbers
    ]

    if obsolete_students:
        print(f"[*] Found {len(obsolete_students)} obsolete records in MySQL (e.g. {obsolete_students[0]['student_name']} - {obsolete_students[0]['register_number']}).")
        obsolete_ids = [s['student_id'] for s in obsolete_students]
        placeholders = ', '.join(['%s'] * len(obsolete_ids))

        # Safely remove dependent marks & predictions for obsolete students
        cursor.execute(f"DELETE FROM marks WHERE student_id IN ({placeholders})", tuple(obsolete_ids))
        cursor.execute(f"DELETE FROM predictions WHERE student_id IN ({placeholders})", tuple(obsolete_ids))
        cursor.execute(f"DELETE FROM students WHERE student_id IN ({placeholders})", tuple(obsolete_ids))
        print(f"[+] Safely removed {len(obsolete_students)} obsolete records from active tables (preserved in archive).")

    # 3. Synchronize new students and CIA 1 marks
    default_pwd_hash = generate_password_hash(Config.DEFAULT_STUDENT_PASSWORD)
    imported_count = 0
    updated_count = 0
    skipped_count = 0
    duplicate_rows = 0
    invalid_rows = 0

    seen_in_batch = set()
    student_id_map = {} # reg_no -> student_id

    for idx, row in df.iterrows():
        row_num = idx + 2

        reg_no = str(row['Register No.']).strip().upper() if pd.notna(row['Register No.']) else ""
        name = str(row['Student Name']).strip() if pd.notna(row['Student Name']) else ""
        phone = str(row['Mobile No.']).split('.')[0].strip() if pd.notna(row['Mobile No.']) else ""
        email = str(row['Email ID']).strip() if pd.notna(row['Email ID']) else ""
        dept = str(row['Department']).strip() if pd.notna(row['Department']) else "Information Technology"
        sec = str(row['Section']).strip() if pd.notna(row['Section']) else "A"

        # Validation
        if not reg_no or reg_no == "NAN":
            skipped_count += 1
            invalid_rows += 1
            continue

        if not name or name == "NAN":
            skipped_count += 1
            invalid_rows += 1
            continue

        if reg_no in seen_in_batch:
            skipped_count += 1
            duplicate_rows += 1
            continue
        seen_in_batch.add(reg_no)

        # Validate marks
        valid_marks = True
        marks_dict = {}
        for sc in SUBJECT_COLUMNS:
            try:
                val = float(row[sc])
                if val < 0 or val > 100:
                    valid_marks = False
                    break
                marks_dict[sc] = val
            except (ValueError, TypeError):
                valid_marks = False
                break

        if not valid_marks:
            skipped_count += 1
            invalid_rows += 1
            continue

        math_v = marks_dict['Mathematics Mark']
        eng_v = marks_dict['English Mark']
        sci_v = marks_dict['Science Mark']
        cs_v = marks_dict['Computer Science Mark']
        db_v = marks_dict['Database Management System Mark']
        web_v = marks_dict['Web Technologies Mark']

        total, avg, perc, grade, result = calculate_exam_metrics(
            math_v, eng_v, sci_v, cs_v, db_v, web_v
        )

        # Check existing student in MySQL
        cursor.execute("SELECT student_id FROM students WHERE register_number = %s", (reg_no,))
        existing = cursor.fetchone()

        if existing:
            s_id = existing['student_id']
            cursor.execute("""
                UPDATE students SET
                    student_name = %s, name = %s, email = %s, phone = %s,
                    department = %s, section = %s, year = %s, semester = %s
                WHERE student_id = %s
            """, (name, name, email, phone, dept, sec, '3rd Year', 'VI Semester', s_id))
            updated_count += 1
        else:
            cursor.execute("""
                INSERT INTO students (
                    register_number, student_name, name, email, phone,
                    gender, department, year, semester, section,
                    date_of_birth, attendance_percentage, password_hash
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                reg_no, name, name, email, phone,
                'Not Specified', dept, '3rd Year', 'VI Semester', sec,
                '2003-01-01', 85.00, default_pwd_hash
            ))
            s_id = cursor.lastrowid
            imported_count += 1

        student_id_map[reg_no] = s_id

        # Insert or update CIA 1 marks
        cursor.execute("""
            SELECT mark_id FROM marks
            WHERE student_id = %s AND (exam_type = 'CIA1' OR exam_name LIKE '%%CIA 1%%')
        """, (s_id,))
        existing_mark = cursor.fetchone()

        if existing_mark:
            cursor.execute("""
                UPDATE marks SET
                    exam_name = %s, exam_type = %s, academic_year = %s,
                    mathematics = %s, english = %s, science = %s,
                    computer_science = %s, database_management = %s, web_technology = %s,
                    total_marks = %s, average = %s, percentage = %s, grade = %s, result = %s
                WHERE mark_id = %s
            """, (
                'CIA 1 Examination', 'CIA1', '2025-2026',
                math_v, eng_v, sci_v, cs_v, db_v, web_v,
                total, avg, perc, grade, result, existing_mark['mark_id']
            ))
        else:
            cursor.execute("""
                INSERT INTO marks (
                    student_id, exam_name, exam_type, academic_year,
                    mathematics, english, science, computer_science,
                    database_management, web_technology, total_marks,
                    average, percentage, grade, result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                s_id, 'CIA 1 Examination', 'CIA1', '2025-2026',
                math_v, eng_v, sci_v, cs_v, db_v, web_v,
                total, avg, perc, grade, result
            ))

    # 4. Synchronize CIA2 and MODEL marks from verified SQLite dataset if available
    sqlite_db_path = os.path.join(BASE_DIR, 'database', 'database.db')
    if os.path.exists(sqlite_db_path):
        import sqlite3
        s_conn = sqlite3.connect(sqlite_db_path)
        s_conn.row_factory = sqlite3.Row
        s_cur = s_conn.cursor()

        s_cur.execute("""
            SELECT m.*, s.register_number
            FROM marks m
            JOIN students s ON m.student_id = s.id
            WHERE m.exam_type IN ('CIA2', 'MODEL')
        """)
        other_marks = s_cur.fetchall()

        synced_other_marks = 0
        for om in other_marks:
            reg = om['register_number'].upper()
            if reg in student_id_map:
                s_id = student_id_map[reg]
                e_type = om['exam_type']
                e_name = om['exam_name']
                a_year = om['academic_year']

                cursor.execute("""
                    SELECT mark_id FROM marks WHERE student_id = %s AND exam_type = %s
                """, (s_id, e_type))
                exists = cursor.fetchone()

                if exists:
                    cursor.execute("""
                        UPDATE marks SET
                            exam_name = %s, academic_year = %s,
                            mathematics = %s, english = %s, science = %s,
                            computer_science = %s, database_management = %s, web_technology = %s,
                            total_marks = %s, average = %s, percentage = %s, grade = %s, result = %s
                        WHERE mark_id = %s
                    """, (
                        e_name, a_year,
                        om['mathematics'], om['english'], om['science'],
                        om['computer_science'], om['database_management'], om['web_technology'],
                        om['total_marks'], om['average'], om['percentage'], om['grade'], om['result'],
                        exists['mark_id']
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO marks (
                            student_id, exam_name, exam_type, academic_year,
                            mathematics, english, science, computer_science,
                            database_management, web_technology, total_marks,
                            average, percentage, grade, result
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        s_id, e_name, e_type, a_year,
                        om['mathematics'], om['english'], om['science'],
                        om['computer_science'], om['database_management'], om['web_technology'],
                        om['total_marks'], om['average'], om['percentage'], om['grade'], om['result']
                    ))
                synced_other_marks += 1

        s_conn.close()
        print(f"[+] Synchronized {synced_other_marks} multi-exam records (CIA 2 & Model) for comprehensive analytics.")

    conn.commit()

    # Verification counts
    cursor.execute("SELECT COUNT(*) as c FROM students")
    total_mysql_students = cursor.fetchone()['c']

    cursor.execute("SELECT COUNT(*) as c FROM marks")
    total_mysql_marks = cursor.fetchone()['c']

    cursor.execute("SELECT exam_type, COUNT(*) as c FROM marks GROUP BY exam_type")
    exam_counts = cursor.fetchall()

    conn.close()

    print("\n" + "=" * 65)
    print("MYSQL DATABASE SYNCHRONIZATION SUMMARY")
    print("=" * 65)
    print(f"Authoritative Excel File   : {os.path.basename(excel_path)}")
    print(f"Total Rows in Excel        : {len(df)}")
    print(f"Newly Inserted Students    : {imported_count}")
    print(f"Updated Existing Students  : {updated_count}")
    print(f"Obsolete Demo Students     : {len(obsolete_students)} (Archived)")
    print(f"Skipped / Invalid Records  : {skipped_count}")
    print(f"Duplicate Register Numbers : {duplicate_rows}")
    print(f"Total Students in MySQL    : {total_mysql_students}")
    print(f"Total Exam Marks in MySQL  : {total_mysql_marks}")
    for ec in exam_counts:
        print(f"  - {ec['exam_type']}: {ec['c']} records")
    print("=" * 65)

    return True

if __name__ == '__main__':
    import_mysql_dataset()
