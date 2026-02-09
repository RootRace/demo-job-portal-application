from flask import Blueprint, render_template, request, flash, session
from app.services.db import get_db_connection
from app.services.auth import role_required

candidate_bp = Blueprint("candidate", __name__, url_prefix="/candidate")


@candidate_bp.route("/profile", methods=["GET", "POST"])
@role_required("candidate")
def candidate_profile():
    conn = get_db_connection()

    if request.method == "POST":
        full_name = request.form["full_name"]
        phone = request.form["phone"]
        location = request.form["location"]
        skills = request.form["skills"]
        experience_years = request.form["experience_years"]
        education = request.form["education"]
        resume_text = request.form["resume_text"]

        existing_profile = conn.execute(
            "SELECT id FROM candidate_profiles WHERE user_id = ?", (session["user_id"],)
        ).fetchone()

        if existing_profile:
            conn.execute(
                """
                UPDATE candidate_profiles 
                SET full_name=?, phone=?, location=?, skills=?, experience_years=?, education=?, resume_text=?
                WHERE user_id=?
            """,
                (full_name, phone, location, skills, experience_years, education, resume_text, session["user_id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO candidate_profiles 
                (user_id, full_name, phone, location, skills, experience_years, education, resume_text)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (session["user_id"], full_name, phone, location, skills, experience_years, education, resume_text),
            )

        conn.commit()
        flash("Profile updated successfully!", "success")

    profile = conn.execute("SELECT * FROM candidate_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    conn.close()

    return render_template("candidate_profile.html", profile=profile)
