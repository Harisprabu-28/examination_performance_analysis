import os
from functools import wraps
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, url_for, 
    session, flash, jsonify, send_file, abort
)
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
from config import Config
from database import (
    init_db, get_db_connection, calculate_exam_metrics,
    get_student_exam_history, calculate_student_trend, get_weak_students,
    get_detailed_student_performance_analysis
)
from ml_model import PerformancePredictor, get_ml_prediction, get_student_multi_exam_prediction
from report_generator import generate_student_pdf_report
from study_planner import (
    init_study_planner_tables, analyze_weak_subjects, get_study_preferences,
    save_study_preferences, generate_study_timetable, get_student_schedule,
    get_today_schedule, get_upcoming_sessions, update_session_status,
    get_study_progress, generate_reminders, check_missed_sessions,
    get_student_notifications, get_unread_notification_count,
    mark_notification_read, mark_all_notifications_read,
    get_study_recommendations, get_student_study_overview_for_faculty,
    start_reminder_scheduler
)

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY
CORS(app)

# Ensure database is initialized on startup
with app.app_context():
    init_db()
    init_study_planner_tables()

# Start background reminder scheduler
_reminder_scheduler = start_reminder_scheduler(app)

# ==============================================================================
# Authentication & Access Control Decorators
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this portal.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("Access denied: Administrative privileges required.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'student':
            flash("Access denied: Student account required.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# Authentication Routes
# ==============================================================================

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('dashboard'))
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role_type = request.form.get('role_type', 'admin')
        conn = get_db_connection()
        
        if role_type == 'admin':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            
            admin = conn.execute(
                "SELECT * FROM admins WHERE username = ?", (username,)
            ).fetchone()
            conn.close()
            
            if admin and check_password_hash(admin['password_hash'], password):
                session.clear()
                session['user_id'] = admin['id']
                session['username'] = admin['username']
                session['user_name'] = admin['username']
                session['role'] = 'admin'
                flash(f"Welcome back, Administrator {admin['username']}!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Invalid admin username or password.", "danger")
                
        else: # student login
            register_number = request.form.get('register_number', '').strip().upper()
            password = request.form.get('password', '')
            
            student = conn.execute(
                "SELECT * FROM students WHERE UPPER(register_number) = ?", (register_number,)
            ).fetchone()
            conn.close()
            
            if student and check_password_hash(student['password_hash'], password):
                session.clear()
                session['user_id'] = student['id']
                session['register_number'] = student['register_number']
                session['user_name'] = student['name']
                session['role'] = 'student'
                flash(f"Welcome, {student['name']}!", "success")
                return redirect(url_for('student_dashboard'))
            else:
                flash("Invalid student register number or password.", "danger")
                
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for('login'))

# ==============================================================================
# Admin Dashboard & Roster Routes
# ==============================================================================

def get_dashboard_data(exam_type='CIA1'):
    """
    Retrieves and calculates dynamic examination statistics, charts, top performers,
    and weak students strictly from the database for the specified exam_type ('CIA1', 'CIA2', 'MODEL').
    """
    exam_type = (exam_type or 'CIA1').upper()
    if exam_type not in Config.EXAM_TYPES:
        exam_type = 'CIA1'
        
    exam_label = Config.EXAM_LABELS.get(exam_type, exam_type)
    conn = get_db_connection()
    
    # 1. Total Students in database
    total_students = conn.execute("SELECT COUNT(*) as c FROM students").fetchone()['c']
    
    # 2. Total Exam Records for selected examination
    records_count = conn.execute("SELECT COUNT(*) as c FROM marks WHERE UPPER(exam_type) = ?", (exam_type,)).fetchone()['c']
    has_data = records_count > 0
    
    # 3. Aggregates for selected examination
    agg = conn.execute("""
        SELECT 
            AVG(percentage) as avg_p,
            SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) as failed
        FROM marks
        WHERE UPPER(exam_type) = ?
    """, (exam_type,)).fetchone()
    
    avg_percentage = round(agg['avg_p'] or 0.0, 2) if has_data else 0.0
    passed_students = agg['passed'] or 0
    failed_students = agg['failed'] or 0
    pass_percentage = round((passed_students / records_count * 100.0), 2) if records_count > 0 else 0.0
    
    # Top Achievers Count (Grade A+ in selected exam)
    top_performers_count = conn.execute("""
        SELECT COUNT(*) as c FROM marks 
        WHERE UPPER(exam_type) = ? AND grade = 'A+'
    """, (exam_type,)).fetchone()['c']
    
    stats = {
        'selected_exam': exam_type,
        'exam_label': exam_label,
        'has_data': has_data,
        'total_students': total_students,
        'total_records': records_count,
        'avg_percentage': avg_percentage,
        'pass_percentage': pass_percentage,
        'passed_students': passed_students,
        'failed_students': failed_students,
        'top_performers_count': top_performers_count
    }
    
    # Subject Averages for Bar Chart
    sub_avgs = conn.execute("""
        SELECT 
            AVG(mathematics) as m_avg,
            AVG(english) as e_avg,
            AVG(science) as s_avg,
            AVG(computer_science) as cs_avg,
            AVG(database_management) as db_avg,
            AVG(web_technology) as w_avg
        FROM marks
        WHERE UPPER(exam_type) = ?
    """, (exam_type,)).fetchone()
    
    subject_labels = ['Mathematics', 'English', 'Science', 'Computer Science', 'Database Management', 'Web Technology']
    subject_averages = [
        round(sub_avgs['m_avg'] or 0.0, 2) if has_data else 0.0,
        round(sub_avgs['e_avg'] or 0.0, 2) if has_data else 0.0,
        round(sub_avgs['s_avg'] or 0.0, 2) if has_data else 0.0,
        round(sub_avgs['cs_avg'] or 0.0, 2) if has_data else 0.0,
        round(sub_avgs['db_avg'] or 0.0, 2) if has_data else 0.0,
        round(sub_avgs['w_avg'] or 0.0, 2) if has_data else 0.0
    ]
    
    # Grade Distribution for Doughnut Chart
    grades = conn.execute("""
        SELECT grade, COUNT(*) as c 
        FROM marks 
        WHERE UPPER(exam_type) = ? 
        GROUP BY grade
    """, (exam_type,)).fetchall()
    grade_distribution = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
    if has_data:
        for g in grades:
            if g['grade'] in grade_distribution:
                grade_distribution[g['grade']] = g['c']
            
    # Trend Analysis across Exam Types
    trends = conn.execute("""
        SELECT exam_type, AVG(percentage) as avg_p, MAX(percentage) as max_p
        FROM marks
        GROUP BY exam_type
        ORDER BY id ASC
    """).fetchall()
    
    trend_labels = [Config.EXAM_LABELS.get(t['exam_type'], t['exam_type']) for t in trends]
    trend_averages = [round(t['avg_p'], 2) for t in trends]
    trend_tops = [round(t['max_p'], 2) for t in trends]
    
    # Top Performing Students for Selected Exam (Sorted by percentage DESC, then student name A-Z)
    top_students_rows = conn.execute("""
        SELECT m.*, s.name, s.register_number, s.email, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.id
        WHERE UPPER(m.exam_type) = ?
        ORDER BY m.percentage DESC, LOWER(s.name) ASC
        LIMIT 10
    """, (exam_type,)).fetchall()
    
    top_students = [dict(row) for row in top_students_rows]
    
    # Weak Students for Selected Exam
    weak_students = get_weak_students(exam_type)
    
    conn.close()
    
    chart_data = {
        'subject_labels': subject_labels,
        'subject_averages': subject_averages,
        'grade_distribution': grade_distribution,
        'trend_labels': trend_labels,
        'trend_averages': trend_averages,
        'trend_tops': trend_tops
    }
    
    return {
        'selected_exam': exam_type,
        'exam_label': exam_label,
        'has_data': has_data,
        'stats': stats,
        'chart_data': chart_data,
        'top_students': top_students,
        'weak_students': weak_students
    }

@app.route('/dashboard')
@admin_required
def dashboard():
    selected_exam = request.args.get('exam', 'CIA1').upper()
    if selected_exam not in Config.EXAM_TYPES:
        selected_exam = 'CIA1'
        
    dash_data = get_dashboard_data(selected_exam)
    return render_template(
        'dashboard.html',
        active_page='dashboard',
        selected_exam=dash_data['selected_exam'],
        exam_label=dash_data['exam_label'],
        has_data=dash_data['has_data'],
        stats=dash_data['stats'],
        chart_data=dash_data['chart_data'],
        top_students=dash_data['top_students'],
        weak_students=dash_data['weak_students']
    )

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    selected_exam = request.args.get('exam', 'CIA1').upper()
    if selected_exam not in Config.EXAM_TYPES:
        selected_exam = 'CIA1'
        
    dash_data = get_dashboard_data(selected_exam)
    return jsonify({
        'status': 'success',
        'selected_exam': dash_data['selected_exam'],
        'exam_label': dash_data['exam_label'],
        'has_data': dash_data['has_data'],
        'stats': dash_data['stats'],
        'chart_data': dash_data['chart_data'],
        'top_students': dash_data['top_students'],
        'weak_students': dash_data['weak_students']
    })

# ==============================================================================
# Student Management Module
# ==============================================================================

@app.route('/students')
@admin_required
def students_list():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    conn.close()
    return render_template('students.html', active_page='students', students=students)

@app.route('/students/add', methods=['GET', 'POST'])
@admin_required
def add_student():
    if request.method == 'POST':
        reg_no = request.form.get('register_number', '').strip().upper()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        dept = request.form.get('department', '').strip()
        year = request.form.get('year', '').strip()
        sem = request.form.get('semester', '').strip()
        sec = request.form.get('section', '').strip().upper()
        dob = request.form.get('date_of_birth', '').strip()
        gender = request.form.get('gender', '').strip()
        password = request.form.get('password', Config.DEFAULT_STUDENT_PASSWORD)
        
        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM students WHERE UPPER(register_number) = ?", (reg_no,)).fetchone()
        if existing:
            conn.close()
            flash(f"A student with Register Number {reg_no} already exists.", "danger")
            return render_template('add_student.html', active_page='students')
            
        pwd_hash = generate_password_hash(password)
        conn.execute("""
            INSERT INTO students (register_number, name, email, phone, department, year, semester, section, date_of_birth, gender, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (reg_no, name, email, phone, dept, year, sem, sec, dob, gender, pwd_hash))
        conn.commit()
        conn.close()
        
        flash(f"Student {name} ({reg_no}) successfully registered!", "success")
        return redirect(url_for('students_list'))
        
    return render_template('add_student.html', active_page='students')

@app.route('/students/edit/<int:student_id>', methods=['GET', 'POST'])
@admin_required
def edit_student(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    
    if not student:
        conn.close()
        flash("Student record not found.", "danger")
        return redirect(url_for('students_list'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        dept = request.form.get('department', '').strip()
        year = request.form.get('year', '').strip()
        sem = request.form.get('semester', '').strip()
        sec = request.form.get('section', '').strip().upper()
        dob = request.form.get('date_of_birth', '').strip()
        gender = request.form.get('gender', '').strip()
        password = request.form.get('password', '').strip()
        
        if password:
            pwd_hash = generate_password_hash(password)
            conn.execute("""
                UPDATE students 
                SET name = ?, email = ?, phone = ?, department = ?, year = ?, semester = ?, section = ?, date_of_birth = ?, gender = ?, password_hash = ?
                WHERE id = ?
            """, (name, email, phone, dept, year, sem, sec, dob, gender, pwd_hash, student_id))
        else:
            conn.execute("""
                UPDATE students 
                SET name = ?, email = ?, phone = ?, department = ?, year = ?, semester = ?, section = ?, date_of_birth = ?, gender = ?
                WHERE id = ?
            """, (name, email, phone, dept, year, sem, sec, dob, gender, student_id))
            
        conn.commit()
        conn.close()
        flash(f"Student {name} updated successfully!", "success")
        return redirect(url_for('students_list'))
        
    conn.close()
    return render_template('edit_student.html', active_page='students', student=student)

@app.route('/students/delete/<int:student_id>', methods=['POST'])
@admin_required
def delete_student(student_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()
    flash("Student record and related examination data deleted successfully.", "info")
    return redirect(url_for('students_list'))

@app.route('/students/<int:student_id>')
@admin_required
def student_detail(student_id):
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if not student:
        conn.close()
        abort(404)
        
    all_marks = conn.execute("SELECT * FROM marks WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
    latest_mark = all_marks[0] if all_marks else None
    
    ml_standing = None
    if latest_mark:
        ml_standing = get_ml_prediction(
            latest_mark['mathematics'], latest_mark['english'], latest_mark['science'],
            latest_mark['computer_science'], latest_mark['database_management'], latest_mark['web_technology'],
            latest_mark['average'], latest_mark['percentage']
        )
    conn.close()
    
    return render_template(
        'student_dashboard.html',
        active_page='students',
        student=student,
        latest_mark=latest_mark,
        all_marks=all_marks,
        ml_standing=ml_standing
    )

# ==============================================================================
# Marks Management Module
# ==============================================================================

@app.route('/marks')
@admin_required
def marks_list():
    conn = get_db_connection()
    marks = conn.execute("""
        SELECT m.*, s.name as student_name, s.register_number, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.id
        ORDER BY LOWER(s.name) ASC
    """).fetchall()
    conn.close()
    return render_template('marks.html', active_page='marks', marks=marks)

@app.route('/marks/add', methods=['GET', 'POST'])
@admin_required
def add_marks():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        exam_name = request.form.get('exam_name', 'Semester Final Examination 2025-26').strip()
        academic_year = request.form.get('academic_year', '2025-2026').strip()
        
        math = float(request.form.get('mathematics', 0))
        eng = float(request.form.get('english', 0))
        sci = float(request.form.get('science', 0))
        cs = float(request.form.get('computer_science', 0))
        db = float(request.form.get('database_management', 0))
        web = float(request.form.get('web_technology', 0))
        
        total, avg, perc, grade, result = calculate_exam_metrics(math, eng, sci, cs, db, web)
        
        conn.execute("""
            INSERT INTO marks (
                student_id, exam_name, academic_year,
                mathematics, english, science, computer_science, database_management, web_technology,
                total_marks, average, percentage, grade, result
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (student_id, exam_name, academic_year, math, eng, sci, cs, db, web, total, avg, perc, grade, result))
        conn.commit()
        conn.close()
        
        flash("Examination marks recorded successfully!", "success")
        return redirect(url_for('marks_list'))
        
    selected_student_id = request.args.get('student_id', '')
    conn.close()
    return render_template(
        'add_marks.html',
        active_page='marks',
        students=students,
        mark=None,
        selected_student_id=selected_student_id
    )

@app.route('/marks/edit/<int:mark_id>', methods=['GET', 'POST'])
@admin_required
def edit_marks(mark_id):
    conn = get_db_connection()
    mark = conn.execute("""
        SELECT m.*, s.name as student_name, s.register_number, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.id
        WHERE m.id = ?
    """, (mark_id,)).fetchone()
    
    if not mark:
        conn.close()
        flash("Examination mark record not found.", "danger")
        return redirect(url_for('marks_list'))
        
    if request.method == 'POST':
        exam_name = request.form.get('exam_name', mark['exam_name']).strip()
        academic_year = request.form.get('academic_year', mark['academic_year']).strip()
        
        math = float(request.form.get('mathematics', mark['mathematics']))
        eng = float(request.form.get('english', mark['english']))
        sci = float(request.form.get('science', mark['science']))
        cs = float(request.form.get('computer_science', mark['computer_science']))
        db = float(request.form.get('database_management', mark['database_management']))
        web = float(request.form.get('web_technology', mark['web_technology']))
        
        total, avg, perc, grade, result = calculate_exam_metrics(math, eng, sci, cs, db, web)
        
        conn.execute("""
            UPDATE marks SET
                exam_name = ?, academic_year = ?,
                mathematics = ?, english = ?, science = ?, computer_science = ?, 
                database_management = ?, web_technology = ?,
                total_marks = ?, average = ?, percentage = ?, grade = ?, result = ?
            WHERE id = ?
        """, (exam_name, academic_year, math, eng, sci, cs, db, web, total, avg, perc, grade, result, mark_id))
        conn.commit()
        conn.close()
        
        flash("Examination marks record updated successfully!", "success")
        return redirect(url_for('marks_list'))
        
    conn.close()
    return render_template('add_marks.html', active_page='marks', mark=mark, students=[])

@app.route('/marks/delete/<int:mark_id>', methods=['POST'])
@admin_required
def delete_marks(mark_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM marks WHERE id = ?", (mark_id,))
    conn.commit()
    conn.close()
    flash("Examination mark record deleted.", "info")
    return redirect(url_for('marks_list'))

# ==============================================================================
# Analytics Module
# ==============================================================================

@app.route('/analytics')
@admin_required
def analytics():
    conn = get_db_connection()
    
    # Overall statistics
    total_records = conn.execute("SELECT COUNT(*) as c FROM marks").fetchone()['c']
    overall_agg = conn.execute("""
        SELECT 
            AVG(percentage) as avg_p,
            MAX(percentage) as max_p,
            MIN(percentage) as min_p,
            SUM(CASE WHEN result = 'PASS' THEN 1 ELSE 0 END) as passed,
            SUM(CASE WHEN result = 'FAIL' THEN 1 ELSE 0 END) as failed
        FROM marks
    """).fetchone()
    
    passed = overall_agg['passed'] or 0
    failed = overall_agg['failed'] or 0
    
    overall = {
        'avg_percentage': round(overall_agg['avg_p'] or 0.0, 2),
        'highest_percentage': round(overall_agg['max_p'] or 0.0, 2),
        'lowest_percentage': round(overall_agg['min_p'] or 0.0, 2),
        'passed_count': passed,
        'failed_count': failed,
        'pass_percentage': round((passed / total_records * 100.0), 2) if total_records > 0 else 0.0,
        'fail_percentage': round((failed / total_records * 100.0), 2) if total_records > 0 else 0.0,
    }
    
    # Subject Statistics
    subjects = [
        ('mathematics', 'Mathematics'),
        ('english', 'English'),
        ('science', 'Science'),
        ('computer_science', 'Computer Science'),
        ('database_management', 'Database Management'),
        ('web_technology', 'Web Technology')
    ]
    
    subject_stats = []
    subject_names = []
    subject_mins = []
    subject_avgs = []
    subject_maxs = []
    
    for col, name in subjects:
        row = conn.execute(f"""
            SELECT 
                AVG({col}) as avg_score,
                MAX({col}) as max_score,
                MIN({col}) as min_score,
                SUM(CASE WHEN {col} >= 40 THEN 1 ELSE 0 END) as passed_sub
            FROM marks
        """).fetchone()
        
        avg_val = round(row['avg_score'] or 0.0, 2)
        max_val = round(row['max_score'] or 0.0, 2)
        min_val = round(row['min_score'] or 0.0, 2)
        passed_sub = row['passed_sub'] or 0
        pass_rate = round((passed_sub / total_records * 100.0), 2) if total_records > 0 else 0.0
        
        subject_stats.append({
            'name': name,
            'avg': avg_val,
            'highest': max_val,
            'lowest': min_val,
            'pass_rate': pass_rate
        })
        
        subject_names.append(name)
        subject_mins.append(min_val)
        subject_avgs.append(avg_val)
        subject_maxs.append(max_val)
        
    # Performance Categories
    cats = [
        ('Excellent', 'percentage >= 85 AND result = "PASS"', 'excellent', 'success', 'Percentage >= 85% with all courses passed'),
        ('Good', 'percentage >= 70 AND percentage < 85 AND result = "PASS"', 'good', 'primary', 'Percentage between 70% and 84.99%'),
        ('Average', 'percentage >= 55 AND percentage < 70 AND result = "PASS"', 'average', 'warning', 'Percentage between 55% and 69.99%'),
        ('Needs Improvement', 'percentage >= 40 AND percentage < 55 AND result = "PASS"', 'needs-imp', 'orange', 'Percentage between 40% and 54.99%'),
        ('Poor', 'result = "FAIL" OR percentage < 40', 'poor', 'danger', 'Score < 40% or failed any course course')
    ]
    
    category_stats = []
    for cat_name, condition, badge_cls, color_cls, crit in cats:
        count = conn.execute(f"SELECT COUNT(*) as c FROM marks WHERE {condition}").fetchone()['c']
        pct = round((count / total_records * 100.0), 2) if total_records > 0 else 0.0
        category_stats.append({
            'name': cat_name,
            'count': count,
            'percentage': pct,
            'badge_class': badge_cls,
            'color_class': color_cls,
            'criteria': crit
        })
        
    conn.close()
    
    return render_template(
        'analytics.html',
        active_page='analytics',
        overall=overall,
        subject_stats=subject_stats,
        subject_names=subject_names,
        subject_mins=subject_mins,
        subject_avgs=subject_avgs,
        subject_maxs=subject_maxs,
        category_stats=category_stats
    )

# ==============================================================================
# Machine Learning Prediction Module
# ==============================================================================

@app.route('/predictions')
@admin_required
def predictions():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    
    predictions_history = conn.execute("""
        SELECT p.*, s.name as student_name, s.register_number, s.department
        FROM predictions p
        JOIN students s ON p.student_id = s.id
        ORDER BY p.id DESC
        LIMIT 20
    """).fetchall()
    
    conn.close()
    return render_template(
        'predictions.html',
        active_page='predictions',
        students=students,
        predictions_history=predictions_history
    )

@app.route('/predict', methods=['POST'])
@app.route('/api/predict', methods=['POST'])
@login_required
def api_predict():
    data = request.get_json() or {}
    try:
        math = float(data.get('mathematics', 0))
        eng = float(data.get('english', 0))
        sci = float(data.get('science', 0))
        cs = float(data.get('computer_science', 0))
        db = float(data.get('database_management', 0))
        web = float(data.get('web_technology', 0))
        student_id = data.get('student_id')
        
        total = math + eng + sci + cs + db + web
        average = total / 6.0
        percentage = (total / Config.TOTAL_MAX_MARKS) * 100.0
        
        if student_id:
            result = get_student_multi_exam_prediction(student_id)
        else:
            result = get_ml_prediction(math, eng, sci, cs, db, web, average, percentage)
            result['used_exams_summary'] = "✓ Manual Score Inputs"
            
        result['percentage'] = percentage
        result['status'] = 'success'
        
        # Log prediction to database if valid student_id is provided
        if student_id:
            try:
                conn = get_db_connection()
                conn.execute("""
                    INSERT INTO predictions (student_id, prediction, confidence, model_version)
                    VALUES (?, ?, ?, ?)
                """, (student_id, result['prediction'], result['confidence'], result['model_version']))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[!] Warning: Could not log prediction to db: {e}")
                
        return jsonify(result)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/student-marks/<int:student_id>')
@login_required
def api_student_marks(student_id):
    # If student role, ensure they can only fetch their own marks
    if session.get('role') == 'student' and session.get('user_id') != student_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    conn = get_db_connection()
    marks = conn.execute("SELECT * FROM marks WHERE student_id = ? ORDER BY id DESC", (student_id,)).fetchall()
    conn.close()
    
    marks_list = [dict(m) for m in marks]
    return jsonify({'marks': marks_list})

# ==============================================================================
# PDF Reports Module
# ==============================================================================

@app.route('/reports')
@admin_required
def reports_hub():
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    
    selected_student_id = request.args.get('student_id')
    selected_student = None
    marks = []
    latest_mark = None
    ml_standing = None
    
    if selected_student_id:
        selected_student = conn.execute("SELECT * FROM students WHERE id = ?", (selected_student_id,)).fetchone()
        if selected_student:
            marks = conn.execute("SELECT * FROM marks WHERE student_id = ? ORDER BY id DESC", (selected_student_id,)).fetchall()
            if marks:
                latest_mark = marks[0]
                ml_standing = get_ml_prediction(
                    latest_mark['mathematics'], latest_mark['english'], latest_mark['science'],
                    latest_mark['computer_science'], latest_mark['database_management'], latest_mark['web_technology'],
                    latest_mark['average'], latest_mark['percentage']
                )
                
    conn.close()
    return render_template(
        'report.html',
        active_page='reports',
        students=students,
        selected_student=selected_student,
        marks=marks,
        latest_mark=latest_mark,
        ml_standing=ml_standing
    )

@app.route('/reports/download/<int:student_id>')
@login_required
def download_report(student_id):
    # Role check: Students can only download their own reports
    if session.get('role') == 'student' and session.get('user_id') != student_id:
        flash("You are not authorized to view another student's report.", "danger")
        return redirect(url_for('student_dashboard'))
        
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    
    if not student:
        conn.close()
        abort(404)
        
    mark_id = request.args.get('mark_id')
    if mark_id:
        mark = conn.execute("SELECT * FROM marks WHERE id = ? AND student_id = ?", (mark_id, student_id)).fetchone()
    else:
        mark = conn.execute("SELECT * FROM marks WHERE student_id = ? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
        
    conn.close()
    
    if not mark:
        flash("No examination marks available to generate a report.", "warning")
        if session.get('role') == 'student':
            return redirect(url_for('student_dashboard'))
        return redirect(url_for('reports_hub'))
        
    ml_prediction = get_ml_prediction(
        mark['mathematics'], mark['english'], mark['science'],
        mark['computer_science'], mark['database_management'], mark['web_technology'],
        mark['average'], mark['percentage']
    )
    
    pdf_path = generate_student_pdf_report(student, mark, ml_prediction)
    return send_file(pdf_path, as_attachment=True, download_name=f"Report_{student['register_number']}.pdf")

# ==============================================================================
# Student Portal Routes
# ==============================================================================

@app.route('/student/dashboard')
@student_required
def student_dashboard():
    student_id = session.get('user_id')
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()
    
    exam_history = get_student_exam_history(student_id)
    all_marks = exam_history['all']
    
    selected_exam = request.args.get('exam', 'CIA1').upper()
    if selected_exam not in Config.EXAM_TYPES:
        selected_exam = 'CIA1'
        
    active_mark = exam_history.get(selected_exam)
    
    ml_standing = None
    if active_mark:
        ml_standing = get_ml_prediction(
            active_mark['mathematics'], active_mark['english'], active_mark['science'],
            active_mark['computer_science'], active_mark['database_management'], active_mark['web_technology'],
            active_mark['average'], active_mark['percentage']
        )
    elif all_marks:
        ml_standing = get_student_multi_exam_prediction(student_id)
        
    # Study planner integration
    try:
        generate_reminders(student_id)
        check_missed_sessions()
    except Exception:
        pass

    study_analysis = analyze_weak_subjects(student_id)
    today_study_sessions = get_today_schedule(student_id)
    study_progress = get_study_progress(student_id)
    upcoming_study_sessions = get_upcoming_sessions(student_id, limit=3)

    return render_template(
        'student_dashboard.html',
        active_page='student_dashboard',
        student=student,
        exam_history=exam_history,
        selected_exam=selected_exam,
        active_mark=active_mark,
        latest_mark=active_mark or (all_marks[0] if all_marks else None),
        all_marks=all_marks,
        ml_standing=ml_standing,
        study_analysis=study_analysis,
        today_study_sessions=today_study_sessions,
        study_progress=study_progress,
        upcoming_study_sessions=upcoming_study_sessions
    )

@app.route('/student/marks')
@student_required
def student_marks():
    return redirect(url_for('student_dashboard'))

@app.route('/student/performance')
@student_required
def student_performance():
    return redirect(url_for('student_performance_page'))

@app.route('/student/prediction')
@student_required
def student_prediction():
    return redirect(url_for('student_dashboard'))

@app.route('/student/report')
@student_required
def student_report():
    return redirect(url_for('download_report', student_id=session.get('user_id')))

# ==============================================================================
# Profile Management
# ==============================================================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session.get('user_id')
    role = session.get('role')
    conn = get_db_connection()
    
    if request.method == 'POST':
        new_pwd = request.form.get('new_password', '').strip()
        confirm_pwd = request.form.get('confirm_password', '').strip()
        
        if new_pwd:
            if new_pwd != confirm_pwd:
                flash("New passwords do not match. Please re-enter.", "danger")
            else:
                pwd_hash = generate_password_hash(new_pwd)
                if role == 'admin':
                    conn.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
                else:
                    conn.execute("UPDATE students SET password_hash = ? WHERE id = ?", (pwd_hash, user_id))
                conn.commit()
                flash("Password updated successfully!", "success")
                
        if role == 'student':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            if name and email:
                conn.execute("UPDATE students SET name = ?, email = ?, phone = ? WHERE id = ?", (name, email, phone, user_id))
                conn.commit()
                session['user_name'] = name
                flash("Contact details updated successfully!", "success")
                
    if role == 'admin':
        user = conn.execute("SELECT * FROM admins WHERE id = ?", (user_id,)).fetchone()
    else:
        user = conn.execute("SELECT * FROM students WHERE id = ?", (user_id,)).fetchone()
        
    conn.close()
    return render_template('profile.html', active_page='profile', user=user)

# ==============================================================================
# Multi-Examination Management & Excel Import Routes
# ==============================================================================

@app.route('/exam/<exam_type>')
@admin_required
def exam_view(exam_type):
    exam_type_upper = exam_type.upper()
    if exam_type_upper not in Config.EXAM_TYPES:
        abort(404)
        
    exam_label = Config.EXAM_LABELS[exam_type_upper]
    conn = get_db_connection()
    marks = conn.execute("""
        SELECT m.*, s.name as student_name, s.register_number, s.department
        FROM marks m
        JOIN students s ON m.student_id = s.id
        WHERE UPPER(m.exam_type) = ?
        ORDER BY LOWER(s.name) ASC
    """, (exam_type_upper,)).fetchall()
    
    total_count = len(marks)
    if total_count > 0:
        avg_percentage = round(sum(m['percentage'] for m in marks) / total_count, 2)
        highest_score = round(max(m['percentage'] for m in marks), 2)
        lowest_score = round(min(m['percentage'] for m in marks), 2)
    else:
        avg_percentage = 0.0
        highest_score = 0.0
        lowest_score = 0.0
        
    subject_averages = []
    for key, name in [('mathematics', 'Mathematics'), ('english', 'English'), ('science', 'Science'),
                      ('computer_science', 'Computer Science'), ('database_management', 'Database Management'),
                      ('web_technology', 'Web Technology')]:
        if total_count > 0:
            avg_val = round(sum(m[key] for m in marks) / total_count, 2)
        else:
            avg_val = 0.0
        subject_averages.append({'name': name, 'avg': avg_val})
        
    conn.close()
    return render_template(
        'exam_view.html',
        active_page=exam_type.lower(),
        exam_type=exam_type_upper,
        exam_label=exam_label,
        marks=marks,
        total_count=total_count,
        avg_percentage=avg_percentage,
        highest_score=highest_score,
        lowest_score=lowest_score,
        subject_averages=subject_averages
    )

@app.route('/upload/<exam_type>')
@admin_required
def upload_exam_page(exam_type):
    exam_type_upper = exam_type.upper()
    if exam_type_upper not in ['CIA2', 'MODEL']:
        flash("CIA 1 dataset is already imported. You can upload CIA 2 or Model Exam files.", "info")
        return redirect(url_for('dashboard'))
        
    exam_label = Config.EXAM_LABELS[exam_type_upper]
    return render_template(
        'upload_exam.html',
        active_page=exam_type.lower(),
        exam_type=exam_type_upper,
        exam_label=exam_label
    )

@app.route('/api/upload/preview', methods=['POST'])
@admin_required
def api_upload_preview():
    if 'excel_file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No Excel file provided.'}), 400
        
    file = request.files['excel_file']
    exam_type = request.form.get('exam_type', 'CIA2').upper()
    
    if not file.filename:
        return jsonify({'status': 'error', 'message': 'No file selected.'}), 400
        
    try:
        df = pd.read_excel(file)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Failed to parse Excel file: {str(e)}'}), 400
        
    def clean_key(val):
        return str(val).strip().lower().replace('_', '').replace('.', '').replace('-', '').replace(' ', '')

    def find_col(possible_aliases):
        clean_aliases = [clean_key(a) for a in possible_aliases]
        for col in df.columns:
            cleaned_col = clean_key(col)
            for alias in clean_aliases:
                if alias == cleaned_col or alias in cleaned_col or (len(alias) >= 3 and cleaned_col in alias):
                    return col
        return None
        
    reg_col = find_col(['register number', 'register no', 'reg no', 'regno', 'register_no', 'reg_no', 'roll no', 'student id', 'reg number'])
    name_col = find_col(['student name', 'name', 'student_name', 'full name'])
    
    math_col = find_col(['mathematics', 'maths', 'math', 'mathematics mark'])
    eng_col = find_col(['english', 'eng', 'english mark'])
    sci_col = find_col(['science', 'sci', 'science mark'])
    cs_col = find_col(['computer science', 'cs', 'comp sci', 'computer science mark'])
    db_col = find_col(['database management', 'dbms', 'database', 'db', 'database management system mark'])
    web_col = find_col(['web technology', 'web technologies', 'web tech', 'web', 'web technologies mark'])
    
    if not reg_col:
        return jsonify({'status': 'error', 'message': 'Could not identify Register Number column in Excel sheet.'}), 400
        
    conn = get_db_connection()
    students_db = conn.execute("SELECT id, register_number, name FROM students").fetchall()
    conn.close()
    
    db_student_map = {s['register_number'].strip().upper(): s for s in students_db}
    
    total_rows = len(df)
    matched_count = 0
    unmatched_count = 0
    invalid_count = 0
    unmatched_reg_numbers = []
    preview_rows = []
    
    seen_regs = set()
    
    for idx, row in df.iterrows():
        raw_reg = str(row[reg_col]).strip().upper() if pd.notna(row[reg_col]) else ""
        if not raw_reg or raw_reg == "NAN":
            invalid_count += 1
            continue
            
        if raw_reg in seen_regs:
            invalid_count += 1
            continue
        seen_regs.add(raw_reg)
        
        raw_name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown Student"
        
        def safe_float(col_name):
            if col_name and col_name in df.columns and pd.notna(row[col_name]):
                try:
                    v = float(row[col_name])
                    return max(0.0, min(100.0, v))
                except Exception:
                    return 70.0
            return 70.0
            
        math_v = safe_float(math_col)
        eng_v = safe_float(eng_col)
        sci_v = safe_float(sci_col)
        cs_v = safe_float(cs_col)
        db_v = safe_float(db_col)
        web_v = safe_float(web_col)
        
        total, avg, perc, grade, result = calculate_exam_metrics(math_v, eng_v, sci_v, cs_v, db_v, web_v)
        
        db_match = db_student_map.get(raw_reg)
        if db_match:
            matched_count += 1
            preview_rows.append({
                'is_matched': True,
                'student_id': db_match['id'],
                'register_number': raw_reg,
                'student_name': db_match['name'],
                'mathematics': math_v,
                'english': eng_v,
                'science': sci_v,
                'computer_science': cs_v,
                'database_management': db_v,
                'web_technology': web_v,
                'total_marks': total,
                'average': avg,
                'percentage': perc,
                'grade': grade,
                'result': result
            })
        else:
            unmatched_count += 1
            unmatched_reg_numbers.append(raw_reg)
            preview_rows.append({
                'is_matched': False,
                'student_id': None,
                'register_number': raw_reg,
                'student_name': raw_name,
                'mathematics': math_v,
                'english': eng_v,
                'science': sci_v,
                'computer_science': cs_v,
                'database_management': db_v,
                'web_technology': web_v,
                'total_marks': total,
                'average': avg,
                'percentage': perc,
                'grade': grade,
                'result': result
            })
            
    return jsonify({
        'status': 'success',
        'exam_type': exam_type,
        'summary': {
            'total_rows': total_rows,
            'matched_count': matched_count,
            'unmatched_count': unmatched_count,
            'invalid_count': invalid_count,
            'unmatched_register_numbers': unmatched_reg_numbers
        },
        'preview_rows': preview_rows
    })

@app.route('/api/upload/confirm', methods=['POST'])
@admin_required
def api_upload_confirm():
    data = request.get_json() or {}
    exam_type = data.get('exam_type', 'CIA2').upper()
    rows = data.get('rows', [])
    
    if not rows:
        return jsonify({'status': 'error', 'message': 'No valid data to import.'}), 400
        
    exam_label = Config.EXAM_LABELS.get(exam_type, exam_type)
    exam_name = f"{exam_label} Examination"
    academic_year = "2025-2026"
    
    conn = get_db_connection()
    imported_count = 0
    
    for r in rows:
        if not r.get('is_matched') or not r.get('student_id'):
            continue
            
        s_id = r['student_id']
        math_v = float(r['mathematics'])
        eng_v = float(r['english'])
        sci_v = float(r['science'])
        cs_v = float(r['computer_science'])
        db_v = float(r['database_management'])
        web_v = float(r['web_technology'])
        
        total, avg, perc, grade, result = calculate_exam_metrics(math_v, eng_v, sci_v, cs_v, db_v, web_v)
        
        existing = conn.execute("SELECT id FROM marks WHERE student_id = ? AND UPPER(exam_type) = ?", (s_id, exam_type)).fetchone()
        
        if existing:
            conn.execute("""
                UPDATE marks SET
                    exam_name = ?, academic_year = ?, mathematics = ?, english = ?, science = ?,
                    computer_science = ?, database_management = ?, web_technology = ?,
                    total_marks = ?, average = ?, percentage = ?, grade = ?, result = ?
                WHERE id = ?
            """, (exam_name, academic_year, math_v, eng_v, sci_v, cs_v, db_v, web_v, total, avg, perc, grade, result, existing['id']))
        else:
            conn.execute("""
                INSERT INTO marks (
                    student_id, exam_name, exam_type, academic_year,
                    mathematics, english, science, computer_science, database_management, web_technology,
                    total_marks, average, percentage, grade, result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (s_id, exam_name, exam_type, academic_year, math_v, eng_v, sci_v, cs_v, db_v, web_v, total, avg, perc, grade, result))
            
        imported_count += 1
        
    conn.commit()
    conn.close()
    
    flash(f"Successfully imported {imported_count} student marks for {exam_label}. CIA 1 marks remain intact.", "success")
    return jsonify({
        'status': 'success',
        'imported_count': imported_count,
        'redirect_url': url_for('exam_view', exam_type=exam_type.lower())
    })

@app.route('/performance-analysis')
@admin_required
def performance_analysis():
    selected_exam = request.args.get('exam', 'ALL').upper()
    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY LOWER(name) ASC").fetchall()
    
    exam_averages = {}
    for et in ['CIA1', 'CIA2', 'MODEL']:
        res = conn.execute("SELECT AVG(percentage) as avg_p FROM marks WHERE UPPER(exam_type) = ?", (et,)).fetchone()
        if res and res['avg_p'] is not None:
            exam_averages[et] = round(res['avg_p'], 2)
        else:
            exam_averages[et] = None
            
    subjects = [
        ('mathematics', 'Mathematics'),
        ('english', 'English'),
        ('science', 'Science'),
        ('computer_science', 'Computer Science'),
        ('database_management', 'Database Management'),
        ('web_technology', 'Web Technology')
    ]
    
    subject_comparisons = []
    for col, name in subjects:
        c1 = conn.execute(f"SELECT AVG({col}) as a FROM marks WHERE UPPER(exam_type) = 'CIA1'").fetchone()['a']
        c2 = conn.execute(f"SELECT AVG({col}) as a FROM marks WHERE UPPER(exam_type) = 'CIA2'").fetchone()['a']
        cm = conn.execute(f"SELECT AVG({col}) as a FROM marks WHERE UPPER(exam_type) = 'MODEL'").fetchone()['a']
        
        c1_val = round(c1, 2) if c1 is not None else 'N/A'
        c2_val = round(c2, 2) if c2 is not None else 'N/A'
        cm_val = round(cm, 2) if cm is not None else 'N/A'
        
        vals = [v for v in [c1_val, c2_val, cm_val] if isinstance(v, (int, float))]
        if len(vals) >= 2:
            diff = vals[-1] - vals[0]
            status = 'Improving' if diff > 1.0 else ('Declining' if diff < -1.0 else 'Stable')
        else:
            status = 'Stable'
            
        subject_comparisons.append({
            'name': name,
            'cia1': c1_val,
            'cia2': c2_val,
            'model': cm_val,
            'status': status
        })
        
    student_trends = []
    for s in students:
        t = calculate_student_trend(s['id'])
        student_trends.append({
            'id': s['id'],
            'register_number': s['register_number'],
            'name': s['name'],
            'department': s['department'],
            'cia1_perc': t['cia1_perc'],
            'cia2_perc': t['cia2_perc'],
            'model_perc': t['model_perc'],
            'status': t['status']
        })
        
    weak_exam_filter = selected_exam if selected_exam in ['CIA1', 'CIA2', 'MODEL'] else None
    weak_students = get_weak_students(weak_exam_filter)
    conn.close()
    
    student_id_arg = request.args.get('student_id')
    selected_student_id = None
    if student_id_arg:
        try:
            selected_student_id = int(student_id_arg)
        except (ValueError, TypeError):
            selected_student_id = None
    elif students:
        selected_student_id = students[0]['id']
        
    student_analysis = get_detailed_student_performance_analysis(selected_student_id) if selected_student_id else None
    
    return render_template(
        'performance_analysis.html',
        active_page='performance_analysis',
        selected_exam=selected_exam,
        exam_averages=exam_averages,
        subject_comparisons=subject_comparisons,
        student_trends=student_trends,
        weak_students=weak_students,
        students=students,
        selected_student_id=selected_student_id,
        student_analysis=student_analysis
    )

@app.route('/student/exam/<exam_type>')
@student_required
def student_exam_page(exam_type):
    exam_type_upper = exam_type.upper()
    if exam_type_upper not in Config.EXAM_TYPES:
        abort(404)
        
    exam_label = Config.EXAM_LABELS[exam_type_upper]
    student_id = session.get('user_id')
    history = get_student_exam_history(student_id)
    mark = history.get(exam_type_upper)
    
    return render_template(
        'student_exam_view.html',
        active_page=f'student_{exam_type.lower()}',
        exam_type=exam_type_upper,
        exam_label=exam_label,
        mark=mark
    )

@app.route('/student/performance-overview')
@student_required
def student_performance_page():
    student_id = session.get('user_id')
    trend = calculate_student_trend(student_id)
    history = trend['history']
    
    cia1 = history.get('CIA1')
    cia2 = history.get('CIA2')
    model = history.get('MODEL')
    
    subject_scores = []
    subjects = [
        ('mathematics', 'Mathematics'),
        ('english', 'English'),
        ('science', 'Science'),
        ('computer_science', 'Computer Science'),
        ('database_management', 'Database Management'),
        ('web_technology', 'Web Technology')
    ]
    
    for col, name in subjects:
        v1 = cia1[col] if cia1 else 0
        v2 = cia2[col] if cia2 else None
        vm = model[col] if model else None
        
        last_val = vm if vm is not None else (v2 if v2 is not None else v1)
        diff = round(last_val - v1, 1)
        
        subject_scores.append({
            'name': name,
            'cia1': v1,
            'cia2': v2 if v2 is not None else 'N/A',
            'model': vm if vm is not None else 'N/A',
            'diff': diff
        })
        
    student_analysis = get_detailed_student_performance_analysis(student_id)
    
    return render_template(
        'student_performance.html',
        active_page='student_performance',
        trend=trend,
        subject_scores=subject_scores,
        student_analysis=student_analysis
    )

# ==============================================================================
# Template Context Processor for Notification Count
# ==============================================================================

@app.context_processor
def inject_notification_count():
    """Makes unread notification count available in all templates."""
    if session.get('role') == 'student' and 'user_id' in session:
        try:
            count = get_unread_notification_count(session['user_id'])
            return {'unread_notification_count': count}
        except Exception:
            return {'unread_notification_count': 0}
    return {'unread_notification_count': 0}

# ==============================================================================
# Study Planner Routes — Student Portal
# ==============================================================================

@app.route('/student/study-planner')
@student_required
def student_study_planner():
    """Main study planner page for students."""
    student_id = session.get('user_id')
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()

    # Generate reminders on page load as fallback
    try:
        generate_reminders(student_id)
        check_missed_sessions()
    except Exception:
        pass

    analysis = analyze_weak_subjects(student_id)
    prefs = get_study_preferences(student_id)
    today_sessions = get_today_schedule(student_id)
    upcoming = get_upcoming_sessions(student_id, limit=5)
    progress = get_study_progress(student_id)
    recommendations = get_study_recommendations(student_id)

    # Get the current week schedule
    week_schedule = get_student_schedule(student_id, view='week')

    return render_template(
        'study_planner.html',
        active_page='study_planner',
        student=student,
        analysis=analysis,
        preferences=prefs,
        today_sessions=today_sessions,
        upcoming_sessions=upcoming,
        progress=progress,
        recommendations=recommendations,
        week_schedule=week_schedule
    )


@app.route('/student/study-planner/preferences', methods=['GET', 'POST'])
@student_required
def student_study_preferences():
    """Study preferences configuration page."""
    student_id = session.get('user_id')

    if request.method == 'POST':
        days = request.form.getlist('available_days')
        if not days:
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

        data = {
            'available_days': days,
            'preferred_start_time': request.form.get('preferred_start_time', '18:00'),
            'preferred_end_time': request.form.get('preferred_end_time', '22:00'),
            'max_daily_duration_minutes': request.form.get('max_daily_duration_minutes', 240),
            'session_duration_minutes': request.form.get('session_duration_minutes', 45),
            'break_duration_minutes': request.form.get('break_duration_minutes', 15),
            'reminder_minutes_before': request.form.get('reminder_minutes_before', 15)
        }

        save_study_preferences(student_id, data)
        flash("Study preferences saved successfully!", "success")
        return redirect(url_for('student_study_planner'))

    prefs = get_study_preferences(student_id)
    return render_template(
        'study_preferences.html',
        active_page='study_preferences',
        preferences=prefs
    )


@app.route('/student/study-planner/generate', methods=['POST'])
@student_required
def student_generate_timetable():
    """Generates a new study timetable."""
    student_id = session.get('user_id')
    result = generate_study_timetable(student_id)

    if result.get('message'):
        flash(result['message'], "warning")
    else:
        flash(f"Study timetable generated successfully! {result.get('total_sessions', 0)} sessions scheduled.", "success")

    return redirect(url_for('student_study_planner'))


@app.route('/student/study-planner/schedule')
@student_required
def student_view_schedule():
    """View detailed schedule with different views."""
    student_id = session.get('user_id')
    view = request.args.get('view', 'week')
    target_date = request.args.get('date')

    schedule = get_student_schedule(student_id, view=view, target_date=target_date)
    prefs = get_study_preferences(student_id)
    progress = get_study_progress(student_id)

    return render_template(
        'study_schedule.html',
        active_page='study_schedule',
        schedule=schedule,
        current_view=view,
        target_date=target_date,
        preferences=prefs,
        progress=progress
    )


@app.route('/api/study-planner/session/<int:session_id>/status', methods=['POST'])
@student_required
def api_update_session_status(session_id):
    """API to update a study session's status."""
    student_id = session.get('user_id')
    data = request.get_json() or {}
    new_status = data.get('status')

    if not new_status:
        return jsonify({'status': 'error', 'message': 'Status is required.'}), 400

    success, message = update_session_status(session_id, student_id, new_status)

    if success:
        return jsonify({'status': 'success', 'message': message})
    else:
        return jsonify({'status': 'error', 'message': message}), 400


@app.route('/api/study-planner/session/<int:session_id>/reschedule', methods=['POST'])
@student_required
def api_reschedule_session(session_id):
    """API to reschedule a study session."""
    student_id = session.get('user_id')
    data = request.get_json() or {}
    new_date = data.get('new_date')
    new_start_time = data.get('new_start_time')

    if not new_date or not new_start_time:
        return jsonify({'status': 'error', 'message': 'New date and start time are required.'}), 400

    conn = get_db_connection()
    sess = conn.execute(
        "SELECT * FROM study_schedule WHERE id = ? AND student_id = ?",
        (session_id, student_id)
    ).fetchone()

    if not sess:
        conn.close()
        return jsonify({'status': 'error', 'message': 'Session not found.'}), 404

    # Calculate new end time based on session duration
    prefs = get_study_preferences(student_id)
    session_minutes = prefs['session_duration_minutes']
    new_start = datetime.strptime(new_start_time, '%H:%M')
    new_end = new_start + timedelta(minutes=session_minutes)

    conn.execute('''
        UPDATE study_schedule SET
            scheduled_date = ?, start_time = ?, end_time = ?, status = 'Scheduled'
        WHERE id = ? AND student_id = ?
    ''', (new_date, new_start_time, new_end.strftime('%H:%M'), session_id, student_id))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': 'Session rescheduled successfully.'})


# ==============================================================================
# Notification Routes
# ==============================================================================

@app.route('/api/notifications')
@student_required
def api_get_notifications():
    """API to get student notifications."""
    student_id = session.get('user_id')
    notifications = get_student_notifications(student_id)
    unread_count = get_unread_notification_count(student_id)
    return jsonify({
        'status': 'success',
        'notifications': notifications,
        'unread_count': unread_count
    })


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@student_required
def api_mark_notification_read(notification_id):
    """API to mark a notification as read."""
    student_id = session.get('user_id')
    mark_notification_read(notification_id, student_id)
    return jsonify({'status': 'success'})


@app.route('/api/notifications/read-all', methods=['POST'])
@student_required
def api_mark_all_read():
    """API to mark all notifications as read."""
    student_id = session.get('user_id')
    mark_all_notifications_read(student_id)
    return jsonify({'status': 'success'})


# ==============================================================================
# Faculty Study Planner Monitoring Routes
# ==============================================================================

@app.route('/admin/student-study-plan/<int:student_id>')
@admin_required
def admin_view_student_study_plan(student_id):
    """Faculty view of a student's study plan."""
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    conn.close()

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('students_list'))

    overview = get_student_study_overview_for_faculty(student_id)
    analysis = analyze_weak_subjects(student_id)
    progress = get_study_progress(student_id)
    schedule = get_student_schedule(student_id, view='all')

    return render_template(
        'admin_study_plan.html',
        active_page='students',
        student=student,
        overview=overview,
        analysis=analysis,
        progress=progress,
        schedule=schedule
    )


# ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# ==============================================================================
# Application Startup
# ==============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("EXAMINATION PERFORMANCE ANALYSIS USING MACHINE LEARNING")
    print("=" * 60)
    print(f"[*] Access Portal at: http://127.0.0.1:5000")
    print(f"[*] Default Admin: admin / admin123")
    print(f"[*] Student Login: 927624BIT001 / student123")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=True)
