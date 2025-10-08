from functools import wraps
from flask import session, redirect, url_for, flash


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