import os
import sys
import sqlite3
import pandas as pd
from werkzeug.security import check_password_hash

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import Config
from database import get_db_connection
from ml_model import get_ml_prediction

def run_verification():
    print("=" * 70)
    print("FINAL APPLICATION & DATA INTEGRATION VERIFICATION")
    print("=" * 70)
    
    # 1. Excel File Verification
    excel_path = os.path.join(Config.BASE_DIR, "IT_STUDENTS_DATASET.xlsx")
    if not os.path.exists(excel_path):
        print("[FAIL] Excel dataset file IT_STUDENTS_DATASET.xlsx not found.")
        return False
    df_excel = pd.read_excel(excel_path, sheet_name="Student Dataset")
    print(f"[PASS] Excel dataset found with {len(df_excel)} rows and {len(df_excel.columns)} columns.")
    
    # 2. Database Counts
    conn = get_db_connection()
    students_count = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    marks_count = conn.execute("SELECT COUNT(*) as c FROM marks").fetchone()['c']
    
    print(f"[*] Total Students in Database: {students_count}")
    print(f"[*] Total Exam Records in Database: {marks_count}")
    
    if students_count != 123:
        print(f"[FAIL] Expected 123 students in DB, found {students_count}")
        return False
    if marks_count != 123:
        print(f"[FAIL] Expected 123 exam records in DB, found {marks_count}")
        return False
    print("[PASS] Database student and mark counts match exactly 123.")
    
    # 3. Duplicate Register Numbers Check
    dups = conn.execute("SELECT register_number, COUNT(*) as c FROM students GROUP BY register_number HAVING c > 1").fetchall()
    if dups:
        print(f"[FAIL] Found duplicate register numbers: {dups}")
        return False
    print("[PASS] Zero duplicate register numbers in database.")
    
    # 4. Demo Students Purge Verification
    demo_check = conn.execute("SELECT COUNT(*) as c FROM students WHERE register_number LIKE 'REG2024%'").fetchone()['c']
    if demo_check > 0:
        print(f"[FAIL] Found {demo_check} demo students remaining in DB.")
        return False
    print("[PASS] All demo student records purged successfully.")
    
    # 5. Admin Credentials Check
    admin = conn.execute("SELECT * FROM admins WHERE username = 'admin'").fetchone()
    if not admin or not check_password_hash(admin['password_hash'], 'admin123'):
        print("[FAIL] Admin credentials (admin / admin123) invalid.")
        return False
    print("[PASS] Default admin account (admin / admin123) verified.")
    
    # 6. Student Credentials Check
    sample_student = conn.execute("SELECT * FROM students WHERE register_number = '927624BIT001'").fetchone()
    if not sample_student or not check_password_hash(sample_student['password_hash'], 'student123'):
        print("[FAIL] Student login (927624BIT001 / student123) failed.")
        return False
    print(f"[PASS] Student account login ({sample_student['name']} - 927624BIT001 / student123) verified.")
    
    # 7. Excel Data vs Database Accuracy Check
    first_excel_row = df_excel.iloc[0]
    excel_reg = str(first_excel_row['Register No.']).strip().upper()
    excel_math = float(first_excel_row['Mathematics Mark'])
    excel_web = float(first_excel_row['Web Technologies Mark'])
    
    db_mark = conn.execute("""
        SELECT m.*, s.register_number 
        FROM marks m JOIN students s ON m.student_id = s.id 
        WHERE s.register_number = ?
    """, (excel_reg,)).fetchone()
    
    if not db_mark:
        print(f"[FAIL] Could not find DB marks for {excel_reg}")
        return False
        
    if db_mark['mathematics'] != excel_math or db_mark['web_technology'] != excel_web:
        print(f"[FAIL] Data mismatch for {excel_reg}: Excel Math={excel_math}, DB Math={db_mark['mathematics']}")
        return False
    print(f"[PASS] Data integrity verified: {excel_reg} Math={db_mark['mathematics']}, Web={db_mark['web_technology']}, Total={db_mark['total_marks']}.")
    
    conn.close()
    
    # 8. ML Prediction Check
    pred = get_ml_prediction(
        db_mark['mathematics'], db_mark['english'], db_mark['science'],
        db_mark['computer_science'], db_mark['database_management'], db_mark['web_technology'],
        db_mark['average'], db_mark['percentage']
    )
    print(f"[PASS] ML Prediction for {excel_reg}: Category={pred['prediction']}, Confidence={pred['confidence']}%, Model={pred['model_version']}.")
    
    print("=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == '__main__':
    run_verification()
