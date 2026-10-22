"""
AI-Based Personalized Study Planner and Smart Reminder System
=============================================================
Core module for:
  - Weak subject identification (Module 1)
  - Personalized timetable generation (Module 2)
  - Study session tracking (Module 5)
  - Smart notifications / reminders (Module 4)
  - Personalized study recommendations (Module 6)

Integrates with the existing Performance Analysis module and MySQL/SQLite database.
"""

import os
import json
from datetime import datetime, timedelta, date, time as dtime
from config import Config
from database import get_db_connection, get_student_exam_history

# ==============================================================================
# Database Schema Setup for Study Planner
# ==============================================================================

def init_study_planner_tables():
    """Creates study planner tables if they do not exist. Safe to call multiple times."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Student Study Preferences
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE,
            available_days TEXT NOT NULL DEFAULT '["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"]',
            preferred_start_time TEXT NOT NULL DEFAULT '18:00',
            preferred_end_time TEXT NOT NULL DEFAULT '22:00',
            max_daily_duration_minutes INTEGER NOT NULL DEFAULT 240,
            session_duration_minutes INTEGER NOT NULL DEFAULT 45,
            break_duration_minutes INTEGER NOT NULL DEFAULT 15,
            reminder_minutes_before INTEGER NOT NULL DEFAULT 15,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
    ''')

    # 2. Study Schedule
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_key TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            study_activity TEXT NOT NULL DEFAULT 'Concept Revision',
            priority TEXT NOT NULL DEFAULT 'Medium',
            status TEXT NOT NULL DEFAULT 'Scheduled',
            completion_timestamp TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE
        )
    ''')

    # 3. Notifications
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            schedule_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT NOT NULL DEFAULT 'reminder',
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
            FOREIGN KEY (schedule_id) REFERENCES study_schedule (id) ON DELETE SET NULL
        )
    ''')

    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_student_date ON study_schedule (student_id, scheduled_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_schedule_status ON study_schedule (status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_student ON notifications (student_id, is_read)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_notifications_schedule ON notifications (schedule_id)')

    conn.commit()
    conn.close()
    print("[*] Study planner tables initialized.")


# ==============================================================================
# MODULE 1: Automatic Identification of Weak Subjects
# ==============================================================================

# Study activity recommendations mapped by subject key
STUDY_ACTIVITIES = {
    'mathematics': {
        'revision': 'Revise fundamental theorems and formulas',
        'practice': 'Practise numerical problems and past papers',
        'concept': 'Study core algebraic and calculus concepts',
        'maintain': 'Solve advanced problems and explore applications'
    },
    'english': {
        'revision': 'Revise grammar rules and vocabulary',
        'practice': 'Practise comprehension and essay writing',
        'concept': 'Study sentence structures and formal writing',
        'maintain': 'Read technical articles and practise summaries'
    },
    'science': {
        'revision': 'Revise fundamental laws and derivations',
        'practice': 'Practise numerical problems and diagrams',
        'concept': 'Study core scientific principles and units',
        'maintain': 'Explore real-world applications and experiments'
    },
    'computer_science': {
        'revision': 'Revise algorithms and data structures',
        'practice': 'Code implementations and trace programs',
        'concept': 'Study OOP principles and programming logic',
        'maintain': 'Solve coding challenges and build mini-projects'
    },
    'database_management': {
        'revision': 'Revise SQL queries and normalization rules',
        'practice': 'Practise writing complex queries and ER diagrams',
        'concept': 'Study relational algebra and ACID properties',
        'maintain': 'Explore advanced indexing and query optimization'
    },
    'web_technology': {
        'revision': 'Revise HTML/CSS fundamentals and DOM concepts',
        'practice': 'Build interactive web components and layouts',
        'concept': 'Study client-server architecture and REST APIs',
        'maintain': 'Explore modern frameworks and responsive design'
    }
}


def analyze_weak_subjects(student_id):
    """
    Analyzes a student's subject-wise performance across CIA1, CIA2, and MODEL exams.
    Returns a list of subjects with performance status, priority, reason, and recommended action.
    Does NOT assume missing marks are zero. Does NOT classify as declining with < 2 exams.
    """
    history = get_student_exam_history(student_id)
    available_exam_types = [et for et in ['CIA1', 'CIA2', 'MODEL'] if history.get(et) is not None]

    if not available_exam_types:
        return {
            'subjects': [],
            'weak_subjects': [],
            'high_priority_count': 0,
            'available_exams': 0,
            'message': 'No examination records are available for this student. Performance analysis requires at least one examination record.'
        }

    subject_definitions = [
        ('mathematics', 'Mathematics', 'fa-calculator'),
        ('english', 'English', 'fa-book-open'),
        ('science', 'Science', 'fa-atom'),
        ('computer_science', 'Computer Science', 'fa-laptop-code'),
        ('database_management', 'Database Management', 'fa-database'),
        ('web_technology', 'Web Technology', 'fa-globe')
    ]

    subjects_analysis = []

    for key, name, icon in subject_definitions:
        # Collect scores across available exams
        scores = []
        for et in ['CIA1', 'CIA2', 'MODEL']:
            if history.get(et) is not None:
                scores.append({
                    'exam_type': et,
                    'label': Config.EXAM_LABELS.get(et, et),
                    'score': history[et][key]
                })

        if not scores:
            continue

        latest_score = scores[-1]['score']
        first_score = scores[0]['score']

        # Determine performance status
        if len(scores) >= 2:
            diff = latest_score - first_score
            # Check for consistent decline across exams
            all_declining = all(
                scores[i]['score'] < scores[i - 1]['score']
                for i in range(1, len(scores))
            )
            all_improving = all(
                scores[i]['score'] > scores[i - 1]['score']
                for i in range(1, len(scores))
            )

            if all_declining and abs(diff) > 1.5:
                performance = 'Declining'
            elif all_improving and diff > 1.5:
                performance = 'Improving'
            elif abs(diff) <= 1.5:
                performance = 'Stable'
            elif diff > 1.5:
                performance = 'Improving'
            elif diff < -1.5:
                performance = 'Declining'
            else:
                performance = 'Stable'
        else:
            performance = 'Baseline'

        # Determine priority
        is_failing = latest_score < Config.PASS_MARK_PER_SUBJECT
        is_low = latest_score < 55
        is_declining = performance == 'Declining'

        if is_failing:
            priority = 'Critical'
            priority_class = 'danger'
            reason = f"Current score ({latest_score:.1f}/100) is below the pass threshold ({Config.PASS_MARK_PER_SUBJECT}). Immediate remediation required."
            recommended_action = STUDY_ACTIVITIES[key]['concept'] + '. ' + STUDY_ACTIVITIES[key]['practice']
        elif is_declining:
            drop = abs(latest_score - first_score)
            priority = 'High'
            priority_class = 'warning'
            reason = f"Marks have decreased by {drop:.1f} across available examinations ({scores[0]['label']}: {first_score:.1f} → {scores[-1]['label']}: {latest_score:.1f})."
            recommended_action = STUDY_ACTIVITIES[key]['revision'] + '. ' + STUDY_ACTIVITIES[key]['practice']
        elif is_low:
            priority = 'Medium'
            priority_class = 'warning'
            reason = f"Score of {latest_score:.1f}/100 is in the low-performance bracket. Reinforcement needed to prevent future failure."
            recommended_action = STUDY_ACTIVITIES[key]['revision']
        elif performance == 'Improving':
            priority = 'Low'
            priority_class = 'success'
            improvement = latest_score - first_score
            reason = f"Performance is improving (+{improvement:.1f} marks). Maintain current study routine."
            recommended_action = STUDY_ACTIVITIES[key]['maintain']
        elif performance == 'Baseline':
            if latest_score >= 75:
                priority = 'Low'
                priority_class = 'success'
                reason = f"Strong baseline score ({latest_score:.1f}/100) established. Maintain consistency."
                recommended_action = STUDY_ACTIVITIES[key]['maintain']
            elif latest_score >= 55:
                priority = 'Medium'
                priority_class = 'info'
                reason = f"Baseline score ({latest_score:.1f}/100). Additional exams needed to determine trend."
                recommended_action = STUDY_ACTIVITIES[key]['revision']
            else:
                priority = 'High'
                priority_class = 'warning'
                reason = f"Low baseline score ({latest_score:.1f}/100). Focus on fundamentals."
                recommended_action = STUDY_ACTIVITIES[key]['concept'] + '. ' + STUDY_ACTIVITIES[key]['practice']
        else:
            # Stable
            if latest_score >= 75:
                priority = 'Low'
                priority_class = 'success'
                reason = f"Stable and strong performance ({latest_score:.1f}/100). Continue current approach."
                recommended_action = STUDY_ACTIVITIES[key]['maintain']
            elif latest_score >= 55:
                priority = 'Medium'
                priority_class = 'info'
                reason = f"Stable performance ({latest_score:.1f}/100) but room for improvement."
                recommended_action = STUDY_ACTIVITIES[key]['revision']
            else:
                priority = 'High'
                priority_class = 'warning'
                reason = f"Consistently low scores ({latest_score:.1f}/100). Structured revision recommended."
                recommended_action = STUDY_ACTIVITIES[key]['concept'] + '. ' + STUDY_ACTIVITIES[key]['practice']

        avg_score = sum(s['score'] for s in scores) / len(scores) if scores else latest_score
        is_weak_flag = priority in ['Critical', 'High'] or latest_score < 50 or performance == 'Declining'
        allocated_hours = 3.5 if priority in ['Critical', 'High'] else (2.5 if priority == 'Medium' else 1.5)

        subjects_analysis.append({
            'key': key,
            'name': name,
            'icon': icon,
            'scores': scores,
            'latest_score': latest_score,
            'average': avg_score,
            'performance': performance,
            'trend_status': performance,
            'priority': priority,
            'priority_class': priority_class,
            'is_weak': is_weak_flag,
            'allocated_hours_per_week': allocated_hours,
            'reason': reason,
            'recommended_action': recommended_action
        })

    # Sort by priority: Critical > High > Medium > Low
    priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
    subjects_analysis.sort(key=lambda s: (priority_order.get(s['priority'], 4), -s['latest_score'] if s['priority'] == 'Low' else s['latest_score']))

    weak_subjects = [s for s in subjects_analysis if s['is_weak']]
    high_priority_count = sum(1 for s in subjects_analysis if s['priority'] in ['Critical', 'High'])

    return {
        'subjects': subjects_analysis,
        'weak_subjects': weak_subjects,
        'high_priority_count': high_priority_count,
        'available_exams': len(available_exam_types),
        'available_exam_types': available_exam_types,
        'message': None
    }


# ==============================================================================
# MODULE 2: Personalized Study Timetable Generation
# ==============================================================================

def get_study_preferences(student_id):
    """Retrieves student study preferences or returns defaults."""
    conn = get_db_connection()
    prefs = conn.execute(
        "SELECT * FROM study_preferences WHERE student_id = ?", (student_id,)
    ).fetchone()
    conn.close()

    if prefs:
        return {
            'id': prefs['id'],
            'student_id': prefs['student_id'],
            'available_days': json.loads(prefs['available_days']),
            'preferred_start_time': prefs['preferred_start_time'],
            'preferred_end_time': prefs['preferred_end_time'],
            'max_daily_duration_minutes': prefs['max_daily_duration_minutes'],
            'session_duration_minutes': prefs['session_duration_minutes'],
            'break_duration_minutes': prefs['break_duration_minutes'],
            'reminder_minutes_before': prefs['reminder_minutes_before'],
            'is_default': False
        }

    # Default preferences
    return {
        'id': None,
        'student_id': student_id,
        'available_days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
        'preferred_start_time': '18:00',
        'preferred_end_time': '22:00',
        'max_daily_duration_minutes': 240,
        'session_duration_minutes': 45,
        'break_duration_minutes': 15,
        'reminder_minutes_before': 15,
        'is_default': True
    }


def save_study_preferences(student_id, data):
    """Saves or updates student study preferences."""
    available_days = data.get('available_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'])
    if isinstance(available_days, list):
        available_days_json = json.dumps(available_days)
    else:
        available_days_json = available_days

    start_time = data.get('preferred_start_time', '18:00')
    end_time = data.get('preferred_end_time', '22:00')
    max_daily = int(data.get('max_daily_duration_minutes', 240))
    session_dur = int(data.get('session_duration_minutes', 45))
    break_dur = int(data.get('break_duration_minutes', 15))
    reminder = int(data.get('reminder_minutes_before', 15))

    # Validate
    if session_dur < 15:
        session_dur = 15
    if session_dur > 120:
        session_dur = 120
    if break_dur < 5:
        break_dur = 5
    if break_dur > 60:
        break_dur = 60
    if max_daily < 30:
        max_daily = 30
    if max_daily > 480:
        max_daily = 480
    if reminder < 5:
        reminder = 5
    if reminder > 60:
        reminder = 60

    conn = get_db_connection()
    existing = conn.execute(
        "SELECT id FROM study_preferences WHERE student_id = ?", (student_id,)
    ).fetchone()

    if existing:
        conn.execute('''
            UPDATE study_preferences SET
                available_days = ?, preferred_start_time = ?, preferred_end_time = ?,
                max_daily_duration_minutes = ?, session_duration_minutes = ?,
                break_duration_minutes = ?, reminder_minutes_before = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE student_id = ?
        ''', (available_days_json, start_time, end_time, max_daily, session_dur, break_dur, reminder, student_id))
    else:
        conn.execute('''
            INSERT INTO study_preferences (
                student_id, available_days, preferred_start_time, preferred_end_time,
                max_daily_duration_minutes, session_duration_minutes, break_duration_minutes,
                reminder_minutes_before
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (student_id, available_days_json, start_time, end_time, max_daily, session_dur, break_dur, reminder))

    conn.commit()
    conn.close()


def generate_study_timetable(student_id):
    """
    Generates a personalized weekly study timetable based on:
    - Weak subjects analysis
    - Student study preferences
    - Priority-based session allocation

    Returns the list of generated schedule entries.
    """
    # Step 1: Get weak subjects analysis
    analysis = analyze_weak_subjects(student_id)
    subjects = analysis.get('subjects', [])

    if not subjects:
        return {
            'sessions': [],
            'message': 'No examination data available to generate a study timetable. Please ensure at least one examination record exists.'
        }

    # Step 2: Get student preferences
    prefs = get_study_preferences(student_id)
    available_days = prefs['available_days']
    start_time_str = prefs['preferred_start_time']
    end_time_str = prefs['preferred_end_time']
    max_daily_minutes = prefs['max_daily_duration_minutes']
    session_minutes = prefs['session_duration_minutes']
    break_minutes = prefs['break_duration_minutes']

    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = datetime.strptime(end_time_str, '%H:%M').time()

    # Step 3: Clear existing future scheduled sessions (not completed/cancelled)
    today = date.today()
    conn = get_db_connection()
    conn.execute('''
        DELETE FROM study_schedule
        WHERE student_id = ? AND scheduled_date >= ? AND status IN ('Scheduled', 'Missed')
    ''', (student_id, today.isoformat()))
    conn.commit()
    conn.close()

    # Step 4: Calculate session allocation per priority
    priority_weights = {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}
    total_weight = sum(priority_weights.get(s['priority'], 1) for s in subjects)

    # Determine sessions per subject for the week
    # Calculate max sessions per day
    effective_session_block = session_minutes + break_minutes
    start_dt = datetime.combine(today, start_time)
    end_dt = datetime.combine(today, end_time)
    available_minutes_window = (end_dt - start_dt).seconds // 60

    # Cap by both window and max_daily
    usable_daily_minutes = min(available_minutes_window, max_daily_minutes)
    max_sessions_per_day = max(1, usable_daily_minutes // effective_session_block)

    total_weekly_slots = max_sessions_per_day * len(available_days)

    # Allocate sessions proportionally
    subject_sessions = []
    for s in subjects:
        weight = priority_weights.get(s['priority'], 1)
        allocated = max(1, round((weight / total_weight) * total_weekly_slots))
        # Determine appropriate activities
        if s['priority'] in ('Critical', 'High'):
            activities = [
                STUDY_ACTIVITIES[s['key']]['concept'],
                STUDY_ACTIVITIES[s['key']]['practice'],
                STUDY_ACTIVITIES[s['key']]['revision'],
            ]
        elif s['priority'] == 'Medium':
            activities = [
                STUDY_ACTIVITIES[s['key']]['revision'],
                STUDY_ACTIVITIES[s['key']]['practice'],
            ]
        else:
            activities = [
                STUDY_ACTIVITIES[s['key']]['maintain'],
            ]
        subject_sessions.append({
            'subject': s,
            'sessions_needed': allocated,
            'activities': activities
        })

    # Step 5: Build the weekly schedule
    # Generate dates for the next 7 days matching available days
    day_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    available_day_nums = [day_map[d] for d in available_days if d in day_map]

    schedule_dates = []
    for offset in range(14):  # Look ahead 14 days to fill a week
        d = today + timedelta(days=offset)
        if d.weekday() in available_day_nums:
            schedule_dates.append(d)
        if len(schedule_dates) >= len(available_days):
            break

    if not schedule_dates:
        return {
            'sessions': [],
            'message': 'No available study days configured. Please update your study preferences.'
        }

    # Step 6: Distribute sessions across days avoiding same-subject clustering
    # Round-robin across subjects, distributing evenly
    schedule_entries = []
    day_slots_used = {d: 0 for d in schedule_dates}
    day_time_cursor = {d: datetime.combine(d, start_time) for d in schedule_dates}

    # Build a flat list of sessions to schedule
    all_sessions_to_schedule = []
    for ss in subject_sessions:
        for i in range(ss['sessions_needed']):
            activity = ss['activities'][i % len(ss['activities'])]
            all_sessions_to_schedule.append({
                'subject_key': ss['subject']['key'],
                'subject_name': ss['subject']['name'],
                'priority': ss['subject']['priority'],
                'activity': activity
            })

    # Distribute using round-robin across days
    day_idx = 0
    last_subject_on_day = {d: None for d in schedule_dates}

    for session_info in all_sessions_to_schedule:
        placed = False
        attempts = 0

        while not placed and attempts < len(schedule_dates) * 2:
            target_date = schedule_dates[day_idx % len(schedule_dates)]
            cursor = day_time_cursor[target_date]
            session_end = cursor + timedelta(minutes=session_minutes)
            day_end = datetime.combine(target_date, end_time)

            # Check constraints
            slots_used = day_slots_used[target_date]
            daily_minutes_used = slots_used * effective_session_block

            if (session_end <= day_end and
                daily_minutes_used + session_minutes <= max_daily_minutes and
                last_subject_on_day[target_date] != session_info['subject_key']):

                schedule_entries.append({
                    'student_id': student_id,
                    'subject_key': session_info['subject_key'],
                    'subject_name': session_info['subject_name'],
                    'scheduled_date': target_date.isoformat(),
                    'start_time': cursor.strftime('%H:%M'),
                    'end_time': session_end.strftime('%H:%M'),
                    'study_activity': session_info['activity'],
                    'priority': session_info['priority'],
                    'status': 'Scheduled'
                })

                day_slots_used[target_date] += 1
                day_time_cursor[target_date] = session_end + timedelta(minutes=break_minutes)
                last_subject_on_day[target_date] = session_info['subject_key']
                placed = True

            day_idx += 1
            attempts += 1

        if not placed:
            # Try to fit on any day even if same subject was last
            for dd in schedule_dates:
                cursor = day_time_cursor[dd]
                session_end = cursor + timedelta(minutes=session_minutes)
                day_end = datetime.combine(dd, end_time)
                slots_used = day_slots_used[dd]
                daily_minutes_used = slots_used * effective_session_block

                if session_end <= day_end and daily_minutes_used + session_minutes <= max_daily_minutes:
                    schedule_entries.append({
                        'student_id': student_id,
                        'subject_key': session_info['subject_key'],
                        'subject_name': session_info['subject_name'],
                        'scheduled_date': dd.isoformat(),
                        'start_time': cursor.strftime('%H:%M'),
                        'end_time': session_end.strftime('%H:%M'),
                        'study_activity': session_info['activity'],
                        'priority': session_info['priority'],
                        'status': 'Scheduled'
                    })
                    day_slots_used[dd] += 1
                    day_time_cursor[dd] = session_end + timedelta(minutes=break_minutes)
                    last_subject_on_day[dd] = session_info['subject_key']
                    placed = True
                    break

        day_idx += 1

    # Step 7: Save to database
    conn = get_db_connection()
    for entry in schedule_entries:
        conn.execute('''
            INSERT INTO study_schedule (
                student_id, subject_key, subject_name, scheduled_date,
                start_time, end_time, study_activity, priority, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entry['student_id'], entry['subject_key'], entry['subject_name'],
            entry['scheduled_date'], entry['start_time'], entry['end_time'],
            entry['study_activity'], entry['priority'], entry['status']
        ))
    conn.commit()
    conn.close()

    # Sort by date and time for display
    schedule_entries.sort(key=lambda e: (e['scheduled_date'], e['start_time']))

    return {
        'sessions': schedule_entries,
        'total_sessions': len(schedule_entries),
        'message': None
    }


# ==============================================================================
# MODULE 3 & 5: Schedule Retrieval and Session Tracking
# ==============================================================================

def get_student_schedule(student_id, view='week', target_date=None):
    """
    Retrieves the student's study schedule.
    view: 'week', 'day', or 'all'
    target_date: ISO date string for day view
    """
    today = date.today()
    conn = get_db_connection()

    if view == 'day':
        if target_date:
            day_str = target_date
        else:
            day_str = today.isoformat()
        rows = conn.execute('''
            SELECT * FROM study_schedule
            WHERE student_id = ? AND scheduled_date = ?
            ORDER BY start_time ASC
        ''', (student_id, day_str)).fetchall()
    elif view == 'week':
        # Get the current week (Mon-Sun)
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        rows = conn.execute('''
            SELECT * FROM study_schedule
            WHERE student_id = ? AND scheduled_date BETWEEN ? AND ?
            ORDER BY scheduled_date ASC, start_time ASC
        ''', (student_id, week_start.isoformat(), week_end.isoformat())).fetchall()
    elif view == 'month':
        month_start = today.replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month - timedelta(days=1)
        rows = conn.execute('''
            SELECT * FROM study_schedule
            WHERE student_id = ? AND scheduled_date BETWEEN ? AND ?
            ORDER BY scheduled_date ASC, start_time ASC
        ''', (student_id, month_start.isoformat(), month_end.isoformat())).fetchall()
    else:
        rows = conn.execute('''
            SELECT * FROM study_schedule
            WHERE student_id = ?
            ORDER BY scheduled_date ASC, start_time ASC
        ''', (student_id,)).fetchall()

    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        try:
            dt = datetime.strptime(d['scheduled_date'], '%Y-%m-%d')
            d['day_name'] = dt.strftime('%A')
            d['formatted_date'] = dt.strftime('%b %d, %Y')
        except Exception:
            d['day_name'] = ''
            d['formatted_date'] = d.get('scheduled_date', '')
        result.append(d)

    return result


def get_today_schedule(student_id):
    """Returns today's scheduled sessions for a student."""
    return get_student_schedule(student_id, view='day')


def get_upcoming_sessions(student_id, limit=5):
    """Returns upcoming future sessions."""
    now = datetime.now()
    today = now.date().isoformat()
    current_time = now.strftime('%H:%M')

    conn = get_db_connection()
    rows = conn.execute('''
        SELECT * FROM study_schedule
        WHERE student_id = ? AND status = 'Scheduled'
              AND (scheduled_date > ? OR (scheduled_date = ? AND start_time > ?))
        ORDER BY scheduled_date ASC, start_time ASC
        LIMIT ?
    ''', (student_id, today, today, current_time, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_session_status(session_id, student_id, new_status):
    """
    Updates the status of a study session.
    Valid statuses: 'Scheduled', 'In Progress', 'Completed', 'Missed', 'Cancelled'
    """
    valid_statuses = ['Scheduled', 'In Progress', 'Completed', 'Missed', 'Cancelled']
    if new_status not in valid_statuses:
        return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"

    conn = get_db_connection()
    session = conn.execute(
        "SELECT * FROM study_schedule WHERE id = ? AND student_id = ?",
        (session_id, student_id)
    ).fetchone()

    if not session:
        conn.close()
        return False, "Session not found or access denied."

    completion_ts = None
    if new_status == 'Completed':
        completion_ts = datetime.now().isoformat()

    conn.execute('''
        UPDATE study_schedule SET status = ?, completion_timestamp = ?
        WHERE id = ? AND student_id = ?
    ''', (new_status, completion_ts, session_id, student_id))
    conn.commit()
    conn.close()
    return True, f"Session status updated to '{new_status}'."


def get_study_progress(student_id):
    """
    Calculates study progress metrics for a student.
    Returns completion rates, subject-wise progress, and missed sessions.
    """
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    conn = get_db_connection()

    # Weekly stats
    weekly_sessions = conn.execute('''
        SELECT status, COUNT(*) as count FROM study_schedule
        WHERE student_id = ? AND scheduled_date BETWEEN ? AND ?
        GROUP BY status
    ''', (student_id, week_start.isoformat(), week_end.isoformat())).fetchall()

    weekly_stats = {}
    total_weekly = 0
    for row in weekly_sessions:
        weekly_stats[row['status']] = row['count']
        total_weekly += row['count']

    completed_weekly = weekly_stats.get('Completed', 0)
    weekly_completion_pct = round((completed_weekly / total_weekly * 100), 1) if total_weekly > 0 else 0

    # Subject-wise progress
    subject_progress = conn.execute('''
        SELECT subject_key, subject_name,
               COUNT(*) as total_sessions,
               SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status = 'Missed' THEN 1 ELSE 0 END) as missed,
               SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN status = 'Scheduled' THEN 1 ELSE 0 END) as scheduled
        FROM study_schedule
        WHERE student_id = ?
        GROUP BY subject_key
        ORDER BY subject_name ASC
    ''', (student_id,)).fetchall()

    subject_data = []
    frequently_missed_subjects = []
    for row in subject_progress:
        total = row['total_sessions']
        completed = row['completed']
        missed = row['missed']
        pct = round((completed / total * 100), 1) if total > 0 else 0
        subject_data.append({
            'subject_key': row['subject_key'],
            'subject_name': row['subject_name'],
            'total_sessions': total,
            'completed': completed,
            'missed': missed,
            'in_progress': row['in_progress'],
            'scheduled': row['scheduled'],
            'completion_pct': pct
        })
        if missed >= 3:
            frequently_missed_subjects.append({
                'subject_name': row['subject_name'],
                'missed_count': missed,
                'suggestion': f"You have missed {missed} sessions for {row['subject_name']}. Consider reviewing your study schedule and allocating a more realistic amount of time."
            })

    # Overall stats
    overall = conn.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'Missed' THEN 1 ELSE 0 END) as missed,
            SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
            SUM(CASE WHEN status = 'Scheduled' THEN 1 ELSE 0 END) as scheduled,
            SUM(CASE WHEN status = 'Cancelled' THEN 1 ELSE 0 END) as cancelled
        FROM study_schedule WHERE student_id = ?
    ''', (student_id,)).fetchone()

    conn.close()

    total_all = overall['total'] or 0
    overall_completion_pct = round(((overall['completed'] or 0) / total_all * 100), 1) if total_all > 0 else 0

    return {
        'completion_rate': overall_completion_pct,
        'completed_sessions': overall['completed'] or 0,
        'total_sessions': total_all,
        'missed_sessions': overall['missed'] or 0,
        'today_date': today.strftime('%A, %b %d, %Y'),
        'weekly': {
            'total': total_weekly,
            'completed': completed_weekly,
            'missed': weekly_stats.get('Missed', 0),
            'in_progress': weekly_stats.get('In Progress', 0),
            'scheduled': weekly_stats.get('Scheduled', 0),
            'completion_pct': weekly_completion_pct
        },
        'overall': {
            'total': total_all,
            'completed': overall['completed'] or 0,
            'missed': overall['missed'] or 0,
            'in_progress': overall['in_progress'] or 0,
            'scheduled': overall['scheduled'] or 0,
            'cancelled': overall['cancelled'] or 0,
            'completion_pct': overall_completion_pct
        },
        'subject_progress': subject_data,
        'frequently_missed': frequently_missed_subjects
    }


# ==============================================================================
# MODULE 4: Smart In-Application Reminders
# ==============================================================================

def generate_reminders(student_id=None):
    """
    Scans upcoming study sessions and generates reminder notifications.
    Called periodically by the background scheduler.
    If student_id is provided, generates only for that student.
    Otherwise, generates for all students with upcoming sessions.
    """
    now = datetime.now()
    conn = get_db_connection()

    if student_id:
        # Get the student's reminder preference
        prefs = conn.execute(
            "SELECT reminder_minutes_before FROM study_preferences WHERE student_id = ?",
            (student_id,)
        ).fetchone()
        reminder_minutes = prefs['reminder_minutes_before'] if prefs else 15

        _generate_reminders_for_student(conn, student_id, reminder_minutes, now)
    else:
        # Get all students with study schedules
        students = conn.execute('''
            SELECT DISTINCT ss.student_id,
                   COALESCE(sp.reminder_minutes_before, 15) as reminder_minutes
            FROM study_schedule ss
            LEFT JOIN study_preferences sp ON ss.student_id = sp.student_id
            WHERE ss.status = 'Scheduled'
                  AND ss.scheduled_date = ?
        ''', (now.date().isoformat(),)).fetchall()

        for s in students:
            _generate_reminders_for_student(conn, s['student_id'], s['reminder_minutes'], now)

    conn.commit()
    conn.close()


def _generate_reminders_for_student(conn, student_id, reminder_minutes, now):
    """Internal helper: generates reminders for a single student."""
    today = now.date().isoformat()
    reminder_window = now + timedelta(minutes=reminder_minutes + 2)
    reminder_window_time = reminder_window.strftime('%H:%M')

    # Find sessions starting within the reminder window
    upcoming = conn.execute('''
        SELECT * FROM study_schedule
        WHERE student_id = ? AND scheduled_date = ?
              AND status = 'Scheduled' AND start_time <= ?
              AND start_time >= ?
        ORDER BY start_time ASC
    ''', (student_id, today, reminder_window_time, now.strftime('%H:%M'))).fetchall()

    for session in upcoming:
        # Check if reminder already exists for this session
        existing = conn.execute('''
            SELECT id FROM notifications
            WHERE student_id = ? AND schedule_id = ? AND notification_type = 'reminder'
        ''', (student_id, session['id'])).fetchone()

        if existing:
            continue  # Skip duplicate

        # Calculate minutes until session
        session_start = datetime.strptime(f"{session['scheduled_date']} {session['start_time']}", '%Y-%m-%d %H:%M')
        minutes_until = max(0, int((session_start - now).total_seconds() / 60))

        if minutes_until <= reminder_minutes:
            title = "Study Session Reminder"
            if minutes_until <= 0:
                message = f"Your {session['subject_name']} study session is starting now. Today's task: {session['study_activity']}."
            else:
                message = f"Your {session['subject_name']} study session starts in {minutes_until} minute{'s' if minutes_until != 1 else ''}. Today's task: {session['study_activity']}."

            conn.execute('''
                INSERT INTO notifications (student_id, schedule_id, title, message, notification_type)
                VALUES (?, ?, ?, ?, 'reminder')
            ''', (student_id, session['id'], title, message))


def check_missed_sessions():
    """
    Marks overdue sessions as 'Missed' and generates overdue notifications.
    Called periodically by the background scheduler.
    """
    now = datetime.now()
    conn = get_db_connection()

    # Find sessions that should have ended but are still 'Scheduled'
    overdue = conn.execute('''
        SELECT ss.*, s.name as student_name FROM study_schedule ss
        JOIN students s ON ss.student_id = s.id
        WHERE ss.status = 'Scheduled'
              AND (ss.scheduled_date < ? OR (ss.scheduled_date = ? AND ss.end_time < ?))
    ''', (now.date().isoformat(), now.date().isoformat(), now.strftime('%H:%M'))).fetchall()

    for session in overdue:
        # Update status to Missed
        conn.execute(
            "UPDATE study_schedule SET status = 'Missed' WHERE id = ?",
            (session['id'],)
        )

        # Check if overdue notification already exists
        existing = conn.execute('''
            SELECT id FROM notifications
            WHERE student_id = ? AND schedule_id = ? AND notification_type = 'overdue'
        ''', (session['student_id'], session['id'])).fetchone()

        if not existing:
            conn.execute('''
                INSERT INTO notifications (student_id, schedule_id, title, message, notification_type)
                VALUES (?, ?, ?, ?, 'overdue')
            ''', (
                session['student_id'], session['id'],
                "Missed Study Session",
                f"You missed your {session['subject_name']} study session scheduled for {session['scheduled_date']} at {session['start_time']}. Consider rescheduling."
            ))

    conn.commit()
    conn.close()


def get_student_notifications(student_id, limit=20):
    """Retrieves recent notifications for a student."""
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT * FROM notifications
        WHERE student_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    ''', (student_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unread_notification_count(student_id):
    """Returns the count of unread notifications."""
    conn = get_db_connection()
    result = conn.execute(
        "SELECT COUNT(*) as count FROM notifications WHERE student_id = ? AND is_read = 0",
        (student_id,)
    ).fetchone()
    conn.close()
    return result['count'] if result else 0


def mark_notification_read(notification_id, student_id):
    """Marks a specific notification as read."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND student_id = ?",
        (notification_id, student_id)
    )
    conn.commit()
    conn.close()


def mark_all_notifications_read(student_id):
    """Marks all notifications as read for a student."""
    conn = get_db_connection()
    conn.execute(
        "UPDATE notifications SET is_read = 1 WHERE student_id = ? AND is_read = 0",
        (student_id,)
    )
    conn.commit()
    conn.close()


# ==============================================================================
# MODULE 6: Personalized Study Recommendations
# ==============================================================================

def get_study_recommendations(student_id):
    """
    Combines performance analysis with study schedule to provide
    actionable, personalized study recommendations.
    """
    analysis = analyze_weak_subjects(student_id)
    progress = get_study_progress(student_id)
    subjects = analysis.get('subjects', [])

    recommendations = []

    for subject in subjects:
        rec = {
            'subject_name': subject['name'],
            'subject_key': subject['key'],
            'icon': subject['icon'],
            'priority': subject['priority'],
            'performance': subject['performance'],
            'latest_score': subject['latest_score'],
            'reason': subject['reason'],
            'actions': []
        }

        # Find subject progress
        subj_progress = next(
            (sp for sp in progress.get('subject_progress', []) if sp['subject_key'] == subject['key']),
            None
        )

        if subject['priority'] == 'Critical':
            rec['actions'].append(f"Assign {subject['name']} as highest study priority.")
            rec['actions'].append(subject['recommended_action'])
            rec['actions'].append(f"Schedule additional {subject['name']} sessions within your availability.")
        elif subject['priority'] == 'High':
            if subject['performance'] == 'Declining':
                rec['actions'].append(f"{subject['name']} marks are declining. Increase study frequency.")
                rec['actions'].append(subject['recommended_action'])
            else:
                rec['actions'].append(f"Consistently low performance in {subject['name']}. Focus on fundamentals.")
                rec['actions'].append(subject['recommended_action'])
        elif subject['priority'] == 'Medium':
            rec['actions'].append(f"Schedule regular revision sessions for {subject['name']}.")
            rec['actions'].append(subject['recommended_action'])
        else:  # Low
            if subject['performance'] == 'Improving':
                rec['actions'].append(f"Maintain your current study routine for {subject['name']}.")
                rec['actions'].append("Avoid over-allocating time — focus excess effort on weaker subjects.")
            else:
                rec['actions'].append(f"Continue periodic revision for {subject['name']}.")

        # Add progress-based insight
        if subj_progress and subj_progress['missed'] > 0:
            rec['actions'].append(
                f"You have missed {subj_progress['missed']} study session(s) for {subject['name']}. "
                f"Regular attendance is important for improvement."
            )

        recommendations.append(rec)

    return {
        'recommendations': recommendations,
        'progress': progress,
        'available_exams': analysis.get('available_exams', 0)
    }


# ==============================================================================
# MODULE 7: Faculty Access Helpers
# ==============================================================================

def get_student_study_overview_for_faculty(student_id):
    """
    Returns a comprehensive study overview for faculty viewing.
    Includes weak subjects, timetable, progress, and missed sessions.
    """
    analysis = analyze_weak_subjects(student_id)
    schedule = get_student_schedule(student_id, view='all')
    progress = get_study_progress(student_id)

    return {
        'weak_subjects': analysis,
        'schedule': schedule,
        'progress': progress
    }


# ==============================================================================
# Background Scheduler for Reminders
# ==============================================================================

def start_reminder_scheduler(app):
    """
    Starts a background scheduler that runs every minute to:
    1. Generate reminders for upcoming sessions
    2. Mark overdue sessions as missed
    Uses APScheduler for reliable background processing.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()

        def run_reminder_tasks():
            with app.app_context():
                try:
                    generate_reminders()
                    check_missed_sessions()
                except Exception as e:
                    print(f"[!] Reminder scheduler error: {e}")

        scheduler.add_job(
            run_reminder_tasks,
            'interval',
            minutes=1,
            id='study_reminder_job',
            replace_existing=True
        )
        scheduler.start()
        print("[*] Study planner reminder scheduler started (runs every 60 seconds).")
        return scheduler
    except ImportError:
        print("[!] APScheduler not installed. Reminders will only be generated on page load.")
        print("[!] Install with: pip install APScheduler>=3.10.0")
        return None
