import re
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from app.services.db import get_db_connection
from app.services.auth import role_required
from app.services.vetting import calculate_dynamic_score, determine_status_and_recommendation

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.route("/dashboard")
@role_required("admin")
def dashboard():
    conn = get_db_connection()
    criteria = conn.execute("SELECT * FROM vetting_criteria").fetchall()
    setting = conn.execute("SELECT value FROM system_settings WHERE key = 'passing_threshold'").fetchone()
    threshold = int(setting["value"]) if setting else 50
    
    # Total assigned weight to give admin a heads up
    total_weight = sum(c["weight"] for c in criteria)

    conn.close()
    return render_template("admin_dashboard.html", criteria=criteria, threshold=threshold, total_weight=total_weight)

@admin_bp.route("/criterion/add", methods=["POST"])
@role_required("admin")
def add_criterion():
    name = request.form.get("name")
    weight = request.form.get("weight", type=int)
    
    if name and weight is not None:
        conn = get_db_connection()
        conn.execute("INSERT INTO vetting_criteria (name, weight) VALUES (?, ?)", (name, weight))
        conn.commit()
        conn.close()
        flash("Criterion added successfully.", "success")
        
        # Trigger recalculation
        recalculate_all_scores()
    else:
        flash("Invalid input.", "error")
        
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/criterion/<int:id>/edit", methods=["POST"])
@role_required("admin")
def edit_criterion(id):
    name = request.form.get("name")
    weight = request.form.get("weight", type=int)
    
    conn = get_db_connection()
    conn.execute("UPDATE vetting_criteria SET name = ?, weight = ? WHERE id = ?", (name, weight, id))
    conn.commit()
    conn.close()
    
    flash("Criterion updated.", "success")
    recalculate_all_scores()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/criterion/<int:id>/delete", methods=["POST"])
@role_required("admin")
def delete_criterion(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM vetting_criteria WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    flash("Criterion removed.", "success")
    recalculate_all_scores()
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/threshold/update", methods=["POST"])
@role_required("admin")
def update_threshold():
    threshold_str = request.form.get("threshold")
    if threshold_str and threshold_str.isdigit():
        conn = get_db_connection()
        conn.execute("UPDATE system_settings SET value = ? WHERE key = 'passing_threshold'", (threshold_str,))
        
        # If no row existed, an insert is needed
        if conn.total_changes == 0:
            conn.execute("INSERT INTO system_settings (key, value) VALUES ('passing_threshold', ?)", (threshold_str,))
            
        conn.commit()
        conn.close()
        flash("Passing threshold updated.", "success")
        recalculate_all_scores()
    
    return redirect(url_for('admin.dashboard'))

def recalculate_all_scores():
    """
    Recalculates all vetting applications and updates their profiles
    based on the current dynamic rules, ensuring no system crashes.
    """
    try:
        conn = get_db_connection()
        
        # Get threshold
        setting = conn.execute("SELECT value FROM system_settings WHERE key = 'passing_threshold'").fetchone()
        threshold = int(setting["value"]) if setting else 50
        
        applications = conn.execute("SELECT id, candidate_id, application_text FROM vetting_applications").fetchall()
        
        for app in applications:
            new_score = calculate_dynamic_score(conn, app["application_text"])
            status, recommendation = determine_status_and_recommendation(new_score, threshold)
            
            # Update vetting application
            conn.execute(
                "UPDATE vetting_applications SET score = ?, status = ? WHERE id = ?",
                (new_score, status, app["id"])
            )
            
            # Update candidate profile
            conn.execute(
                "UPDATE candidate_profiles SET verification_status = ?, verification_score = ?, verification_recommendation = ? WHERE user_id = ?",
                (status, new_score, recommendation, app["candidate_id"])
            )
            
        conn.commit()
    except Exception as e:
        print(f"Error recalculating scores: {e}")
        # Soft fail: Don't raise, just let it pass gracefully to prevent crashes
    finally:
        try:
            conn.close()
        except:
            pass
