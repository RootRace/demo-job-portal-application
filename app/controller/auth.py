from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.services.email import send_reset_code_email
from app.services.db import get_db_connection
from app.services.auth import (
    hash_password,
    verify_password,
    get_user_by_email,
    generate_reset_code,
    reset_code_expiry,
    save_reset_code,
    verify_reset_code,
    clear_reset_code,
)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    # preserve old index behavior
    from app.controller.jobs import list_jobs

    return list_jobs()


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        role = request.form.get("role")

        if not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("auth.register"))

        conn = get_db_connection()

        existing_user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()

        if existing_user:
            conn.close()
            flash("Email already registered. Please login.", "error")
            return redirect(url_for("auth.login"))

        hashed_password = hash_password(password)

        conn.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)", (email, hashed_password, role))
        conn.commit()
        conn.close()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()

        if user and verify_password(password, user["password"]):
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            session["role"] = user["role"]
            flash("Login successful!", "success")

            if user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            elif user["role"] == "recruiter":
                return redirect(url_for("recruiter.dashboard"))
            elif user["role"] == "candidate":
                return redirect(url_for("candidate.candidate_profile"))
            else:
                return redirect(url_for("jobs.list_jobs"))
        else:
            flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("jobs.list_jobs"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        user = get_user_by_email(email)
        if user:
            code = generate_reset_code()
            expiry = reset_code_expiry()

            save_reset_code(user["id"], code, expiry)

            # send email instead of printing
            send_reset_code_email(email, code)

        flash("If the email exists, a verification code has been sent.", "success")
        return redirect(url_for("auth.verify_code", email=email))

    return render_template("forgot_password.html")


@auth_bp.route("/verify-code", methods=["GET", "POST"])
def verify_code():
    email = request.args.get("email")

    if request.method == "POST":
        code = request.form.get("code")

        user = verify_reset_code(email, code)
        if not user:
            flash("Invalid or expired code.", "error")
            return redirect(url_for("auth.verify_code", email=email))

        return redirect(url_for("auth.reset_password", user_id=user["id"]))

    return render_template("verify_code.html", email=email)


@auth_bp.route("/reset-password/<int:user_id>", methods=["GET", "POST"])
def reset_password(user_id):
    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(request.url)

        hashed_password = hash_password(password)

        conn = get_db_connection()
        conn.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_password, user_id))
        conn.commit()
        conn.close()

        clear_reset_code(user_id)

        flash("Password reset successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html")
