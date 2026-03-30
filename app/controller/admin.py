import logging
from flask import Blueprint, render_template, request, flash, session, redirect, url_for
from app.services.db import get_db_connection
from app.services.auth import role_required, verify_password, hash_password

logger = logging.getLogger(__name__)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ---------------------------------------------------------------------------
# Helper: compute a weighted score for a single vetting application
# ---------------------------------------------------------------------------

def _compute_score(application_text: str, skills: str, experience_years, criteria: list) -> tuple[int, str]:
    """
    Returns (score_0_to_100, status_string).

    criteria is a list of sqlite3.Row objects from vetting_criteria.
    Scoring map (name → raw signal):
      'Content Quality' → word count of application_text  (capped at 200 words → 100 %)
      'Skills'          → count of comma-separated skills  (capped at 10 → 100 %)
      'Experience'      → experience_years                 (capped at 10 yrs → 100 %)
    """
    if not criteria:
        # Fallback to the original simple formula if no criteria configured
        word_count = len((application_text or "").split())
        raw = 40 + min(word_count, 40)
        status = "Verified" if raw > 70 else ("Pending Review" if raw > 50 else "Needs Improvement")
        return raw, status

    # Raw signal functions (each returns 0.0 – 1.0)
    word_count = len((application_text or "").split())
    skills_count = len([s for s in (skills or "").split(",") if s.strip()])
    exp_years = float(experience_years or 0)

    signal_map = {
        "content quality": min(word_count / 200.0, 1.0),
        "skills":          min(skills_count / 10.0, 1.0),
        "experience":      min(exp_years / 10.0, 1.0),
    }

    total_weight = sum(row["weight"] for row in criteria)
    if total_weight == 0:
        return 0, "Needs Improvement"

    weighted_sum = 0.0
    avg_threshold = 0.0
    for row in criteria:
        key = row["name"].lower().strip()
        signal = signal_map.get(key, 0.5)          # unknown criteria default to 50 %
        weighted_sum += signal * row["weight"]
        avg_threshold += row["passing_threshold"] * row["weight"]

    score = int(round((weighted_sum / total_weight) * 100))
    avg_threshold = avg_threshold / total_weight

    if score >= avg_threshold:
        status = "Verified"
    elif score >= avg_threshold * 0.75:
        status = "Pending Review"
    else:
        status = "Needs Improvement"

    return score, status


# ---------------------------------------------------------------------------
# Admin Login  (separate from main login, admits role=="admin" only)
# ---------------------------------------------------------------------------

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("role") == "admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and user["role"] == "admin" and verify_password(password, user["password"]):
            session["user_id"] = user["id"]
            session["email"]   = user["email"]
            session["role"]    = user["role"]
            flash("Welcome back, Admin!", "success")
            return redirect(url_for("admin.dashboard"))
        else:
            flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------

@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    conn = get_db_connection()

    criteria = conn.execute(
        "SELECT * FROM vetting_criteria ORDER BY created_at ASC"
    ).fetchall()

    total_candidates = conn.execute(
        "SELECT COUNT(*) as cnt FROM users WHERE role='candidate'"
    ).fetchone()["cnt"]

    total_vetting = conn.execute(
        "SELECT COUNT(*) as cnt FROM vetting_applications"
    ).fetchone()["cnt"]

    status_dist = conn.execute("""
        SELECT verification_status, COUNT(*) as cnt
        FROM candidate_profiles
        GROUP BY verification_status
    """).fetchall()

    conn.close()

    status_map = {row["verification_status"]: row["cnt"] for row in status_dist}

    return render_template(
        "admin_dashboard.html",
        criteria=criteria,
        total_candidates=total_candidates,
        total_vetting=total_vetting,
        status_map=status_map,
    )


# ---------------------------------------------------------------------------
# Add Criterion
# ---------------------------------------------------------------------------

@admin_bp.route("/criteria/add", methods=["GET", "POST"])
@role_required("admin")
def add_criterion():
    if request.method == "POST":
        name               = request.form.get("name", "").strip()
        weight             = request.form.get("weight", 0)
        passing_threshold  = request.form.get("passing_threshold", 60)

        if not name:
            flash("Criterion name is required.", "error")
            return redirect(url_for("admin.add_criterion"))

        try:
            weight            = int(weight)
            passing_threshold = int(passing_threshold)
        except ValueError:
            flash("Weight and passing threshold must be integers.", "error")
            return redirect(url_for("admin.add_criterion"))

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO vetting_criteria (name, weight, passing_threshold) VALUES (?, ?, ?)",
                (name, weight, passing_threshold),
            )
            conn.commit()
            flash(f"Criterion '{name}' added successfully.", "success")
        except Exception as exc:
            flash(f"Could not add criterion: {exc}", "error")
        finally:
            conn.close()

        return redirect(url_for("admin.dashboard"))

    return render_template("admin_criteria_form.html", criterion=None, action="add")


# ---------------------------------------------------------------------------
# Edit Criterion
# ---------------------------------------------------------------------------

@admin_bp.route("/criteria/<int:criterion_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_criterion(criterion_id):
    conn = get_db_connection()
    criterion = conn.execute(
        "SELECT * FROM vetting_criteria WHERE id = ?", (criterion_id,)
    ).fetchone()

    if not criterion:
        conn.close()
        flash("Criterion not found.", "error")
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        name              = request.form.get("name", "").strip()
        weight            = request.form.get("weight", 0)
        passing_threshold = request.form.get("passing_threshold", 60)

        if not name:
            flash("Criterion name is required.", "error")
            conn.close()
            return redirect(url_for("admin.edit_criterion", criterion_id=criterion_id))

        try:
            weight            = int(weight)
            passing_threshold = int(passing_threshold)
        except ValueError:
            flash("Weight and passing threshold must be integers.", "error")
            conn.close()
            return redirect(url_for("admin.edit_criterion", criterion_id=criterion_id))

        try:
            conn.execute(
                "UPDATE vetting_criteria SET name=?, weight=?, passing_threshold=? WHERE id=?",
                (name, weight, passing_threshold, criterion_id),
            )
            conn.commit()
            flash(f"Criterion '{name}' updated.", "success")
        except Exception as exc:
            flash(f"Could not update criterion: {exc}", "error")
        finally:
            conn.close()

        return redirect(url_for("admin.dashboard"))

    conn.close()
    return render_template("admin_criteria_form.html", criterion=criterion, action="edit")


# ---------------------------------------------------------------------------
# Delete Criterion
# ---------------------------------------------------------------------------

@admin_bp.route("/criteria/<int:criterion_id>/delete", methods=["POST"])
@role_required("admin")
def delete_criterion(criterion_id):
    conn = get_db_connection()
    criterion = conn.execute(
        "SELECT name FROM vetting_criteria WHERE id = ?", (criterion_id,)
    ).fetchone()

    if criterion:
        conn.execute("DELETE FROM vetting_criteria WHERE id = ?", (criterion_id,))
        conn.commit()
        flash(f"Criterion '{criterion['name']}' deleted.", "success")
    else:
        flash("Criterion not found.", "error")

    conn.close()
    return redirect(url_for("admin.dashboard"))


# ---------------------------------------------------------------------------
# Recalculate all candidate scores
# ---------------------------------------------------------------------------

@admin_bp.route("/recalculate", methods=["POST"])
@role_required("admin")
def recalculate():
    conn = get_db_connection()

    criteria = conn.execute(
        "SELECT * FROM vetting_criteria ORDER BY id ASC"
    ).fetchall()

    vetting_apps = conn.execute(
        "SELECT * FROM vetting_applications ORDER BY candidate_id, submitted_at DESC"
    ).fetchall()

    updated = 0
    skipped = 0

    # Process only the most-recent vetting application per candidate
    seen_candidates = set()
    for app in vetting_apps:
        cid = app["candidate_id"]
        if cid in seen_candidates:
            continue
        seen_candidates.add(cid)

        profile = conn.execute(
            "SELECT skills, experience_years FROM candidate_profiles WHERE user_id = ?",
            (cid,),
        ).fetchone()

        if not profile:
            logger.warning(
                "Recalculate: no candidate_profile found for user_id=%s — skipping.", cid
            )
            skipped += 1
            continue

        score, status = _compute_score(
            app["application_text"],
            profile["skills"],
            profile["experience_years"],
            criteria,
        )

        if status == "Verified":
            recommendation = (
                "Highly Recommended: This candidate demonstrated exceptional proficiency. "
                "Their background and qualifications significantly align with standards of excellence."
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
            UPDATE candidate_profiles
            SET verification_status=?, verification_score=?, verification_recommendation=?
            WHERE user_id=?
            """,
            (status, score, recommendation, cid),
        )
        conn.execute(
            "UPDATE vetting_applications SET score=?, status=? WHERE id=?",
            (score, status, app["id"]),
        )
        updated += 1

    conn.commit()
    conn.close()

    flash(
        f"Recalculation complete: {updated} candidate(s) updated, {skipped} skipped (no profile).",
        "success",
    )
    return redirect(url_for("admin.dashboard"))
