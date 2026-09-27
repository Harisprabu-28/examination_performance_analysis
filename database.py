import os
import sqlite3
from werkzeug.security import generate_password_hash
from config import Config

def get_db_connection():
    """Returns a SQLite connection with Row row_factory for dict-like access."""
    os.makedirs(Config.DB_DIR, exist_ok=True)
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(Config.ML_DIR, exist_ok=True)
    
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def calculate_exam_metrics(math, eng, sci, cs, db, web):
    """
    Calculates total marks, average, percentage, grade, and pass/fail result.
    Pass requirement: Every subject score >= 40.
    """
    subjects = [float(math), float(eng), float(sci), float(cs), float(db), float(web)]
    total_marks = round(sum(subjects), 2)
    average = round(total_marks / 6.0, 2)
    percentage = round((total_marks / Config.TOTAL_MAX_MARKS) * 100.0, 2)
    
    # Pass if all subjects >= 40
    is_pass = all(m >= Config.PASS_MARK_PER_SUBJECT for m in subjects)
    result = "PASS" if is_pass else "FAIL"
    
    # Grading scheme
    if percentage >= 90:
        grade = "A+"
    elif percentage >= 80:
        grade = "A"
    elif percentage >= 70:
        grade = "B+"
    elif percentage >= 60:
        grade = "B"
    elif percentage >= 50:
        grade = "C"
    elif percentage >= 40:
        grade = "D"
    else:
        grade = "F"
        
    return total_marks, average, percentage, grade, result

def init_db():
    """Creates tables if they do not exist and seeds initial demo data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            register_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            department TEXT,
            year TEXT,
            semester TEXT,
            section TEXT,
            date_of_birth TEXT,
            gender TEXT,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. marks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            exam_type TEXT NOT NULL DEFAULT 'CIA1',
            academic_year TEXT NOT NULL,
            mathematics REAL NOT NULL,
            english REAL NOT NULL,
            science REAL NOT NULL,
            computer_science REAL NOT NULL,
            database_management REAL NOT NULL,
            web_technology REAL NOT NULL,
            total_marks REAL NOT NULL,
            average REAL NOT NULL,
            percentage REAL NOT NULL,
            grade TEXT NOT NULL,
            result TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
    ''')
    
    # Check and migrate schema if exam_type column is missing
    cursor.execute("PRAGMA table_info(marks)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'exam_type' not in columns:
        cursor.execute("ALTER TABLE marks ADD COLUMN exam_type TEXT DEFAULT 'CIA1'")
        cursor.execute("UPDATE marks SET exam_type = 'CIA1' WHERE exam_type IS NULL OR exam_type = ''")
        print("[*] Migration: Added exam_type column to marks table.")
    
    # 4. predictions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            prediction TEXT NOT NULL,
            confidence REAL NOT NULL,
            model_version TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
    ''')
    
    # Create default Admin if not exists
    cursor.execute("SELECT id FROM admins WHERE username = ?", (Config.DEFAULT_ADMIN_USERNAME,))
    admin = cursor.fetchone()
    if not admin:
        cursor.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?, ?)",
            (Config.DEFAULT_ADMIN_USERNAME, generate_password_hash(Config.DEFAULT_ADMIN_PASSWORD))
        )
        print(f"[*] Default admin created: {Config.DEFAULT_ADMIN_USERNAME}")
    
    # Check if student data exists; if not, import real dataset from Excel
    cursor.execute("SELECT COUNT(*) as count FROM students")
    student_count = cursor.fetchone()['count']
    
    conn.commit()
    conn.close()
    
    if student_count == 0:
        try:
            from import_dataset import import_excel_dataset
            print("[*] Empty database detected. Importing real student dataset...")
            import_excel_dataset()
        except Exception as e:
            print(f"[!] Auto-import from Excel failed: {e}")

def get_student_exam_history(student_id):
    """
    Returns a dictionary of examination records for a student indexed by exam_type ('CIA1', 'CIA2', 'MODEL').
    """
    conn = get_db_connection()
    records = conn.execute(
        "SELECT * FROM marks WHERE student_id = ? ORDER BY id ASC", (student_id,)
    ).fetchall()
    conn.close()
    
    history = {'CIA1': None, 'CIA2': None, 'MODEL': None, 'all': []}
    for r in records:
        e_type = r['exam_type'] if 'exam_type' in r.keys() and r['exam_type'] else 'CIA1'
        if e_type in history:
            history[e_type] = dict(r)
        history['all'].append(dict(r))
    return history

def calculate_student_trend(student_id):
    """
    Calculates student performance trend across available exams (CIA 1 -> CIA 2 -> MODEL).
    Returns trend status: 'Improving', 'Stable', or 'Declining'.
    """
    history = get_student_exam_history(student_id)
    available_scores = []
    
    for e_type in ['CIA1', 'CIA2', 'MODEL']:
        if history[e_type]:
            available_scores.append((e_type, history[e_type]['percentage']))
            
    if len(available_scores) <= 1:
        status = 'Stable'
    else:
        diffs = [available_scores[i][1] - available_scores[i-1][1] for i in range(1, len(available_scores))]
        avg_diff = sum(diffs) / len(diffs)
        if avg_diff > 1.5:
            status = 'Improving'
        elif avg_diff < -1.5:
            status = 'Declining'
        else:
            status = 'Stable'
            
    return {
        'history': history,
        'available_scores': available_scores,
        'status': status,
        'cia1_perc': history['CIA1']['percentage'] if history['CIA1'] else None,
        'cia2_perc': history['CIA2']['percentage'] if history['CIA2'] else None,
        'model_perc': history['MODEL']['percentage'] if history['MODEL'] else None
    }

def get_weak_students(exam_type=None):
    """
    Identifies students needing academic attention based on:
    1. Overall average < 50%
    2. Failing result or subject score < 40 in exam
    3. Declining performance trend from CIA 1 to CIA 2 / MODEL
    If exam_type is specified ('CIA1', 'CIA2', 'MODEL'), evaluates performance for that selected exam.
    """
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    conn.close()
    
    weak_list = []
    for s in students:
        s_id = s['id']
        history = get_student_exam_history(s_id)
        trend_info = calculate_student_trend(s_id)
        
        if exam_type:
            target_exam = history.get(exam_type.upper())
        else:
            target_exam = history['MODEL'] or history['CIA2'] or history['CIA1']
            
        if not target_exam:
            continue
            
        reasons = []
        # Check failed subjects (< 40)
        failed_subs = []
        subjects = [
            ('mathematics', 'Maths'), 
            ('english', 'English'), 
            ('science', 'Science'),
            ('computer_science', 'CS'), 
            ('database_management', 'DBMS'), 
            ('web_technology', 'Web Tech')
        ]
        for sub_col, sub_title in subjects:
            if target_exam[sub_col] < Config.PASS_MARK_PER_SUBJECT:
                failed_subs.append(f"{sub_title} ({target_exam[sub_col]})")
                
        if failed_subs:
            reasons.append(f"Failed in: {', '.join(failed_subs)}")
        elif target_exam['result'] == 'FAIL':
            reasons.append(f"Failed in {target_exam['exam_name']}")
            
        if target_exam['percentage'] < 50.0:
            reasons.append(f"Low overall score ({target_exam['percentage']}%)")
            
        if not exam_type and trend_info['status'] == 'Declining':
            reasons.append("Declining performance trend across exams")
            
        if reasons:
            weak_list.append({
                'id': s['id'],
                'register_number': s['register_number'],
                'name': s['name'],
                'department': s['department'],
                'section': s['section'],
                'cia1_perc': trend_info['cia1_perc'],
                'cia2_perc': trend_info['cia2_perc'],
                'model_perc': trend_info['model_perc'],
                'latest_perc': target_exam['percentage'],
                'status': 'At-Risk' if target_exam['result'] == 'FAIL' else 'Needs Attention',
                'reasons': ", ".join(reasons),
                'exam_type': target_exam.get('exam_type', exam_type or 'CIA1')
            })
            
    return weak_list

def seed_sample_data(cursor):
    """Seeds 25 realistic college student records and examination histories."""
    default_pwd_hash = generate_password_hash(Config.DEFAULT_STUDENT_PASSWORD)
    
    sample_students = [
        ("REG2024001", "Aarav Sharma", "aarav.sharma@college.edu", "9876543210", "Computer Science & Engineering", "3rd Year", "VI Semester", "A", "2003-05-14", "Male"),
        ("REG2024002", "Priya Patel", "priya.patel@college.edu", "9876543211", "Computer Science & Engineering", "3rd Year", "VI Semester", "A", "2003-08-22", "Female"),
        ("REG2024003", "Rohan Verma", "rohan.verma@college.edu", "9876543212", "Information Technology", "3rd Year", "VI Semester", "B", "2003-02-10", "Male"),
        ("REG2024004", "Ananya Iyer", "ananya.iyer@college.edu", "9876543213", "Information Technology", "3rd Year", "VI Semester", "A", "2003-11-30", "Female"),
        ("REG2024005", "Karthik Nair", "karthik.nair@college.edu", "9876543214", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "A", "2004-04-18", "Male"),
        ("REG2024006", "Sneha Kulkarni", "sneha.kulkarni@college.edu", "9876543215", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "A", "2004-09-05", "Female"),
        ("REG2024007", "Vikramaditya Rao", "vikram.rao@college.edu", "9876543216", "Computer Science & Engineering", "3rd Year", "VI Semester", "B", "2003-01-25", "Male"),
        ("REG2024008", "Diya Sengupta", "diya.sengupta@college.edu", "9876543217", "Electronics & Communication", "2nd Year", "IV Semester", "A", "2004-07-12", "Female"),
        ("REG2024009", "Arjun Reddy", "arjun.reddy@college.edu", "9876543218", "Information Technology", "3rd Year", "VI Semester", "A", "2003-10-15", "Male"),
        ("REG2024010", "Meera Joshi", "meera.joshi@college.edu", "9876543219", "Computer Science & Engineering", "3rd Year", "VI Semester", "B", "2003-03-28", "Female"),
        ("REG2024011", "Aditya Deshmukh", "aditya.deshmukh@college.edu", "9876543220", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "B", "2004-06-19", "Male"),
        ("REG2024012", "Kavya Menon", "kavya.menon@college.edu", "9876543221", "Computer Science & Engineering", "3rd Year", "VI Semester", "A", "2003-12-08", "Female"),
        ("REG2024013", "Siddharth Malhotra", "siddharth.m@college.edu", "9876543222", "Electronics & Communication", "2nd Year", "IV Semester", "B", "2004-02-14", "Male"),
        ("REG2024014", "Pooja Hegde", "pooja.hegde@college.edu", "9876543223", "Information Technology", "3rd Year", "VI Semester", "B", "2003-09-21", "Female"),
        ("REG2024015", "Varun Teja", "varun.teja@college.edu", "9876543224", "Computer Science & Engineering", "3rd Year", "VI Semester", "A", "2003-04-03", "Male"),
        ("REG2024016", "Tanvi Bhatt", "tanvi.bhatt@college.edu", "9876543225", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "A", "2004-08-11", "Female"),
        ("REG2024017", "Gaurav Sen", "gaurav.sen@college.edu", "9876543226", "Information Technology", "3rd Year", "VI Semester", "A", "2003-07-29", "Male"),
        ("REG2024018", "Ishita Roy", "ishita.roy@college.edu", "9876543227", "Electronics & Communication", "2nd Year", "IV Semester", "A", "2004-05-02", "Female"),
        ("REG2024019", "Rahul Dravid", "rahul.d@college.edu", "9876543228", "Computer Science & Engineering", "3rd Year", "VI Semester", "B", "2003-10-09", "Male"),
        ("REG2024020", "Rhea Kapoor", "rhea.kapoor@college.edu", "9876543229", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "B", "2004-01-17", "Female"),
        ("REG2024021", "Manoj Kumar", "manoj.k@college.edu", "9876543230", "Electronics & Communication", "2nd Year", "IV Semester", "B", "2004-11-23", "Male"),
        ("REG2024022", "Divya Pillai", "divya.pillai@college.edu", "9876543231", "Information Technology", "3rd Year", "VI Semester", "A", "2003-06-16", "Female"),
        ("REG2024023", "Sameer Khan", "sameer.khan@college.edu", "9876543232", "Computer Science & Engineering", "3rd Year", "VI Semester", "B", "2003-03-04", "Male"),
        ("REG2024024", "Ananya Panday", "ananya.p@college.edu", "9876543233", "Artificial Intelligence & Data Science", "2nd Year", "IV Semester", "A", "2004-10-30", "Female"),
        ("REG2024025", "Nikhil Chopra", "nikhil.c@college.edu", "9876543234", "Electronics & Communication", "2nd Year", "IV Semester", "A", "2004-04-27", "Male"),
    ]
    
    student_ids = []
    for s in sample_students:
        cursor.execute('''
            INSERT INTO students (register_number, name, email, phone, department, year, semester, section, date_of_birth, gender, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (*s, default_pwd_hash))
        student_ids.append(cursor.lastrowid)
        
    # Seed multi-exam marks for realistic analysis and diverse training dataset
    # We will generate marks covering Excellent, Good, Average, Needs Improvement, and Poor
    exam_templates = [
        # (math, eng, sci, cs, db, web)
        # Tier 1: High / Excellent performers
        [ (94, 88, 92, 96, 95, 91), (96, 90, 95, 98, 97, 94) ], # Student 1
        [ (89, 92, 86, 94, 91, 88), (91, 95, 88, 96, 93, 90) ], # Student 2
        [ (82, 78, 85, 88, 84, 80), (85, 80, 88, 90, 87, 83) ], # Student 3 (Good)
        [ (92, 94, 90, 95, 93, 96), (95, 97, 92, 98, 96, 97) ], # Student 4 (Excellent)
        [ (74, 70, 78, 82, 75, 72), (76, 73, 80, 85, 78, 75) ], # Student 5 (Good)
        [ (88, 85, 87, 91, 89, 86), (90, 87, 89, 93, 91, 88) ], # Student 6 (Excellent)
        [ (62, 58, 65, 68, 64, 60), (65, 60, 68, 70, 66, 62) ], # Student 7 (Average)
        [ (78, 82, 75, 80, 77, 79), (80, 84, 78, 83, 80, 81) ], # Student 8 (Good)
        [ (45, 52, 48, 55, 50, 47), (48, 54, 50, 58, 52, 49) ], # Student 9 (Needs Improvement)
        [ (85, 80, 88, 92, 87, 84), (88, 82, 90, 94, 89, 86) ], # Student 10 (Good/Excellent)
        [ (58, 62, 55, 64, 60, 59), (60, 65, 58, 66, 62, 61) ], # Student 11 (Average)
        [ (95, 91, 93, 97, 96, 94), (97, 93, 95, 99, 98, 96) ], # Student 12 (Excellent)
        [ (38, 42, 35, 45, 40, 36), (42, 45, 38, 48, 44, 39) ], # Student 13 (Poor / Failed subjects)
        [ (71, 75, 73, 79, 76, 74), (73, 77, 75, 81, 78, 76) ], # Student 14 (Good)
        [ (83, 79, 86, 90, 85, 82), (85, 81, 88, 92, 87, 84) ], # Student 15 (Good)
        [ (90, 88, 91, 95, 92, 89), (92, 90, 93, 97, 94, 91) ], # Student 16 (Excellent)
        [ (64, 68, 61, 70, 66, 63), (66, 70, 63, 72, 68, 65) ], # Student 17 (Average)
        [ (52, 48, 55, 58, 53, 50), (54, 50, 57, 60, 55, 52) ], # Student 18 (Needs Improvement)
        [ (35, 40, 32, 44, 38, 30), (38, 42, 36, 46, 40, 34) ], # Student 19 (Poor / Fail)
        [ (86, 84, 88, 92, 89, 87), (88, 86, 90, 94, 91, 89) ], # Student 20 (Good/Excellent)
        [ (42, 45, 40, 48, 44, 41), (45, 48, 43, 50, 46, 43) ], # Student 21 (Needs Improvement)
        [ (79, 83, 81, 87, 84, 82), (81, 85, 83, 89, 86, 84) ], # Student 22 (Good)
        [ (60, 56, 62, 65, 61, 58), (62, 58, 64, 67, 63, 60) ], # Student 23 (Average)
        [ (93, 91, 95, 96, 94, 92), (95, 93, 97, 98, 96, 94) ], # Student 24 (Excellent)
        [ (55, 58, 52, 62, 57, 54), (57, 60, 54, 64, 59, 56) ]  # Student 25 (Average)
    ]
    
    exam_names = ["Mid-Term Examination 2025-26", "Semester Final Examination 2025-26"]
    academic_year = "2025-2026"
    
    for i, s_id in enumerate(student_ids):
        exams_for_student = exam_templates[i]
        for exam_idx, exam_scores in enumerate(exams_for_student):
            math, eng, sci, cs, db, web = exam_scores
            total, avg, perc, grade, result = calculate_exam_metrics(math, eng, sci, cs, db, web)
            
            cursor.execute('''
                INSERT INTO marks (
                    student_id, exam_name, academic_year,
                    mathematics, english, science, computer_science, database_management, web_technology,
                    total_marks, average, percentage, grade, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (s_id, exam_names[exam_idx], academic_year, math, eng, sci, cs, db, web, total, avg, perc, grade, result))
            
    print(f"[*] Inserted {len(sample_students) * 2} exam records.")
