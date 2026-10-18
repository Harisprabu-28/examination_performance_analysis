import os

class Config:
    """Application configuration settings."""
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'anti-dmt-secret-key-2026-exam-ml-secure')
    
    # Institution
    INSTITUTION_NAME = 'M. Kumarasamy College of Engineering'
    
    # Directories
    DB_DIR = os.path.join(BASE_DIR, 'database')
    DB_PATH = os.path.join(DB_DIR, 'database.db')
    
    ML_DIR = os.path.join(BASE_DIR, 'ml')
    ML_MODEL_PATH = os.path.join(ML_DIR, 'model.pkl')
    
    REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
    
    # Examination Types Configuration
    EXAM_TYPES = ['CIA1', 'CIA2', 'MODEL']
    EXAM_LABELS = {
        'CIA1': 'CIA 1',
        'CIA2': 'CIA 2',
        'MODEL': 'Model Exam'
    }
    
    # Subject Configuration
    SUBJECTS = [
        'mathematics',
        'english',
        'science',
        'computer_science',
        'database_management',
        'web_technology'
    ]
    
    SUBJECT_LABELS = {
        'mathematics': 'Mathematics',
        'english': 'English',
        'science': 'Science',
        'computer_science': 'Computer Science',
        'database_management': 'Database Management System',
        'web_technology': 'Web Technologies'
    }
    
    MAX_MARK_PER_SUBJECT = 100
    PASS_MARK_PER_SUBJECT = 40
    TOTAL_MAX_MARKS = 600
    
    # ML Classes
    PERFORMANCE_CLASSES = [
        'Excellent',
        'Good',
        'Average',
        'Needs Improvement',
        'Poor'
    ]
    
    # Default Credentials
    DEFAULT_ADMIN_USERNAME = 'admin'
    DEFAULT_ADMIN_PASSWORD = 'admin123'
    DEFAULT_STUDENT_PASSWORD = 'student123'
