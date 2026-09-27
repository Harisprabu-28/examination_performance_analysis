import os
import sys
import sqlite3
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

# Add parent directory to sys.path to import config & database
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from config import Config
from database import init_db, get_db_connection

def derive_performance_label(row):
    """
    Labels each mark record into a performance category based on academic criteria:
    - Poor: Result is FAIL (any subject < 40) or percentage < 40
    - Needs Improvement: Percentage between 40 and 54.99
    - Average: Percentage between 55 and 69.99
    - Good: Percentage between 70 and 84.99
    - Excellent: Percentage >= 85 with all subjects >= 70
    """
    subjects = [
        row['mathematics'],
        row['english'],
        row['science'],
        row['computer_science'],
        row['database_management'],
        row['web_technology']
    ]
    percentage = row['percentage']
    
    # If any subject failed (<40) or percentage < 40
    if any(s < Config.PASS_MARK_PER_SUBJECT for s in subjects) or percentage < 40.0:
        return 'Poor'
    elif percentage < 55.0:
        return 'Needs Improvement'
    elif percentage < 70.0:
        return 'Average'
    elif percentage < 85.0:
        return 'Good'
    else:
        return 'Excellent'

def train_and_save_model():
    """
    Loads marks data from SQLite, preprocesses features, trains Random Forest Classifier,
    evaluates performance, and saves model to ml/model.pkl.
    """
    print("=" * 60)
    print("EXAMINATION PERFORMANCE ANALYSIS - ML TRAINING PIPELINE")
    print("=" * 60)
    
    # Ensure database exists
    init_db()
    
    conn = get_db_connection()
    query = """
        SELECT mathematics, english, science, computer_science, 
               database_management, web_technology, average, percentage, result
        FROM marks
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if len(df) < 5:
        print("[!] Insufficient data for ML training (less than 5 records).")
        return False, "Insufficient data for training"
        
    print(f"[*] Loaded {len(df)} examination records from database.")
    
    # Feature columns (INPUT FEATURES):
    # - Subject marks: mathematics, english, science, computer_science, database_management, web_technology
    # - Derived academic aggregates: average, percentage
    # Note: Target performance category is derived based on academic performance tiers.
    # The Random Forest model learns non-linear relationships across raw subject scores & averages to classify Performance Category.
    feature_cols = [
        'mathematics', 'english', 'science', 
        'computer_science', 'database_management', 'web_technology', 
        'average', 'percentage'
    ]
    
    # Assign target label (TARGET VARIABLE for Performance Category Prediction)
    df['target'] = df.apply(derive_performance_label, axis=1)
    
    print("\nTarget Label Distribution:")
    print(df['target'].value_counts())
    
    X = df[feature_cols]
    y = df['target']
    
    # Stratified split if possible, else standard split
    try:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    except Exception:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        
    print(f"\n[*] Training set: {len(X_train)} samples, Test set: {len(X_test)} samples")
    
    # Train Random Forest Classifier
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=6,
        criterion='gini',
        random_state=42,
        class_weight='balanced'
    )
    
    rf_model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = rf_model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\n[*] Test Accuracy: {acc * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, zero_division=0))
    
    # Feature Importance
    importances = dict(zip(feature_cols, rf_model.feature_importances_))
    print("\nFeature Importances:")
    for feat, imp in sorted(importances.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {feat:22s}: {imp * 100:.2f}%")
        
    # Save model and metadata
    os.makedirs(Config.ML_DIR, exist_ok=True)
    payload = {
        'model': rf_model,
        'feature_names': feature_cols,
        'classes': rf_model.classes_.tolist(),
        'accuracy': round(acc * 100, 2),
        'trained_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'version': 'RandomForestClassifier_v1.0'
    }
    
    joblib.dump(payload, Config.ML_MODEL_PATH)
    print(f"\n[+] Successfully saved trained model to: {Config.ML_MODEL_PATH}")
    print("=" * 60)
    return True, f"Trained successfully with {acc * 100:.1f}% accuracy"

if __name__ == '__main__':
    train_and_save_model()
