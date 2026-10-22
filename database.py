import os
import sqlite3
from werkzeug.security import generate_password_hash
from config import Config

import re
from decimal import Decimal

# ==============================================================================
# Module-level MySQL Connection Pool & Directory Initialization
# ==============================================================================

_mysql_pool = None
_dirs_initialized = False


def _get_mysql_pool():
    """Lazily creates and returns a MySQL connection pool (singleton)."""
    global _mysql_pool
    if _mysql_pool is None:
        try:
            import mysql.connector.pooling
            _mysql_pool = mysql.connector.pooling.MySQLConnectionPool(
                pool_name="exam_analysis_pool",
                pool_size=10,
                pool_reset_session=True,
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB
            )
            print("[*] MySQL connection pool created (pool_size=10).")
        except Exception as e:
            print(f"[!] Warning: Failed to create MySQL connection pool ({e}).")
            _mysql_pool = None
    return _mysql_pool


def ensure_dirs():
    """Creates required directories once. Safe to call multiple times."""
    global _dirs_initialized
    if _dirs_initialized:
        return
    os.makedirs(Config.DB_DIR, exist_ok=True)
    os.makedirs(Config.REPORTS_DIR, exist_ok=True)
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(Config.ML_DIR, exist_ok=True)
    _dirs_initialized = True

def rewrite_mysql_query(query):
    """Translates SQLite query syntax to MySQL 8.0 syntax."""
    q = query.replace('?', '%s')
    if re.search(r'\b(from|update|into|join)\s+students\b', q, re.I):
        q = re.sub(r'\bstudents\.id\b', 'students.student_id', q, flags=re.I)
        q = re.sub(r'(?<!student_)\bid\b', 'student_id', q, flags=re.I)
    elif re.search(r'\b(from|update|into|join)\s+marks\b', q, re.I):
        q = re.sub(r'\bmarks\.id\b', 'marks.mark_id', q, flags=re.I)
        q = re.sub(r'(?<!mark_)\bid\b', 'mark_id', q, flags=re.I)
    elif re.search(r'\b(from|update|into|join)\s+admins\b', q, re.I):
        q = re.sub(r'\badmins\.id\b', 'admins.admin_id', q, flags=re.I)
        q = re.sub(r'(?<!admin_)\bid\b', 'admin_id', q, flags=re.I)
    return q

class DbRow(dict):
    """Dictionary-like row with attribute and alias fallback (id/student_id/mark_id/admin_id, name/student_name)."""
    def __init__(self, mapping=None):
        converted = {}
        if mapping:
            for k, v in mapping.items():
                if isinstance(v, Decimal):
                    converted[k] = float(v)
                else:
                    converted[k] = v
        super().__init__(converted)

    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        # Case insensitive check
        key_lower = key.lower()
        for k, v in self.items():
            if k.lower() == key_lower:
                return v
        # Alias fallbacks using super().get() to prevent recursion
        if key == 'id':
            val = super().get('student_id') or super().get('mark_id') or super().get('admin_id')
            if val is not None:
                return val
        if key in ('student_id', 'mark_id', 'admin_id'):
            val = super().get('id')
            if val is not None:
                return val
        if key == 'name':
            val = super().get('student_name')
            if val is not None:
                return val
        if key == 'student_name':
            val = super().get('name')
            if val is not None:
                return val
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

class MySQLCursorWrapper:
    def __init__(self, raw_cursor):
        self.raw = raw_cursor

    def execute(self, query, params=None):
        q = rewrite_mysql_query(query)
        if params is None:
            return self.raw.execute(q)
        return self.raw.execute(q, params)

    def fetchone(self):
        row = self.raw.fetchone()
        return DbRow(row) if row else None

    def fetchall(self):
        rows = self.raw.fetchall()
        return [DbRow(r) for r in rows] if rows else []

    @property
    def lastrowid(self):
        return self.raw.lastrowid

    @property
    def rowcount(self):
        return self.raw.rowcount

    def close(self):
        self.raw.close()

class MySQLConnectionWrapper:
    def __init__(self, raw_conn):
        self.raw = raw_conn

    def cursor(self):
        return MySQLCursorWrapper(self.raw.cursor(dictionary=True))

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

def get_db_connection():
    """Returns a database connection with dict-like Row access for MySQL or SQLite.
    Uses connection pooling for MySQL to avoid per-request TCP handshake overhead."""
    ensure_dirs()

    if Config.DB_TYPE == 'mysql':
        # Try pooled connection first
        pool = _get_mysql_pool()
        if pool is not None:
            try:
                raw_conn = pool.get_connection()
                try:
                    cur = raw_conn.cursor()
                    cur.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
                    cur.close()
                except Exception:
                    pass
                return MySQLConnectionWrapper(raw_conn)
            except Exception as e:
                print(f"[!] Warning: Pool connection failed ({e}). Trying direct connection.")

        # Fallback to direct connection if pool unavailable
        try:
            import mysql.connector
            raw_conn = mysql.connector.connect(
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB
            )
            try:
                cur = raw_conn.cursor()
                cur.execute("SET SESSION sql_mode='NO_ENGINE_SUBSTITUTION'")
                cur.close()
            except Exception:
                pass
            return MySQLConnectionWrapper(raw_conn)
        except Exception as e:
            print(f"[!] Warning: Failed to connect to MySQL ({e}). Falling back to SQLite.")

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
    if Config.DB_TYPE == 'mysql':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as c FROM admins")
        res = cursor.fetchone()
        if res and res['c'] == 0:
            cursor.execute(
                "INSERT INTO admins (username, full_name, password_hash) VALUES (?, ?, ?)",
                (Config.DEFAULT_ADMIN_USERNAME, 'System Administrator', generate_password_hash(Config.DEFAULT_ADMIN_PASSWORD))
            )
            conn.commit()
        conn.close()
        return

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

def calculate_student_trend(student_id, history=None):
    """
    Calculates student performance trend across available exams (CIA 1 -> CIA 2 -> MODEL).
    Returns trend status: 'Improving', 'Stable', or 'Declining'.
    Accepts optional pre-fetched history to avoid redundant DB queries.
    """
    if history is None:
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

def get_detailed_student_performance_analysis(student_id):
    """
    Computes an extensive, accurate multi-examination comparative performance analysis
    for a given student across CIA 1, CIA 2, and Model Examination using real stored DB marks.
    Identifies subjects needing improvement, strong subjects, and personalized recommendations.
    """
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        return None
        
    student_dict = dict(student)
    
    # Fetch all mark records ordered chronologically
    records = conn.execute(
        "SELECT * FROM marks WHERE student_id = ? ORDER BY id ASC", (student_id,)
    ).fetchall()
    conn.close()
    
    exam_history = {'CIA1': None, 'CIA2': None, 'MODEL': None}
    for r in records:
        e_type = r['exam_type'] if 'exam_type' in r.keys() and r['exam_type'] else 'CIA1'
        e_type = e_type.upper()
        if e_type in exam_history:
            exam_history[e_type] = dict(r)
            
    # Filter only available exams
    available_exam_types = [et for et in ['CIA1', 'CIA2', 'MODEL'] if exam_history[et] is not None]
    available_exams_count = len(available_exam_types)
    
    # 1. Overall Performance Status
    if available_exams_count == 0:
        overall_status = 'Insufficient Data'
        overall_diff = 0.0
        status_description = "No examination records are currently uploaded for this student."
    elif available_exams_count == 1:
        et = available_exam_types[0]
        perc = exam_history[et]['percentage']
        overall_status = 'Baseline (1 Exam Recorded)'
        overall_diff = 0.0
        status_description = f"Baseline performance established with {Config.EXAM_LABELS.get(et, et)} ({perc:.2f}%). Multi-exam comparative trend tracking requires at least two examination cycles."
    else:
        first_et = available_exam_types[0]
        latest_et = available_exam_types[-1]
        first_perc = exam_history[first_et]['percentage']
        latest_perc = exam_history[latest_et]['percentage']
        overall_diff = round(latest_perc - first_perc, 2)
        
        if overall_diff > 1.5:
            overall_status = 'Improving'
            status_description = f"Overall performance has improved by +{overall_diff:.2f}% ({Config.EXAM_LABELS.get(first_et, first_et)}: {first_perc:.2f}% -> {Config.EXAM_LABELS.get(latest_et, latest_et)}: {latest_perc:.2f}%)."
        elif overall_diff < -1.5:
            overall_status = 'Declining'
            status_description = f"Overall performance has declined by {overall_diff:.2f}% ({Config.EXAM_LABELS.get(first_et, first_et)}: {first_perc:.2f}% -> {Config.EXAM_LABELS.get(latest_et, latest_et)}: {latest_perc:.2f}%). Immediate targeted intervention advised."
        else:
            overall_status = 'Stable'
            status_description = f"Overall academic performance is consistent across examinations ({Config.EXAM_LABELS.get(first_et, first_et)}: {first_perc:.2f}%, {Config.EXAM_LABELS.get(latest_et, latest_et)}: {latest_perc:.2f}%, variation within ±1.5%)."

    # 2. Subject-wise Analysis
    subject_definitions = [
        ('mathematics', 'Mathematics', 'fa-calculator'),
        ('english', 'English', 'fa-book-open'),
        ('science', 'Science', 'fa-atom'),
        ('computer_science', 'Computer Science', 'fa-laptop-code'),
        ('database_management', 'Database Management', 'fa-database'),
        ('web_technology', 'Web Technology', 'fa-globe')
    ]
    
    subject_analysis = []
    
    for key, name, icon in subject_definitions:
        m_cia1 = exam_history['CIA1'][key] if exam_history['CIA1'] else None
        m_cia2 = exam_history['CIA2'][key] if exam_history['CIA2'] else None
        m_model = exam_history['MODEL'][key] if exam_history['MODEL'] else None
        
        # Chronological list of available values
        avail_scores = []
        for et in available_exam_types:
            avail_scores.append((et, exam_history[et][key]))
            
        latest_val = avail_scores[-1][1] if avail_scores else 0.0
        first_val = avail_scores[0][1] if avail_scores else 0.0
        
        diff_1_to_2 = round(m_cia2 - m_cia1, 1) if (m_cia1 is not None and m_cia2 is not None) else None
        diff_2_to_model = round(m_model - m_cia2, 1) if (m_cia2 is not None and m_model is not None) else None
        
        if len(avail_scores) >= 2:
            sub_diff = round(latest_val - first_val, 1)
            if sub_diff > 1.5:
                sub_status = 'Improving'
            elif sub_diff < -1.5:
                sub_status = 'Declining'
            else:
                sub_status = 'Stable'
        else:
            sub_diff = 0.0
            sub_status = 'Baseline' if len(avail_scores) == 1 else 'Insufficient Data'
            
        is_pass = (latest_val >= Config.PASS_MARK_PER_SUBJECT)
        
        item = {
            'key': key,
            'name': name,
            'icon': icon,
            'cia1': m_cia1,
            'cia2': m_cia2,
            'model': m_model,
            'diff_1_to_2': diff_1_to_2,
            'diff_2_to_model': diff_2_to_model,
            'overall_diff': sub_diff,
            'status': sub_status,
            'latest_score': latest_val,
            'is_pass': is_pass
        }
        subject_analysis.append(item)

    # 3. Practical Recommendations Knowledge Base per Subject
    recommendations_db = {
        'mathematics': {
            'failing': "Focus intensely on foundational arithmetic, algebra, and calculus principles. Dedicate 60-90 minutes daily to working through solved textbook examples step-by-step. Attend faculty tutorial hours for doubt clearance before attempting complex numericals.",
            'declining': "Performance in Mathematics has declined across assessments. Maintain a personalized formula revision notebook, practice 5-8 numerical problem variations daily on problem topics, and practice solving past semester question papers under 45-minute timed exam conditions.",
            'borderline': "Focus on high-weightage topics such as differential equations and matrix algebra. Review step-by-step algebraic manipulation to eliminate computational inaccuracies and review test mistakes thoroughly.",
            'strong': "Continue your stellar performance by attempting advanced university distinction problem sets, exploring discrete mathematical modeling in computing, and peer-mentoring classmates to deepen conceptual mastery."
        },
        'database_management': {
            'failing': "Core relational concepts require immediate remediation. Practice foundational SQL DDL and DML queries (SELECT, JOIN, WHERE, GROUP BY, HAVING) directly in MySQL/SQLite daily. Review relational algebra and primary/foreign key integrity rules.",
            'declining': "Database scores have dropped across recent exams. Dedicate time to hands-on query writing rather than passive reading. Practice database normalization decompositions (1NF to BCNF) on sample datasets and draw ER diagrams for real-world scenarios.",
            'borderline': "Solidify intermediate database topics including transaction ACID properties, concurrency control mechanisms (locks, two-phase commit), and index performance optimization to push your score into distinction.",
            'strong': "Demonstrating solid mastery of relational theory and SQL. Enhance your expertise by exploring database indexing, query execution plan tuning, and NoSQL architecture (MongoDB/Redis) for modern full-stack development."
        },
        'computer_science': {
            'failing': "Foundational programming and algorithmic thinking require urgent attention. Write and execute basic code daily, trace conditional logic and loop variables manually on paper, and review linear data structures (arrays, stacks, queues).",
            'declining': "Scores have dropped across the examination cycles. Focus on algorithmic problem breakdown, memory management, and object-oriented principles. Implement data structures from scratch rather than reading slides.",
            'borderline': "Enhance algorithm analysis capabilities (Big-O time and space complexity). Practice recursion, tree traversal algorithms, and divide-and-conquer techniques by coding mini-programs independently.",
            'strong': "Exceptional computer science acumen. Elevate your competence by solving competitive programming challenges (LeetCode / CodeChef), exploring system design, and building modular software projects."
        },
        'web_technology': {
            'failing': "Fundamental web architecture requires immediate focus. Build simple static web pages from scratch using semantic HTML5 elements, CSS box model styling, and basic JavaScript click event listeners to grasp client-side mechanics.",
            'declining': "Performance in Web Technology has slipped. Revisit DOM tree manipulation, asynchronous JavaScript execution (Promises, async/await, Fetch API), and responsive layout techniques (CSS Flexbox and Grid).",
            'borderline': "Strengthen client-server communication paradigms (HTTP request methods, status codes, REST APIs, JSON data exchange). Build a practical end-to-end interactive component (such as dynamic form validation or an API weather card).",
            'strong': "Superb grasp of web technologies. Maintain your edge by mastering modern component architectures (React, Vue, or Next.js), frontend performance optimization, and progressive web application standards."
        },
        'science': {
            'failing': "Fundamental scientific definitions, SI units, and core physical laws require structured revision. Form a weekly study group, review labeled apparatus diagrams, and clarify core lecture concepts with course faculty.",
            'declining': "Marks have dropped across examinations. Focus on analytical derivations and numerical problem solving. Double-check unit conversion calculations and link theoretical concepts to real-world engineering applications.",
            'borderline': "Review experimental procedures, laboratory observations, and standard unit derivations to convert satisfactory marks into distinction. Summarize each module with concise conceptual mind-maps.",
            'strong': "Outstanding scientific grasp. Maintain momentum by exploring contemporary technological applications of your physics/chemistry modules and practicing higher-order application questions."
        },
        'english': {
            'failing': "English language comprehension and grammatical foundations require structured practice. Dedicate 20 minutes daily to reading formal articles, review sentence structures (subject-verb agreement, active/passive voice), and practice paragraph writing.",
            'declining': "Scores have trended downward across assessments. Practice technical report writing, expand domain-specific professional vocabulary, and proofread assignments thoroughly to eliminate punctuation and syntax errors.",
            'borderline': "Elevate formal business communication and technical documentation writing. Practice summarizing engineering articles and answer comprehension questions under timed conditions to improve writing precision.",
            'strong': "Excellent communication and linguistic skills. Sustain excellence by delivering seminar presentations, publishing technical blog posts, and refining professional technical writing and resume drafting."
        }
    }

    # 4. Identify Subjects Requiring Improvement (Prioritized)
    subjects_needing_improvement = []
    
    # Priority 1: Failing subjects (score < 40)
    for sub in subject_analysis:
        if not sub['is_pass']:
            rec_text = recommendations_db[sub['key']]['failing']
            subjects_needing_improvement.append({
                'key': sub['key'],
                'name': sub['name'],
                'icon': sub['icon'],
                'latest_score': sub['latest_score'],
                'overall_diff': sub['overall_diff'],
                'severity': 'Critical / Failing (< 40)',
                'severity_class': 'danger',
                'reason': f"Current score ({sub['latest_score']:.1f}/100) is below the university pass threshold (40.0). Urgent remediation required.",
                'recommendation': rec_text
            })
            
    # Priority 2: Declining subjects (and not already in failing list)
    failing_keys = {s['key'] for s in subjects_needing_improvement}
    for sub in subject_analysis:
        if sub['key'] not in failing_keys and sub['status'] == 'Declining':
            rec_text = recommendations_db[sub['key']]['declining']
            drop_amount = abs(sub['overall_diff'])
            subjects_needing_improvement.append({
                'key': sub['key'],
                'name': sub['name'],
                'icon': sub['icon'],
                'latest_score': sub['latest_score'],
                'overall_diff': sub['overall_diff'],
                'severity': 'Significant Decline' if drop_amount >= 5.0 else 'Moderate Decline',
                'severity_class': 'danger' if drop_amount >= 5.0 else 'warning',
                'reason': f"Performance dropped by {drop_amount:.1f} marks across available exams (from {sub['cia1'] or 'initial'} to {sub['latest_score']:.1f}).",
                'recommendation': rec_text
            })
            
    # Priority 3: Low or borderline subjects (< 55) not already included
    included_keys = {s['key'] for s in subjects_needing_improvement}
    for sub in subject_analysis:
        if sub['key'] not in included_keys and sub['latest_score'] < 55.0:
            rec_text = recommendations_db[sub['key']]['borderline']
            subjects_needing_improvement.append({
                'key': sub['key'],
                'name': sub['name'],
                'icon': sub['icon'],
                'latest_score': sub['latest_score'],
                'overall_diff': sub['overall_diff'],
                'severity': 'Borderline Performance',
                'severity_class': 'warning',
                'reason': f"Score of {sub['latest_score']:.1f}/100 is in the low-performance bracket. Academic reinforcement needed to prevent future failure.",
                'recommendation': rec_text
            })

    # 5. Identify Strong Subjects
    strong_subjects = []
    included_improvement_keys = {s['key'] for s in subjects_needing_improvement}
    for sub in subject_analysis:
        if sub['key'] not in included_improvement_keys:
            if sub['latest_score'] >= 75.0 or (sub['status'] == 'Improving' and sub['latest_score'] >= 65.0):
                strong_subjects.append({
                    'key': sub['key'],
                    'name': sub['name'],
                    'icon': sub['icon'],
                    'latest_score': sub['latest_score'],
                    'overall_diff': sub['overall_diff'],
                    'achievement': f"Scored {sub['latest_score']:.1f}/100 with consistent mastery." if sub['status'] != 'Improving' else f"Scored {sub['latest_score']:.1f}/100 with a strong positive progression of +{sub['overall_diff']:.1f} marks.",
                    'recommendation': recommendations_db[sub['key']]['strong']
                })
                
    # 6. Personalized 3-Phase Improvement Plan
    if subjects_needing_improvement:
        primary_focus = [s['name'] for s in subjects_needing_improvement[:2]]
        focus_names = " and ".join(primary_focus)
        
        plan_steps = [
            {
                'step_num': '1',
                'title': f'Targeted Remediation in {focus_names}',
                'icon': 'fa-triangle-exclamation text-danger',
                'description': f"Allocate 4-5 additional study hours per week strictly to {focus_names}. Focus on high-frequency exam questions, solving core numericals/code samples, and scheduling doubt clarification with course instructors."
            },
            {
                'step_num': '2',
                'title': 'Active Practice & Mock Exam Drills',
                'icon': 'fa-pencil-ruler text-primary',
                'description': "Shift from passive lecture review to active problem solving. Complete at least two timed 45-minute practice tests on weak modules weekly, reviewing every incorrect answer immediately to correct conceptual gaps."
            },
            {
                'step_num': '3',
                'title': 'Milestone Target & Academic Checkpoint',
                'icon': 'fa-bullseye text-success',
                'description': f"Aim for a minimum target improvement of +10 marks in the next examination cycle for {focus_names}. Meet with your faculty mentor fortnightly to verify progress and maintain study momentum in your strong subjects."
            }
        ]
    else:
        plan_steps = [
            {
                'step_num': '1',
                'title': 'Maintain Excellence & Consistency',
                'icon': 'fa-star text-warning',
                'description': "All course performances are currently well-balanced. Maintain your current study routine and ensure continuous revision across all subjects before upcoming university examinations."
            },
            {
                'step_num': '2',
                'title': 'Advanced Distinction & Project Work',
                'icon': 'fa-laptop-code text-primary',
                'description': "Translate high theoretical marks into practical competence. Work on independent technical mini-projects, contribute to academic seminars, or attempt competitive programming problem sets."
            },
            {
                'step_num': '3',
                'title': 'Peer Mentorship & Milestone Setting',
                'icon': 'fa-award text-success',
                'description': "Engage in collaborative study groups. Teaching concepts to peers solidifies your own retention while keeping academic engagement consistently high."
            }
        ]
        
    # 7. Chart Data for Chart.js
    chart_labels = [s[1] for s in subject_definitions]
    chart_datasets = []
    
    color_palette = {
        'CIA1': {'bg': 'rgba(37, 99, 235, 0.75)', 'border': '#2563eb'},
        'CIA2': {'bg': 'rgba(6, 182, 212, 0.75)', 'border': '#06b6d4'},
        'MODEL': {'bg': 'rgba(16, 185, 129, 0.75)', 'border': '#10b981'}
    }
    
    for et in available_exam_types:
        exam_marks = [exam_history[et][k] for k, _, _ in subject_definitions]
        chart_datasets.append({
            'label': Config.EXAM_LABELS.get(et, et),
            'data': exam_marks,
            'backgroundColor': color_palette[et]['bg'],
            'borderColor': color_palette[et]['border'],
            'borderWidth': 1.5,
            'borderRadius': 4
        })
        
    chart_data = {
        'labels': chart_labels,
        'datasets': chart_datasets
    }
    
    return {
        'student': student_dict,
        'available_exams': available_exam_types,
        'exam_history': exam_history,
        'overall_status': overall_status,
        'overall_diff': overall_diff,
        'status_description': status_description,
        'subject_analysis': subject_analysis,
        'subjects_needing_improvement': subjects_needing_improvement,
        'strong_subjects': strong_subjects,
        'improvement_plan': plan_steps,
        'chart_data': chart_data
    }

def get_weak_students(exam_type=None):
    """
    Identifies students needing academic attention based on:
    1. Overall average < 50%
    2. Failing result or subject score < 40 in exam
    3. Declining performance trend from CIA 1 to CIA 2 / MODEL
    If exam_type is specified ('CIA1', 'CIA2', 'MODEL'), evaluates performance for that selected exam.
    
    Optimized: Uses only 2 DB queries (all students + all marks) instead of N+1 per student.
    """
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    all_marks = conn.execute("SELECT * FROM marks ORDER BY id ASC").fetchall()
    conn.close()
    
    # Pre-build per-student exam history in memory (replaces N individual queries)
    marks_by_student = {}
    for m in all_marks:
        sid = m['student_id']
        if sid not in marks_by_student:
            marks_by_student[sid] = []
        marks_by_student[sid].append(dict(m))
    
    def _build_history(student_id):
        """Builds exam history dict from pre-fetched marks (no DB call)."""
        records = marks_by_student.get(student_id, [])
        history = {'CIA1': None, 'CIA2': None, 'MODEL': None, 'all': []}
        for r in records:
            e_type = r.get('exam_type') or 'CIA1'
            if e_type in history and history[e_type] is None:
                history[e_type] = r
            history['all'].append(r)
        return history
    
    weak_list = []
    for s in students:
        s_id = s['id']
        history = _build_history(s_id)
        # Pass pre-built history to avoid redundant DB call
        trend_info = calculate_student_trend(s_id, history=history)
        
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
