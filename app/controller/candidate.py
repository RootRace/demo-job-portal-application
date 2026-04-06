from flask import Blueprint, render_template, request, flash, session, redirect, url_for
from app.services.db import get_db_connection
from app.services.auth import role_required
from app.services.notifications import create_notification, get_recent_notifications

candidate_bp = Blueprint("candidate", __name__, url_prefix="/candidate")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_criteria(conn):
    """Return all vetting_criteria rows, ordered by id."""
    return conn.execute("SELECT * FROM vetting_criteria ORDER BY id ASC").fetchall()


def _compute_score(application_text: str, skills: str, experience_years, criteria: list) -> tuple:
    """
    Compute a weighted 0-100 score and a status string from active criteria.

    Scoring signals (each normalised 0.0 – 1.0):
      'Content Quality' → word count of application_text  (capped at 200 words)
      'Skills'          → comma-separated skill count      (capped at 10)
      'Experience'      → experience_years                 (capped at 10 yrs)

    Any unrecognised criterion name defaults to 0.5.
    Falls back to the original formula if no criteria exist.
    """
    if not criteria:
        word_count = len((application_text or "").split())
        raw = 40 + min(word_count, 40)
        status = "Verified" if raw > 70 else ("Pending Review" if raw > 50 else "Needs Improvement")
        return raw, status

    word_count   = len((application_text or "").split())
    skills_count = len([s for s in (skills or "").split(",") if s.strip()])
    exp_years    = float(experience_years or 0)

    signal_map = {
        "content quality": min(word_count   / 200.0, 1.0),
        "skills":          min(skills_count / 10.0,  1.0),
        "experience":      min(exp_years    / 10.0,  1.0),
    }

    total_weight = sum(row["weight"] for row in criteria)
    if total_weight == 0:
        return 0, "Needs Improvement"

    weighted_sum  = 0.0
    avg_threshold = 0.0
    for row in criteria:
        key = row["name"].lower().strip()
        signal = signal_map.get(key, 0.5)
        weighted_sum  += signal * row["weight"]
        avg_threshold += row["passing_threshold"] * row["weight"]

    score         = int(round((weighted_sum / total_weight) * 100))
    avg_threshold = avg_threshold / total_weight

    if score >= avg_threshold:
        status = "Verified"
    elif score >= avg_threshold * 0.75:
        status = "Pending Review"
    else:
        status = "Needs Improvement"

    return score, status


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@candidate_bp.route("/profile", methods=["GET", "POST"])
@role_required("candidate")
def candidate_profile():
    conn = get_db_connection()

    if request.method == "POST":
        full_name        = request.form["full_name"]
        phone            = request.form["phone"]
        location         = request.form["location"]
        skills           = request.form["skills"]
        experience_years = request.form["experience_years"]
        education        = request.form["education"]
        resume_text      = request.form["resume_text"]

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

    notifications = get_recent_notifications(session["user_id"], limit=5)

    return render_template("candidate_profile.html", profile=profile, notifications=notifications)


@candidate_bp.route("/vetting", methods=["POST"])
@role_required("candidate")
def vetting_application():
    conn = get_db_connection()

    # Check if a profile exists
    profile = conn.execute(
        "SELECT id, skills, experience_years, verification_status FROM candidate_profiles WHERE user_id = ?",
        (session["user_id"],),
    ).fetchone()

    if not profile:
        flash("Please complete your profile first before applying for vetting.", "error")
        conn.close()
        return redirect(url_for("candidate.candidate_profile"))

    # Score is calculated directly from the candidate's profile — no form needed
    criteria = _get_criteria(conn)
    score, status = _compute_score(
        "",  # application_text no longer required
        profile["skills"],
        profile["experience_years"],
        criteria,
    )

    # Build recommendation text based on status
    if status == "Verified":
        recommendation = (
            "Highly Recommended: This candidate demonstrated exceptional proficiency. "
            "Their background and qualifications significantly align with standards of excellence in this sector."
        )
    elif status == "Pending Review":
        recommendation = (
            "Recommended: This candidate possesses solid foundational skills and represents "
            "a capable choice for the role."
        )
    else:
        recommendation = (
            "Needs Review: The candidate may require additional support or verification "
            "to meet the standard requirements."
        )

    conn.execute(
        """
        INSERT INTO vetting_applications (candidate_id, application_text, score, status)
        VALUES (?, ?, ?, ?)
        """,
        (session["user_id"], "", score, status),
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

    create_notification(
        session["user_id"],
        f"Your vetting application result: {status}. Score: {score}/100."
    )

    flash(f"Vetting complete! Your score: {score}/100 — {status}.", "success")
    conn.close()
    return redirect(url_for("candidate.candidate_profile"))
