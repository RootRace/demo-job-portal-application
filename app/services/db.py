import sqlite3
from flask import current_app


def get_db_connection():
    db_path = current_app.config.get("DATABASE", "jobs.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_users_table():
    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute("ALTER TABLE users ADD COLUMN reset_code TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE users ADD COLUMN reset_code_expiry TIMESTAMP")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            reset_code TEXT,
            reset_code_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
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
            verification_status TEXT DEFAULT 'Unverified',
            verification_score INTEGER DEFAULT 0,
            verification_recommendation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    c.execute("""
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
    """)

    c.execute("""
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
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vetting_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            application_text TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'submitted',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES users (id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS vetting_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            weight INTEGER NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    # Attempt to alter existing table in case it was created previously without these columns
    try:
        c.execute("ALTER TABLE candidate_profiles ADD COLUMN verification_status TEXT DEFAULT 'Unverified'")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE candidate_profiles ADD COLUMN verification_score INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    try:
        c.execute("ALTER TABLE candidate_profiles ADD COLUMN verification_recommendation TEXT")
    except sqlite3.OperationalError:
        pass

    # Seed Default Admin User
    admin_exists = c.execute("SELECT id FROM users WHERE email = 'admin@vettorix.com'").fetchone()
    if not admin_exists:
        from app.services.auth import hash_password
        admin_pass = hash_password("admin123")
        c.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)", ("admin@vettorix.com", admin_pass, "admin"))

    # Seed Default Criteria if none exist
    criteria_count = c.execute("SELECT COUNT(*) as count FROM vetting_criteria").fetchone()["count"]
    if criteria_count == 0:
        c.execute("INSERT INTO vetting_criteria (name, weight) VALUES ('Word Count Mastery', 40)")
        c.execute("INSERT INTO vetting_criteria (name, weight) VALUES ('Keyword Fluency', 60)")

    # Seed Default Setting
    threshold_exists = c.execute("SELECT key FROM system_settings WHERE key = 'passing_threshold'").fetchone()
    if not threshold_exists:
        c.execute("INSERT INTO system_settings (key, value) VALUES ('passing_threshold', '50')")

    conn.commit()
    conn.close()
