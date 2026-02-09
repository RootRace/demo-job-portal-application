from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.services.db import get_db_connection
from app.services.auth import login_required, role_required

jobs_bp = Blueprint("jobs", __name__)


@jobs_bp.route("/jobs")
@login_required
def list_jobs():
    search = request.args.get("search", "")
    location = request.args.get("location", "")

    conn = get_db_connection()

    query = """
        SELECT j.*, u.email as recruiter_email,
               EXISTS(SELECT 1 FROM applications a WHERE a.job_id = j.id AND a.candidate_id = ?) as has_applied
        FROM jobs j 
        JOIN users u ON j.recruiter_id = u.id 
        WHERE 1=1
    """
    params = [session["user_id"]]

    if search:
        query += " AND (j.title LIKE ? OR j.description LIKE ? OR j.requirements LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])

    if location:
        query += " AND j.location LIKE ?"
        params.append(f"%{location}%")

    query += " ORDER BY j.created_at DESC"

    jobs = conn.execute(query, params).fetchall()
    conn.close()

    return (
        render_template("index.html", jobs=jobs)
        if request.path == "/"
        else render_template("jobs.html", jobs=jobs, search=search, location=location)
    )


@jobs_bp.route("/job/<int:job_id>")
@login_required
def job_detail(job_id):
    conn = get_db_connection()

    job = conn.execute(
        """
        SELECT j.*, u.email as recruiter_email 
        FROM jobs j 
        JOIN users u ON j.recruiter_id = u.id 
        WHERE j.id = ?
    """,
        (job_id,),
    ).fetchone()

    if not job:
        flash("Job not found.", "error")
        return redirect(url_for("jobs.list_jobs"))

    has_applied = conn.execute(
        "SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?", (job_id, session["user_id"])
    ).fetchone()
    conn.close()

    return render_template("job_detail.html", job=job, has_applied=bool(has_applied))


@jobs_bp.route("/job/<int:job_id>/apply")
@role_required("candidate")
def apply_job(job_id):
    conn = get_db_connection()

    profile = conn.execute("SELECT id FROM candidate_profiles WHERE user_id = ?", (session["user_id"],)).fetchone()
    if not profile:
        flash("Please complete your profile before applying.", "error")
        conn.close()
        return redirect(url_for("candidate.candidate_profile"))

    existing_application = conn.execute(
        "SELECT id FROM applications WHERE job_id = ? AND candidate_id = ?", (job_id, session["user_id"])
    ).fetchone()
    if existing_application:
        flash("You have already applied for this job.", "error")
        conn.close()
        return redirect(url_for("jobs.job_detail", job_id=job_id))

    conn.execute(
        "INSERT INTO applications (job_id, candidate_id, status) VALUES (?, ?, ?)",
        (job_id, session["user_id"], "applied"),
    )
    conn.commit()
    conn.close()

    flash("Application submitted successfully!", "success")
    return redirect(url_for("jobs.job_detail", job_id=job_id))
