# Examination Performance Analysis Using Machine Learning

An end-to-end, full-stack college academic intelligence web application designed to automate student performance evaluation, visualize examination trends, generate official PDF reports, and predict academic performance tiers using **Scikit-learn Random Forest Classifier**.

---

## 1. Project Overview & Architecture

* **Frontend**: HTML5, CSS3 (Custom Academic Theme), Vanilla JavaScript, Bootstrap 5 CDN, FontAwesome 6 CDN
* **Backend**: Python Flask 3
* **Database**: SQLite 3 (`database/database.db`)
* **Machine Learning**: Python + Scikit-learn (`RandomForestClassifier`), Joblib
* **Data Visualizations**: Chart.js 4.4 (Bar, Pie, Doughnut, Line, Radar Charts)
* **Report Generation**: ReportLab (High-resolution PDF generation with academic styling)
* **Data Processing**: Pandas & NumPy

```text
Examination Data ──> SQLite DB ──> Metric Calculation ──> Statistical Analysis ──> Chart.js Visuals ──> Random Forest ML ──> ReportLab PDF
```

---

## 2. Existing System vs. Proposed System

| Dimension | Existing Traditional System | Proposed ML Examination System |
| :--- | :--- | :--- |
| **Data Analysis** | Manual calculations prone to human error | Automated metrics (total, percentage, GPA grade, pass/fail) |
| **Performance Insights** | Basic tabular score storage | Interactive multi-dimensional dashboards & cohort trends |
| **Early Intervention** | Weak students identified late in academic cycle | Immediate early warning flags & failure risk indicators |
| **Course Analysis** | Difficult to compare course-wise health | Automated course dispersion (Min / Avg / Max / Pass Rate) |
| **Future Prediction** | Unavailable | Random Forest classification with real confidence scores |
| **Reporting** | Paper-based or manual spreadsheets | Instant downloadable official PDF examination transcripts |

---

## 3. Project Structure

```text
examination-performance-analysis/
│
├── app.py                     # Main Flask web application & API endpoints
├── config.py                  # Global application configuration & paths
├── database.py                # SQLite database management, seeding & calculations
├── ml_model.py                # Random Forest predictor & inference engine
├── report_generator.py        # ReportLab PDF report generator
├── requirements.txt           # Python dependencies
├── README.md                  # Complete documentation & run instructions
│
├── database/
│   └── database.db            # SQLite database file (Auto-created on first run)
│
├── ml/
│   ├── train_model.py         # Standalone ML training & evaluation script
│   └── model.pkl              # Serialized Random Forest model & metadata
│
├── reports/                   # Output folder for generated PDF student reports
│
├── static/
│   ├── css/
│   │   └── style.css          # Modern academic UI stylesheet
│   └── js/
│       └── main.js            # Chart.js visualizers & live calculation handlers
│
└── templates/
    ├── base.html              # Layout shell with sidebar, topbar & flash alerts
    ├── login.html             # Dual-tab Admin / Student login portal
    ├── dashboard.html         # Faculty/Admin analytics dashboard with Chart.js
    ├── students.html          # Student directory & management table
    ├── add_student.html       # Student registration form
    ├── edit_student.html      # Student profile modification form
    ├── marks.html             # Examination marks roster
    ├── add_marks.html         # Add/edit marks with live auto-calculator preview
    ├── analytics.html         # Course statistics & 5-tier classification
    ├── predictions.html       # ML prediction portal with confidence meters
    ├── student_dashboard.html # Personalized student portal with Radar chart
    ├── profile.html           # Profile view and password change
    ├── report.html            # Report center & preview
    ├── 404.html               # 404 Not Found error page
    └── 500.html               # 500 Internal Server Error page
```

---

## 4. Key Modules & Features

### 🎓 1. Faculty / Admin Module
* **Executive Dashboard**: KPI metric cards (Total Students, Exams, Batch Average, Pass Rate, Failures, Honor Students) and 4 interactive Chart.js visualizations.
* **Student Management**: Full CRUD operations for student records, instant search, department filters, and deletion confirmation modal.
* **Marks Management**: Real-time auto-calculation of Total (out of 600), Average, Percentage, Grade (A+ to F), and Result (PASS / FAIL).
* **Performance Analytics**: Course-wise statistical breakdowns (Class Average, Highest, Lowest, Pass Rate) and 5 performance tiers.
* **ML Predictions**: Test student marks against the trained Random Forest Classifier, view confidence scores, and review historical prediction logs.
* **Official Reports Hub**: Instant document preview and PDF transcript downloads.

### 🧑‍🎓 2. Student Portal Module
* **Personalized Dashboard**: View personal academic profile, cumulative metrics, and latest examination standing.
* **Subject Performance Radar**: Interactive radar chart benchmarking student course marks against the 40-mark passing threshold.
* **Examination History**: Historical record across all terms.
* **AI Academic Guidance**: Personalized recommendations tailored to weakest subjects and predicted tier.
* **Direct Transcript Download**: One-click download of the official institutional PDF report.

---

## 5. Grading & Examination Rules

* **6 Core Courses**: Mathematics, English, Science, Computer Science, Database Management, Web Technology (100 Marks each; Total: 600 Marks).
* **Passing Requirement**: Score $\ge 40$ in **every** individual course.
* **Grading Brackets**:
  * $90\% - 100\%$: **A+**
  * $80\% - 89.99\%$: **A**
  * $70\% - 79.99\%$: **B+**
  * $60\% - 69.99\%$: **B**
  * $50\% - 59.99\%$: **C**
  * $40\% - 49.99\%$: **D**
  * Below $40\%$: **F**

---

## 6. Installation & Execution Guide (Windows)

### Step 1: Open Terminal in Project Directory
Open PowerShell or Command Prompt in the project folder:
```powershell
cd "c:\Users\Harish\OneDrive\Desktop\ANTI DMT"
```

### Step 2: Create & Activate Virtual Environment (Optional but Recommended)
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 4: Train Machine Learning Model (Optional - Auto-runs if model missing)
```powershell
python ml\train_model.py
```

### Step 5: Start the Flask Web Application
```powershell
python app.py
```

### Step 6: Open in Web Browser
Open your browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 7. Default Login Credentials

### 🛡️ Administrator Account
* **Username**: `admin`
* **Password**: `admin123`

### 🎓 Demo Student Accounts
* **Student 1 (Excellent / Honor Roll)**:
  * **Register Number**: `REG2024001`
  * **Password**: `student123`
* **Student 2 (Good Standing)**:
  * **Register Number**: `REG2024003`
  * **Password**: `student123`
* **Student 3 (Needs Improvement / At-Risk)**:
  * **Register Number**: `REG2024009`
  * **Password**: `student123`
* **Student 4 (Poor / Remedial Attention)**:
  * **Register Number**: `REG2024013`
  * **Password**: `student123`

*(Note: The login page includes convenient 1-click credential auto-fill buttons for quick demonstration and testing).*

---

## 8. Security & Best Practices Implemented
* **Password Hashing**: Werkzeug SHA-256 password hashing; no plain-text passwords stored.
* **Session Security**: Server-side Flask session authentication with role decorators.
* **SQL Injection Prevention**: Parameterized SQL queries for all database transactions.
* **Cross-Site Access Control**: Role checks ensuring students cannot access admin routes or another student's report.
* **Input Validation**: Bounds checking on marks (0 to 100) and email format validation.
