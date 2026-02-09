from functools import wraps
from datetime import datetime, timedelta
import secrets
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from app.services.db import get_db_connection


# ---------------- AUTH HELPERS ----------------

def hash_password(password: str) -> str:
    return generate_password_hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    return check_password_hash(hashed_password, password)


# ---------------- RESET PASSWORD (OTP BASED) ----------------

def generate_reset_code():
    return str(secrets.randbelow(1000000)).zfill(6)  # 6-digit code


def reset_code_expiry(minutes=10):
    return datetime.utcnow() + timedelta(minutes=minutes)


def save_reset_code(user_id, code, expiry):
    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET reset_code = ?, reset_code_expiry = ? WHERE id = ?',
        (code, expiry, user_id)
    )
    conn.commit()
    conn.close()


def verify_reset_code(email, code):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ? AND reset_code = ?',
        (email, code)
    ).fetchone()
    conn.close()

    if not user:
        return None

    # SQLite returns expiry as STRING → convert it
    expiry = datetime.fromisoformat(user['reset_code_expiry'])

    if expiry < datetime.utcnow():
        return None

    return user

def clear_reset_code(user_id):
    conn = get_db_connection()
    conn.execute(
        'UPDATE users SET reset_code = NULL, reset_code_expiry = NULL WHERE id = ?',
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ?',
        (email,)
    ).fetchone()
    conn.close()
    return user


# ---------------- DECORATORS ----------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in first.', 'error')
                return redirect(url_for('auth.login'))
            if session.get('role') != role:
                flash(f'{role.capitalize()} access required.', 'error')
                return redirect(url_for('jobs.list_jobs'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
