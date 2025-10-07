from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import fitz            # PyMuPDF
from docx import Document
import re
from werkzeug.utils import secure_filename
import app
import spacy
from spacy.matcher import Matcher


load_dotenv()


app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-key')
app.config['DATABASE'] = 'jobs.db'

nlp = spacy.load("en_core_web_trf")

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)
PHONE_RE = re.compile(r'(\+?\d{1,3}[\s\-]?)?(?:\d[\d\-\s]{6,}\d)')

EDUCATION_KEYWORDS = ["B.Tech","M.Tech","BSc","MSc","MBA","BE","ME","PhD"]

def extract_text_from_pdf(file_path):
    text = ""
    with fitz.open(file_path) as pdf:
        for page in pdf:
            text += page.get_text("text") + "\n"
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

def normalize_whitespace(s):
    return re.sub(r'\s+', ' ', s).strip()

def find_email(text):
    m = EMAIL_RE.search(text)
    return m.group(0).strip() if m else ""

def find_phone(text):
    m = PHONE_RE.search(text)
    if not m:
        return ""
    phone = re.sub(r'[^\d\+]', '', m.group(0))
    return phone

def extract_name_location_education(text):
    doc = nlp(text)
    name, location, education = "", "", ""

    name_match = re.search(r'(?i)(?:Name|Full Name)\s*[:\-]\s*(.+)', text)
    if name_match:
        name = name_match.group(1).split("\n")[0].strip()
    else:
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                name = ent.text.strip()
                break

    loc_match = re.search(r'(?i)(?:Location|City)\s*[:\-]\s*(.+)', text)
    if loc_match:
        location = loc_match.group(1).split("\n")[0].strip()
    else:
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:
                location = ent.text.strip()
                break

    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in text.lower():
            education = kw
            break

    return name, location, education

def extract_skills(text):
    doc = nlp(text)
    matcher = Matcher(nlp.vocab)

    pattern = [{"POS": "PROPN", "OP": "+"}, {"POS": "NOUN", "OP": "*"}]
    matcher.add("SKILL_PATTERN", [pattern])

    matches = matcher(doc)
    skills_set = set()

    for match_id, start, end in matches:
        span = doc[start:end].text.strip()
        if 1 <= len(span.split()) <= 4:
            skills_set.add(span)

    common_skills = ['Python','Java','Django','Flask','React','JavaScript','SQL','C++','AWS','Docker','Kubernetes','HTML','CSS','Node','ERPNext']
    for token in doc:
        if token.text in common_skills:
            skills_set.add(token.text)

    return ", ".join(sorted(skills_set))

def extract_experience(text):
    exp_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years|yrs)\s*(?:of)?\s*(?:experience|exp)?', text, re.I)
    if exp_m:
        return exp_m.group(1)
    else:
        doc = nlp(text)
        for sent in doc.sents:
            if "experience" in sent.text.lower():
                nums = [token.text for token in sent if token.like_num]
                if nums:
                    return nums[0]
    return ""

def extract_info_from_cv(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        raw_text = extract_text_from_pdf(file_path)
    elif ext in (".doc", ".docx"):
        raw_text = extract_text_from_docx(file_path)
    else:
        return {}

    text = normalize_whitespace(raw_text)

    email = find_email(raw_text)
    phone = find_phone(raw_text)
    name, location, education = extract_name_location_education(raw_text)
    skills = extract_skills(raw_text)
    experience_years = extract_experience(raw_text)

    return {
        "full_name": name,
        "email": email,
        "phone": phone,
        "location": location,
        "skills": skills,
        "experience_years": experience_years,
        "education": education,
        "resume_text": text[:5000]
    }

def init_db():
    conn = sqlite3.connect('jobs.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Candidate profiles table
    c.execute('''
        CREATE TABLE IF NOT EXISTS candidate_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            location TEXT,
            skills TEXT,
            experience_years REAL,
            education TEXT,
            resume_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Jobs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruiter_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT NOT NULL,
            salary_range TEXT,
            job_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (recruiter_id) REFERENCES users (id)
        )
    ''')
    
    # Applications table
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            status TEXT DEFAULT 'applied',
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (job_id) REFERENCES jobs (id),
            FOREIGN KEY (candidate_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def recruiter_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'recruiter':
            flash('Recruiter access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def candidate_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'candidate':
            flash('Candidate access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        if session['role'] == 'recruiter':
            return redirect(url_for('recruiter_dashboard'))
        else:
            return redirect(url_for('jobs'))
    
    conn = get_db_connection()
    recent_jobs = conn.execute('''
        SELECT j.*, u.email as recruiter_email 
        FROM jobs j 
        JOIN users u ON j.recruiter_id = u.id 
        ORDER BY j.created_at DESC 
        LIMIT 6
    ''').fetchall()
    conn.close()
    
    return render_template('index.html', jobs=recent_jobs)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        conn = get_db_connection()
        
        existing_user = conn.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        ).fetchone()
        
        if existing_user:
            flash('Email already registered. Please login.', 'error')
            conn.close()
            return redirect(url_for('login'))
        
        hashed_password = generate_password_hash(password)
        conn.execute(
            'INSERT INTO users (email, password, role) VALUES (?, ?, ?)',
            (email, hashed_password, role)
        )
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/upload-cv-extract', methods=['POST'])
@candidate_required
def upload_cv_extract():
    uploaded_file = request.files.get('resume_file')
    if not uploaded_file or uploaded_file.filename == '':
        return jsonify({'success': False, 'error': 'No file uploaded'})

    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(uploaded_file.filename)
    file_path = os.path.join(upload_folder, filename)
    uploaded_file.save(file_path)

    extracted_data = extract_info_from_cv(file_path)

    if not extracted_data:
        return jsonify({'success': False, 'error': 'Could not extract data'})

    app.logger.debug("CV extraction result: %s", extracted_data)

    return jsonify({'success': True, **extracted_data})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ?', (email,)
        ).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['email'] = user['email']
            session['role'] = user['role']
            flash('Login successful!', 'success')
            
            if user['role'] == 'recruiter':
                return redirect(url_for('recruiter_dashboard'))
            else:
                return redirect(url_for('jobs'))
        else:
            flash('Invalid email or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/candidate/profile', methods=['GET', 'POST'])
@candidate_required
def candidate_profile():
    conn = get_db_connection()
    
    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone']
        location = request.form['location']
        skills = request.form['skills']
        experience_years = request.form['experience_years']
        education = request.form['education']
        resume_text = request.form['resume_text']
        
        existing_profile = conn.execute(
            'SELECT id FROM candidate_profiles WHERE user_id = ?', 
            (session['user_id'],)
        ).fetchone()
        
        if existing_profile:
            conn.execute('''
                UPDATE candidate_profiles 
                SET full_name=?, phone=?, location=?, skills=?, experience_years=?, education=?, resume_text=?
                WHERE user_id=?
            ''', (full_name, phone, location, skills, experience_years, education, resume_text, session['user_id']))
        else:
            conn.execute('''
                INSERT INTO candidate_profiles 
                (user_id, full_name, phone, location, skills, experience_years, education, resume_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (session['user_id'], full_name, phone, location, skills, experience_years, education, resume_text))
        
        conn.commit()
        flash('Profile updated successfully!', 'success')
    
    profile = conn.execute(
        'SELECT * FROM candidate_profiles WHERE user_id = ?', 
        (session['user_id'],)
    ).fetchone()
    conn.close()
    
    return render_template('candidate_profile.html', profile=profile)

@app.route('/jobs')
@login_required
def jobs():
    search = request.args.get('search', '')
    location = request.args.get('location', '')
    
    conn = get_db_connection()
    
    query = '''
        SELECT j.*, u.email as recruiter_email,
               EXISTS(SELECT 1 FROM applications a WHERE a.job_id = j.id AND a.candidate_id = ?) as has_applied
        FROM jobs j 
        JOIN users u ON j.recruiter_id = u.id 
        WHERE 1=1
    '''
    params = [session['user_id']]
    
    if search:
        query += ' AND (j.title LIKE ? OR j.description LIKE ? OR j.requirements LIKE ?)'
        search_term = f'%{search}%'
        params.extend([search_term, search_term, search_term])
    
    if location:
        query += ' AND j.location LIKE ?'
        params.append(f'%{location}%')
    
    query += ' ORDER BY j.created_at DESC'
    
    jobs = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('jobs.html', jobs=jobs, search=search, location=location)

@app.route('/job/<int:job_id>')
@login_required
def job_detail(job_id):
    conn = get_db_connection()
    
    job = conn.execute('''
        SELECT j.*, u.email as recruiter_email 
        FROM jobs j 
        JOIN users u ON j.recruiter_id = u.id 
        WHERE j.id = ?
    ''', (job_id,)).fetchone()
    
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('jobs'))
    
    has_applied = conn.execute(
        'SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?',
        (job_id, session['user_id'])
    ).fetchone()
    
    conn.close()
    
    return render_template('job_detail.html', job=job, has_applied=bool(has_applied))

@app.route('/job/<int:job_id>/apply')
@candidate_required
def apply_job(job_id):
    conn = get_db_connection()
    
    profile = conn.execute(
        'SELECT id FROM candidate_profiles WHERE user_id = ?',
        (session['user_id'],)
    ).fetchone()
    
    if not profile:
        flash('Please complete your profile before applying.', 'error')
        conn.close()
        return redirect(url_for('candidate_profile'))
    
    existing_application = conn.execute(
        'SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?',
        (job_id, session['user_id'])
    ).fetchone()
    
    if existing_application:
        flash('You have already applied for this job.', 'error')
        conn.close()
        return redirect(url_for('job_detail', job_id=job_id))
    
    conn.execute(
        'INSERT INTO applications (job_id, candidate_id, status) VALUES (?, ?, ?)',
        (job_id, session['user_id'], 'applied')
    )
    conn.commit()
    conn.close()
    
    flash('Application submitted successfully!', 'success')
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/recruiter/dashboard')
@recruiter_required
def recruiter_dashboard():
    conn = get_db_connection()
    
    jobs = conn.execute('''
        SELECT j.*, 
               COUNT(a.id) as application_count,
               SUM(CASE WHEN a.status = 'shortlisted' THEN 1 ELSE 0 END) as shortlisted_count,
               SUM(CASE WHEN a.status = 'rejected' THEN 1 ELSE 0 END) as rejected_count
        FROM jobs j 
        LEFT JOIN applications a ON j.id = a.job_id 
        WHERE j.recruiter_id = ?
        GROUP BY j.id
        ORDER BY j.created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    recent_applications = conn.execute('''
        SELECT a.*, j.title as job_title, cp.full_name as candidate_name
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN candidate_profiles cp ON a.candidate_id = cp.user_id
        WHERE j.recruiter_id = ?
        ORDER BY a.applied_at DESC
        LIMIT 5
    ''', (session['user_id'],)).fetchall()
    
    conn.close()
    
    return render_template('recruiter_dashboard.html', jobs=jobs, recent_applications=recent_applications)

@app.route('/recruiter/post-job', methods=['GET', 'POST'])
@recruiter_required
def post_job():
    if request.method == 'POST':
        title = request.form['title']
        company = request.form['company']
        location = request.form['location']
        description = request.form['description']
        requirements = request.form['requirements']
        salary_range = request.form['salary_range']
        job_type = request.form['job_type']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO jobs (recruiter_id, title, company, location, description, requirements, salary_range, job_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, company, location, description, requirements, salary_range, job_type))
        conn.commit()
        conn.close()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('recruiter_dashboard'))
    
    return render_template('post_job.html')

@app.route('/recruiter/applications/<int:job_id>')
@recruiter_required
def view_applications(job_id):
    conn = get_db_connection()
    
    job = conn.execute(
        'SELECT id, title FROM jobs WHERE id = ? AND recruiter_id = ?',
        (job_id, session['user_id'])
    ).fetchone()
    
    if not job:
        flash('Job not found.', 'error')
        conn.close()
        return redirect(url_for('recruiter_dashboard'))
    
    applications = conn.execute('''
        SELECT a.*, cp.full_name, cp.skills, cp.experience_years, cp.location as candidate_location
        FROM applications a
        JOIN candidate_profiles cp ON a.candidate_id = cp.user_id
        WHERE a.job_id = ?
        ORDER BY a.applied_at DESC
    ''', (job_id,)).fetchall()
    
    conn.close()
    
    return render_template('applications.html', applications=applications, job=job)

@app.route('/recruiter/update-application-status', methods=['POST'])
@recruiter_required
def update_application_status():
    application_id = request.form['application_id']
    new_status = request.form['status']
    
    conn = get_db_connection()
    
    application = conn.execute('''
        SELECT a.id 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        WHERE a.id = ? AND j.recruiter_id = ?
    ''', (application_id, session['user_id'])).fetchone()
    
    if application:
        conn.execute(
            'UPDATE applications SET status = ? WHERE id = ?',
            (new_status, application_id)
        )
        conn.commit()
        flash('Application status updated!', 'success')
    else:
        flash('Application not found.', 'error')
    
    conn.close()
    
    return redirect(request.referrer)

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
