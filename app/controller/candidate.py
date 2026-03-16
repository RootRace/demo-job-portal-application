from flask import Blueprint, render_template, request, flash, session, redirect, url_for
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


@candidate_bp.route("/vetting", methods=["GET", "POST"])
@role_required("candidate")
def vetting_application():
    conn = get_db_connection()

    # Check if a profile exists
    profile = conn.execute(
        "SELECT id, verification_status FROM candidate_profiles WHERE user_id = ?", (session["user_id"],)
    ).fetchone()

    if not profile:
        flash("Please complete your profile first before applying for vetting.", "error")
        conn.close()
        return redirect(url_for("candidate.candidate_profile"))

    if request.method == "POST":
        application_text = request.form.get("application_text", "")

        # Simple mock verification score logic:
        # Base score 40 + word count bonus (up to 40) + random factor (simulating real review/ML score)
        word_count = len(application_text.split())
        score = 40 + min(word_count, 40)

        # Determine status and recommendation text
        if score > 70:
            status = "Verified"
            recommendation = "Highly Recommended: This candidate demonstrated exceptional proficiency. Their background and qualifications significantly align with standards of excellence in this sector."
        elif score > 50:
            status = "Pending Review"
            recommendation = "Recommended: This candidate possesses solid foundational skills and represents a capable choice for the role."
        else:
            status = "Needs Improvement"
            recommendation = "Needs Review: The candidate may require additional support or verification to meet the standard requirements."

        conn.execute(
            """
            INSERT INTO vetting_applications (candidate_id, application_text, score, status)
            VALUES (?, ?, ?, ?)
            """,
            (session["user_id"], application_text, score, status),
        )

        conn.execute(
            """
            UPDATE candidate_profiles 
            SET verification_status = ?, verification_score = ?, verification_recommendation = ?
            WHERE user_id = ?
            """,
            (status, score, recommendation, session["user_id"]),
        )

        conn.commit()
        flash("Vetting application submitted successfully!", "success")
        conn.close()
        return redirect(url_for("candidate.candidate_profile"))

    conn.close()
    return render_template("vetting_form.html")
