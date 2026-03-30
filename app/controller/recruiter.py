from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.db import get_db_connection, create_notification
from app.services.auth import role_required

recruiter_bp = Blueprint("recruiter", __name__, url_prefix="/recruiter")


@recruiter_bp.route("/dashboard")
@role_required("recruiter")
def dashboard():
    conn = get_db_connection()

    jobs = conn.execute(
        """
        SELECT j.*, 
               COUNT(a.id) as application_count,
               SUM(CASE WHEN a.status = 'shortlisted' THEN 1 ELSE 0 END) as shortlisted_count,
               SUM(CASE WHEN a.status = 'rejected' THEN 1 ELSE 0 END) as rejected_count
        FROM jobs j 
        LEFT JOIN applications a ON j.id = a.job_id 
        WHERE j.recruiter_id = ?
        GROUP BY j.id
        ORDER BY j.created_at DESC
    """,
        (session["user_id"],),
    ).fetchall()

    recent_applications = conn.execute(
        """
        SELECT a.*, j.title as job_title, cp.full_name as candidate_name
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN candidate_profiles cp ON a.candidate_id = cp.user_id
        WHERE j.recruiter_id = ?
        ORDER BY a.applied_at DESC
        LIMIT 5
    """,
        (session["user_id"],),
    ).fetchall()

    conn.close()

    return render_template("recruiter_dashboard.html", jobs=jobs, recent_applications=recent_applications)


@recruiter_bp.route("/post-job", methods=["GET", "POST"])
@role_required("recruiter")
def post_job():
    if request.method == "POST":
        title = request.form["title"]
        company = request.form["company"]
        location = request.form["location"]
        description = request.form["description"]
        requirements = request.form["requirements"]
        salary_range = request.form["salary_range"]
        job_type = request.form["job_type"]

        conn = get_db_connection()
        conn.execute(
            """
            INSERT INTO jobs (recruiter_id, title, company, location, description, requirements, salary_range, job_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (session["user_id"], title, company, location, description, requirements, salary_range, job_type),
        )
        conn.commit()
        conn.close()

        flash("Job posted successfully!", "success")
        return redirect(url_for("recruiter.dashboard"))

    return render_template("post_job.html")


@recruiter_bp.route("/applications/<int:job_id>")
@role_required("recruiter")
def view_applications(job_id):
    conn = get_db_connection()

    job = conn.execute(
        "SELECT id, title FROM jobs WHERE id = ? AND recruiter_id = ?", (job_id, session["user_id"])
    ).fetchone()
    if not job:
        flash("Job not found.", "error")
        conn.close()
        return redirect(url_for("recruiter.dashboard"))

    applications = conn.execute(
        """
        SELECT a.*, cp.full_name, cp.skills, cp.experience_years, cp.location as candidate_location, 
               cp.verification_status, cp.verification_score, cp.verification_recommendation
        FROM applications a
        JOIN candidate_profiles cp ON a.candidate_id = cp.user_id
        WHERE a.job_id = ?
        ORDER BY a.applied_at DESC
    """,
        (job_id,),
    ).fetchall()

    conn.close()
    return render_template("applications.html", applications=applications, job=job)


@recruiter_bp.route("/update-application-status", methods=["POST"])
@role_required("recruiter")
def update_application_status():
    application_id = request.form["application_id"]
    new_status = request.form["status"]

    conn = get_db_connection()

    application = conn.execute(
        """
        SELECT a.id, a.candidate_id, j.title as job_title 
        FROM applications a 
        JOIN jobs j ON a.job_id = j.id 
        WHERE a.id = ? AND j.recruiter_id = ?
    """,
        (application_id, session["user_id"]),
    ).fetchone()

    if application:
        conn.execute("UPDATE applications SET status = ? WHERE id = ?", (new_status, application_id))
        conn.commit()
        
        # Notify the candidate
        message = f"Your application for '{application['job_title']}' has been marked as: {new_status}."
        create_notification(application["candidate_id"], message)
        
        flash("Application status updated!", "success")
    else:
        flash("Application not found.", "error")

    conn.close()
    return redirect(request.referrer)


@recruiter_bp.route("/application/<int:application_id>")
@role_required("recruiter")
def application_detail(application_id):
    conn = get_db_connection()
    application = conn.execute(
        """
        SELECT a.id as application_id, a.status, a.applied_at, 
               j.id as job_id, j.title as job_title, j.company as company,
               cp.*
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN candidate_profiles cp ON a.candidate_id = cp.user_id
        WHERE a.id = ? AND j.recruiter_id = ?
    """,
        (application_id, session["user_id"]),
    ).fetchone()

    conn.close()

    if not application:
        flash("Application profile not found.", "error")
        return redirect(url_for("recruiter.dashboard"))

    return render_template("application_detail.html", profile=application)
