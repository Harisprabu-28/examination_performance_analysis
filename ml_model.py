import os
import joblib
import pandas as pd
import numpy as np
from config import Config

class PerformancePredictor:
    """
    Random Forest Performance Predictor for Student Examination Analysis.
    Loads serialized model and generates class predictions with probability confidence scores.
    """
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PerformancePredictor()
        return cls._instance

    def __init__(self):
        self.model_data = None
        self.load_model()
        
    def load_model(self):
        """Loads model from disk or triggers automatic training if missing."""
        if not os.path.exists(Config.ML_MODEL_PATH):
            from ml.train_model import train_and_save_model
            train_and_save_model()
            
        try:
            self.model_data = joblib.load(Config.ML_MODEL_PATH)
        except Exception as e:
            print(f"[!] Error loading model: {e}")
            self.model_data = None
            
    def predict(self, math, eng, sci, cs, db, web, average=None, percentage=None):
        """
        Predicts performance category and confidence score for a student's marks.
        """
        math = float(math)
        eng = float(eng)
        sci = float(sci)
        cs = float(cs)
        db = float(db)
        web = float(web)
        
        if average is None or percentage is None:
            total = math + eng + sci + cs + db + web
            average = total / 6.0
            percentage = (total / Config.TOTAL_MAX_MARKS) * 100.0
        else:
            average = float(average)
            percentage = float(percentage)
            
        feature_cols = [
            'mathematics', 'english', 'science', 
            'computer_science', 'database_management', 'web_technology', 
            'average', 'percentage'
        ]
        
        input_df = pd.DataFrame([[
            math, eng, sci, cs, db, web, average, percentage
        ]], columns=feature_cols)
        
        # If model is not loaded, reload or fallback
        if self.model_data is None:
            self.load_model()
            
        if self.model_data and 'model' in self.model_data:
            model = self.model_data['model']
            classes = self.model_data.get('classes', model.classes_.tolist())
            pred_class = model.predict(input_df)[0]
            
            # Predict probabilities
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(input_df)[0]
                class_probs = {cls_name: round(float(prob) * 100, 2) for cls_name, prob in zip(classes, probs)}
                pred_idx = list(classes).index(pred_class)
                confidence = round(float(probs[pred_idx]) * 100, 2)
            else:
                confidence = 85.0
                class_probs = {pred_class: 85.0}
                
            model_version = self.model_data.get('version', 'RandomForestClassifier_v1.0')
        else:
            # Rule-based fallback
            if percentage >= 85:
                pred_class = 'Excellent'
                confidence = 90.0
            elif percentage >= 70:
                pred_class = 'Good'
                confidence = 85.0
            elif percentage >= 55:
                pred_class = 'Average'
                confidence = 80.0
            elif percentage >= 40:
                pred_class = 'Needs Improvement'
                confidence = 75.0
            else:
                pred_class = 'Poor'
                confidence = 85.0
                
            class_probs = {pred_class: confidence}
            model_version = 'HeuristicFallback_v1.0'
            
        recommendations = self.generate_recommendations(pred_class, math, eng, sci, cs, db, web, percentage)
        
        return {
            'prediction': pred_class,
            'confidence': confidence,
            'class_probabilities': class_probs,
            'recommendations': recommendations,
            'model_version': model_version
        }
        
    def generate_recommendations(self, pred_class, math, eng, sci, cs, db, web, percentage):
        """Generates actionable personalized academic guidance based on marks and ML prediction."""
        recs = []
        subject_scores = {
            'Mathematics': math,
            'English': eng,
            'Science': sci,
            'Computer Science': cs,
            'Database Management': db,
            'Web Technology': web
        }
        
        # Check failed subjects (< 40)
        failed_subs = [sub for sub, score in subject_scores.items() if score < Config.PASS_MARK_PER_SUBJECT]
        weak_subs = [sub for sub, score in subject_scores.items() if 40 <= score < 60]
        strong_subs = [sub for sub, score in subject_scores.items() if score >= 80]
        
        if failed_subs:
            recs.append(f"URGENT: Remediate failed subjects ({', '.join(failed_subs)}). Attend mandatory tutorial sessions before re-examination.")
            
        if weak_subs:
            recs.append(f"Focus on improving foundational concepts in {', '.join(weak_subs)} to elevate overall academic standing.")
            
        if pred_class == 'Excellent':
            recs.append("Outstanding academic performance! Consider participating in hackathons, research publications, or advanced honors certifications.")
            if strong_subs:
                recs.append(f"Demonstrated domain mastery in {', '.join(strong_subs)}.")
        elif pred_class == 'Good':
            recs.append("Consistent and strong performance. Targeted revision in moderate subjects can push your standing into the Excellent bracket.")
        elif pred_class == 'Average':
            recs.append("Steady performance, but higher consistency across technical subjects is required. Regular practice and lab problem-solving recommended.")
        elif pred_class == 'Needs Improvement':
            recs.append("At-risk performance tier. Establish a structured daily revision schedule and consult faculty mentors for subject-specific doubt resolution.")
        elif pred_class == 'Poor':
            recs.append("Critical intervention required. Immediate counseling with academic advisors and structured remedial coursework is essential.")
            
        return recs

        return recs

# Helper functions
def get_ml_prediction(math, eng, sci, cs, db, web, average=None, percentage=None):
    predictor = PerformancePredictor.get_instance()
    return predictor.predict(math, eng, sci, cs, db, web, average, percentage)

def get_student_multi_exam_prediction(student_id):
    """
    Fetches available examination records for a student (CIA 1, CIA 2, Model Exam),
    combines available performance metrics, runs Random Forest inference,
    and returns predictions along with clear data availability indicators.
    """
    from database import get_student_exam_history
    history = get_student_exam_history(student_id)
    
    cia1 = history.get('CIA1')
    cia2 = history.get('CIA2')
    model = history.get('MODEL')
    
    availability = {
        'cia1': cia1 is not None,
        'cia2': cia2 is not None,
        'model': model is not None
    }
    
    active_exams = [e for e in [cia1, cia2, model] if e is not None]
    
    if not active_exams:
        # Fallback default if no exams found
        res = get_ml_prediction(70, 70, 70, 70, 70, 70, 70.0, 70.0)
        res['availability'] = availability
        res['summary_text'] = "Prediction based on: Default Baseline (No exams uploaded)"
        return res
        
    # Calculate average scores across available exams for this student
    math_avg = np.mean([e['mathematics'] for e in active_exams])
    eng_avg = np.mean([e['english'] for e in active_exams])
    sci_avg = np.mean([e['science'] for e in active_exams])
    cs_avg = np.mean([e['computer_science'] for e in active_exams])
    db_avg = np.mean([e['database_management'] for e in active_exams])
    web_avg = np.mean([e['web_technology'] for e in active_exams])
    
    overall_avg = np.mean([e['average'] for e in active_exams])
    overall_perc = np.mean([e['percentage'] for e in active_exams])
    
    result = get_ml_prediction(
        math_avg, eng_avg, sci_avg, cs_avg, db_avg, web_avg, overall_avg, overall_perc
    )
    
    used_labels = []
    if availability['cia1']: used_labels.append("✓ CIA 1")
    else: used_labels.append("✗ CIA 1: Not Available")
    
    if availability['cia2']: used_labels.append("✓ CIA 2")
    else: used_labels.append("✗ CIA 2: Not Available")
    
    if availability['model']: used_labels.append("✓ Model Exam")
    else: used_labels.append("✗ Model Exam: Not Available")
    
    result['availability'] = availability
    result['used_exams_summary'] = " | ".join(used_labels)
    result['active_exam_count'] = len(active_exams)
    return result

