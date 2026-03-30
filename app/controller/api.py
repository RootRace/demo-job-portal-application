import os
from flask import Blueprint, request, jsonify, current_app, session
from werkzeug.utils import secure_filename
from app.services.cv_parser import extract_info_from_cv, ensure_nlp
from app.services.db import get_db_connection
from app.services.cv_parser import extract_info_from_cv, ensure_nlp

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/upload-cv-extract", methods=["POST"])
def upload_cv_extract():
    uploaded_file = request.files.get("resume_file")
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"success": False, "error": "No file uploaded"})

    upload_folder = current_app.config.get("UPLOAD_FOLDER", "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(uploaded_file.filename)
    file_path = os.path.join(upload_folder, filename)
    uploaded_file.save(file_path)

    # ensure spaCy model loaded lazily
    ensure_nlp()

    extracted_data = extract_info_from_cv(file_path)

    if not extracted_data:
        return jsonify({"success": False, "error": "Could not extract data"})

    current_app.logger.debug("CV extraction result: %s", extracted_data)

    return jsonify({"success": True, **extracted_data})

@api_bp.route("/notifications", methods=["GET"])
def get_notifications():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    notifications = conn.execute(
        "SELECT id, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
        (session["user_id"],)
    ).fetchall()
    conn.close()
    
    return jsonify({
        "success": True,
        "notifications": [dict(n) for n in notifications],
        "unread_count": sum(1 for n in notifications if not n["is_read"])
    })

@api_bp.route("/notifications/mark-read", methods=["POST"])
def mark_notifications_read():
    if "user_id" not in session:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
        
    conn = get_db_connection()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (session["user_id"],))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True})
