from app import create_app
from app.services.db import get_db_connection
from app.services.auth import hash_password

app = create_app()

with app.app_context():
    conn = get_db_connection()
    c = conn.cursor()

    # Create admin
    c.execute("INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)",
              ("admin@test.com", hash_password("password123"), "admin"))
    
    # Create recruiter
    c.execute("INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)",
              ("recruiter@test.com", hash_password("password123"), "recruiter"))
    recruiter_id = c.lastrowid if c.lastrowid else 2

    # Create candidate
    c.execute("INSERT OR IGNORE INTO users (email, password, role) VALUES (?, ?, ?)",
              ("candidate@test.com", hash_password("password123"), "candidate"))
    candidate_id = c.lastrowid if c.lastrowid else 3

    # Add profile for candidate
    c.execute("INSERT OR IGNORE INTO candidate_profiles (user_id, full_name, skills, experience_years) VALUES (?, ?, ?, ?)",
              (candidate_id, "Test Candidate", "Python, SQL, React", 5.5))

    # Add job
    c.execute("INSERT OR IGNORE INTO jobs (recruiter_id, title, company, location, description, requirements) VALUES (?, ?, ?, ?, ?, ?)",
              (recruiter_id, "Software Engineer", "Test Company", "Remote", "Looking for a great engineer.", "Python, SQL"))
    job_id = c.lastrowid if c.lastrowid else 1

    # Add application
    c.execute("INSERT OR IGNORE INTO applications (job_id, candidate_id, status) VALUES (?, ?, ?)",
              (job_id, candidate_id, "applied"))

    conn.commit()
    conn.close()
    print("Database seeded successfully with test data.")
