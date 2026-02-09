import os
from flask import Flask
from dotenv import load_dotenv
from app.controller.auth import auth_bp
from app.controller.candidate import candidate_bp
from app.controller.recruiter import recruiter_bp
from app.controller.jobs import jobs_bp
from app.controller.api import api_bp
from app.services.db import init_db, migrate_users_table

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.secret_key = os.getenv('SECRET_KEY', 'dev-key')
    app.config['DATABASE'] = os.getenv('DATABASE', 'jobs.db')
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
    app.config['SPACY_MODEL'] = os.getenv('SPACY_MODEL', 'en_core_web_sm')

    # ✅ Initialize database automatically when the app starts
    with app.app_context():
        init_db()               # safe (CREATE IF NOT EXISTS)
        migrate_users_table()   # 🔥 REQUIRED for existing DBs

    # ✅ Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(recruiter_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(api_bp)

    # ✅ Prevent caching issues
    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    return app
