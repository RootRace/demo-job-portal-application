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

    # Allowed roles: 'candidate', 'recruiter', 'admin'
    # (SQLite has no ENUM — role constraint is enforced in the application layer)
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
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Admin-managed scoring criteria table
    c.execute("""
        CREATE TABLE IF NOT EXISTS vetting_criteria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            weight INTEGER NOT NULL DEFAULT 1,
            passing_threshold INTEGER NOT NULL DEFAULT 60,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Seed default criteria — INSERT OR IGNORE keeps this idempotent across restarts
    default_criteria = [
        ("Content Quality", 40, 60),
        ("Skills",          30, 60),
        ("Experience",      30, 60),
    ]
    c.executemany(
        "INSERT OR IGNORE INTO vetting_criteria (name, weight, passing_threshold) VALUES (?, ?, ?)",
        default_criteria,
    )

    # Attempt to alter existing tables in case they were created without these columns
    for alter_sql in [
        "ALTER TABLE candidate_profiles ADD COLUMN verification_status TEXT DEFAULT 'Unverified'",
        "ALTER TABLE candidate_profiles ADD COLUMN verification_score INTEGER DEFAULT 0",
        "ALTER TABLE candidate_profiles ADD COLUMN verification_recommendation TEXT",
    ]:
        try:
            c.execute(alter_sql)
        except sqlite3.OperationalError:
            pass

    c.execute("CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_applications_candidate_id ON applications(candidate_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_recruiter_id ON jobs(recruiter_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_candidate_profiles_user_id ON candidate_profiles(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_vetting_applications_candidate_id ON vetting_applications(candidate_id)")

    conn.commit()
    conn.close()
