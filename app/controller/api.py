import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
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
