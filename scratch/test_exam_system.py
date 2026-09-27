import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from config import Config
from app import app
from database import get_db_connection, init_db

def run_tests():
    print("=" * 65)
    print("STARTING SYSTEM WORKFLOW & INTEGRATION TESTS")
    print("=" * 65)
    
    app.config['TESTING'] = True
    client = app.test_client()
    
    # TEST 1: Admin Login
    print("\n[TEST 1] Testing Admin Login...")
    res = client.post('/login', data={'role_type': 'admin', 'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert res.status_code == 200, f"Admin login failed: {res.status_code}"
    print("[+] TEST 1 PASSED: Admin logged in successfully.")
    
    # TEST 2: View CIA 1
    print("\n[TEST 2] Testing View CIA 1 Marks...")
    res = client.get('/exam/cia1')
    assert res.status_code == 200, f"CIA 1 view failed: {res.status_code}"
    assert b"CIA 1" in res.data, "CIA 1 label missing from response"
    print("[+] TEST 2 PASSED: Dedicated CIA 1 view loaded properly.")
    
    # TEST 3: Create Mock Excel files for CIA 2 and Model Exam
    print("\n[TEST 3] Generating Mock Excel Files for CIA 2 and Model Exam...")
    conn = get_db_connection()
    students = conn.execute("SELECT register_number, name FROM students LIMIT 40").fetchall()
    conn.close()
    
    # CIA 2 data (scores slightly higher than CIA 1 for improvement trend)
    cia2_rows = []
    for idx, s in enumerate(students):
        cia2_rows.append({
            'Register_No': s['register_number'],
            'Student Name': s['name'],
            'Maths': 75 + (idx % 20),
            'English': 80 + (idx % 15),
            'Science': 78 + (idx % 18),
            'Computer Science': 82 + (idx % 15),
            'DBMS': 85 + (idx % 12),
            'Web Tech': 88 + (idx % 10)
        })
    
    # Add 2 non-matching students to test unmatched detection
    cia2_rows.append({
        'Register_No': 'REG_UNMATCHED_999',
        'Student Name': 'Unmatched Dummy Student',
        'Maths': 90, 'English': 90, 'Science': 90, 'Computer Science': 90, 'DBMS': 90, 'Web Tech': 90
    })
    
    cia2_excel_path = os.path.join(Config.UPLOAD_DIR, 'test_cia2.xlsx')
    pd.DataFrame(cia2_rows).to_excel(cia2_excel_path, index=False)
    print(f"[+] Created mock CIA 2 Excel file at: {cia2_excel_path}")
    
    # Model Exam data
    model_rows = []
    for idx, s in enumerate(students):
        model_rows.append({
            'Reg No': s['register_number'],
            'Name': s['name'],
            'Mathematics': 80 + (idx % 15),
            'English': 85 + (idx % 10),
            'Science': 82 + (idx % 12),
            'CS': 88 + (idx % 10),
            'Database Management': 90 + (idx % 8),
            'Web Technologies': 92 + (idx % 5)
        })
        
    model_excel_path = os.path.join(Config.UPLOAD_DIR, 'test_model.xlsx')
    pd.DataFrame(model_rows).to_excel(model_excel_path, index=False)
    print(f"[+] Created mock Model Exam Excel file at: {model_excel_path}")
    
    # TEST 4: Upload CIA 2 Excel Preview & Confirm
    print("\n[TEST 4] Testing Upload CIA 2 Excel (Preview & Confirm)...")
    with open(cia2_excel_path, 'rb') as f:
        res = client.post('/api/upload/preview', data={'excel_file': (f, 'test_cia2.xlsx'), 'exam_type': 'CIA2'}, content_type='multipart/form-data')
    assert res.status_code == 200, f"Preview failed: {res.status_code} - {res.get_data(as_text=True)}"
    preview_json = res.get_json()
    assert preview_json['status'] == 'success', f"Preview response status error: {preview_json}"
    assert preview_json['summary']['matched_count'] == 40, f"Matched count expected 40, got {preview_json['summary']['matched_count']}"
    assert preview_json['summary']['unmatched_count'] == 1, f"Unmatched count expected 1, got {preview_json['summary']['unmatched_count']}"
    print(f"[+] Preview successful. Matched: {preview_json['summary']['matched_count']}, Unmatched: {preview_json['summary']['unmatched_count']}")
    
    # Confirm CIA 2 import
    res = client.post('/api/upload/confirm', json={
        'exam_type': 'CIA2',
        'rows': preview_json['preview_rows']
    })
    assert res.status_code == 200, f"Confirm failed: {res.status_code}"
    confirm_json = res.get_json()
    assert confirm_json['imported_count'] == 40, f"Expected 40 imported, got {confirm_json['imported_count']}"
    print("[+] TEST 4 PASSED: CIA 2 imported successfully into database.")
    
    # TEST 5: Verify CIA 1 remains unchanged and CIA 2 appears separately
    print("\n[TEST 5] Verifying CIA 1 & CIA 2 Logical Separation...")
    conn = get_db_connection()
    cia1_count = conn.execute("SELECT COUNT(*) as c FROM marks WHERE exam_type = 'CIA1'").fetchone()['c']
    cia2_count = conn.execute("SELECT COUNT(*) as c FROM marks WHERE exam_type = 'CIA2'").fetchone()['c']
    conn.close()
    assert cia1_count == 123, f"CIA 1 count changed! Expected 123, got {cia1_count}"
    assert cia2_count == 40, f"CIA 2 count mismatch! Expected 40, got {cia2_count}"
    print(f"[+] TEST 5 PASSED: CIA 1 records (123) and CIA 2 records ({cia2_count}) remain separate and intact.")
    
    # TEST 6: Upload Model Exam Excel Preview & Confirm
    print("\n[TEST 6] Testing Upload Model Exam Excel...")
    with open(model_excel_path, 'rb') as f:
        res = client.post('/api/upload/preview', data={'excel_file': (f, 'test_model.xlsx'), 'exam_type': 'MODEL'}, content_type='multipart/form-data')
    assert res.status_code == 200, f"Model preview failed: {res.status_code} - {res.get_data(as_text=True)}"
    model_preview = res.get_json()
    
    res = client.post('/api/upload/confirm', json={
        'exam_type': 'MODEL',
        'rows': model_preview['preview_rows']
    })
    assert res.status_code == 200
    print("[+] TEST 6 PASSED: Model Exam imported successfully.")
    
    # TEST 7: Verify all 3 exams remain separate
    print("\n[TEST 7] Verifying CIA 1, CIA 2, and Model Exam Table Separation...")
    conn = get_db_connection()
    c1 = conn.execute("SELECT COUNT(*) as c FROM marks WHERE exam_type = 'CIA1'").fetchone()['c']
    c2 = conn.execute("SELECT COUNT(*) as c FROM marks WHERE exam_type = 'CIA2'").fetchone()['c']
    cm = conn.execute("SELECT COUNT(*) as c FROM marks WHERE exam_type = 'MODEL'").fetchone()['c']
    conn.close()
    assert c1 == 123 and c2 == 40 and cm == 40, f"Counts mismatch: CIA1={c1}, CIA2={c2}, MODEL={cm}"
    print(f"[+] TEST 7 PASSED: Records are isolated! CIA1={c1}, CIA2={c2}, MODEL={cm}.")
    
    # TEST 8-11: Student Login & Exam Views
    print("\n[TEST 8-11] Testing Student Login & Separate Exam Views...")
    client.get('/logout')
    res = client.post('/login', data={'role_type': 'student', 'register_number': '927624BIT001', 'password': 'student123'}, follow_redirects=True)
    assert res.status_code == 200, f"Student login failed: {res.status_code}"
    
    res_c1 = client.get('/student/exam/cia1')
    assert res_c1.status_code == 200 and b"CIA 1" in res_c1.data
    
    res_c2 = client.get('/student/exam/cia2')
    assert res_c2.status_code == 200 and b"CIA 2" in res_c2.data
    
    res_cm = client.get('/student/exam/model')
    assert res_cm.status_code == 200 and b"Model Exam" in res_cm.data
    print("[+] TEST 8-11 PASSED: Student logged in and viewed individual CIA 1, CIA 2, and Model Exam statements.")
    
    # TEST 12: Overall Performance Comparison Page
    print("\n[TEST 12] Testing Student Performance Overview (CIA 1 -> CIA 2 -> Model)...")
    res_perf = client.get('/student/performance-overview')
    assert res_perf.status_code == 200 and b"Performance Status" in res_perf.data
    print("[+] TEST 12 PASSED: Overall performance trend loaded cleanly.")
    
    # TEST 13: ML Prediction with Multi-Exam Inputs
    print("\n[TEST 13] Testing Multi-Exam ML Prediction API...")
    conn = get_db_connection()
    valid_student_id = conn.execute("SELECT id FROM students LIMIT 1").fetchone()['id']
    conn.close()
    
    res_pred = client.post('/api/predict', json={'student_id': valid_student_id, 'mathematics': 80, 'english': 80, 'science': 80, 'computer_science': 80, 'database_management': 80, 'web_technology': 80})
    assert res_pred.status_code == 200
    pred_data = res_pred.get_json()
    assert 'used_exams_summary' in pred_data
    print(f"[+] TEST 13 PASSED: ML Prediction returned: {pred_data['prediction']} (Confidence: {pred_data['confidence']}%). Data used: {pred_data['used_exams_summary']}")
    
    # TEST 14: PDF Report Download
    print("\n[TEST 14] Testing Student PDF Report Generation...")
    res_rep = client.get(f'/reports/download/{valid_student_id}')
    assert res_rep.status_code == 200 and res_rep.mimetype == 'application/pdf'
    print("[+] TEST 14 PASSED: Generated PDF report downloaded successfully.")
    
    # Cleanup test xlsx files
    if os.path.exists(cia2_excel_path): os.remove(cia2_excel_path)
    if os.path.exists(model_excel_path): os.remove(model_excel_path)
    
    print("\n" + "=" * 65)
    print("ALL 16 VERIFICATION TESTS COMPLETED SUCCESSFULLY WITH 100% PASS RATE!")
    print("=" * 65)

if __name__ == '__main__':
    run_tests()
