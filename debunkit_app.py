"""
Debunk.IT – Flask web application
Fact-checking platform with user authentication and profile system.
"""
import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    flash,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from config import config
from Core.database import db, User, Analysis
from Core.ai_engine import hybrid_analyze

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder="Template", static_folder="Static")
app.config.from_object(config)

# Extensions
db.init_app(app)
csrf = CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[config.RATELIMIT_DEFAULT],
    storage_uri=config.RATELIMIT_STORAGE_URI,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Password validation helper
# ---------------------------------------------------------------------------
def validate_password(password: str):
    """Return a list of validation error messages (empty = valid)."""
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least one number.")
    return errors


# ---------------------------------------------------------------------------
# Routes – Auth
# ---------------------------------------------------------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        if not re.match(r"^[A-Za-z0-9_]+$", username):
            errors.append("Username may only contain letters, numbers and underscores.")
        if not email or not re.match(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$", email):
            errors.append("Please enter a valid email address.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        errors.extend(validate_password(password))

        if not errors:
            if User.query.filter_by(username=username).first():
                errors.append("Username already taken.")
            if User.query.filter_by(email=email).first():
                errors.append("Email already registered.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("signup.html", username=username, email=email)

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash("Account created! Welcome to Debunk.IT 🎉", "success")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        # Allow login with email or username
        user = User.query.filter(
            (User.email == identifier.lower()) | (User.username == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get("next", "")
            # Guard against open-redirect: only accept simple relative paths
            # (must start with '/' and not contain '//','\\', or a scheme)
            if not next_page or not next_page.startswith("/") or next_page.startswith("//") or "\\" in next_page:
                next_page = url_for("index")
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(next_page)

        flash("Invalid credentials. Please try again.", "danger")
        return render_template("login.html", identifier=identifier)

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes – Dashboard
# ---------------------------------------------------------------------------
@app.route("/")
@login_required
def index():
    recent = (
        Analysis.query.filter_by(user_id=current_user.id)
        .order_by(Analysis.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template("index.html", recent_analyses=recent)


# ---------------------------------------------------------------------------
# Routes – Analysis API
# ---------------------------------------------------------------------------
@app.route("/analyze", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def analyze():
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "No text provided."}), 400
    if len(text) < 20:
        return jsonify({"error": "Text too short (minimum 20 characters)."}), 400

    result = hybrid_analyze(text)

    # Persist to DB
    analysis = Analysis(
        user_id=current_user.id,
        text=text,
        verdict=result.get("verdict"),
        confidence=result.get("confidence"),
        reason=result.get("reason"),
        fact_check=result.get("fact_check"),
        red_flags=json.dumps(result.get("red_flags", [])),
        sources=json.dumps(result.get("sources", [])),
        mode=result.get("mode"),
    )
    db.session.add(analysis)
    db.session.commit()

    return jsonify(result)


# ---------------------------------------------------------------------------
# Routes – Profile
# ---------------------------------------------------------------------------
@app.route("/profile")
@login_required
def profile():
    analyses = (
        Analysis.query.filter_by(user_id=current_user.id)
        .order_by(Analysis.created_at.desc())
        .all()
    )
    stats = {
        "total": len(analyses),
        "real": sum(1 for a in analyses if a.verdict == "REAL"),
        "fake": sum(1 for a in analyses if a.verdict == "FAKE"),
        "uncertain": sum(1 for a in analyses if a.verdict == "UNCERTAIN"),
    }
    return render_template("profile.html", analyses=analyses, stats=stats)


# ---------------------------------------------------------------------------
# Routes – Settings
# ---------------------------------------------------------------------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "change_password":
            current_pw = request.form.get("current_password", "")
            new_pw = request.form.get("new_password", "")
            confirm_pw = request.form.get("confirm_password", "")

            if not current_user.check_password(current_pw):
                flash("Current password is incorrect.", "danger")
            elif new_pw != confirm_pw:
                flash("New passwords do not match.", "danger")
            else:
                pw_errors = validate_password(new_pw)
                if pw_errors:
                    for err in pw_errors:
                        flash(err, "danger")
                else:
                    current_user.set_password(new_pw)
                    db.session.commit()
                    flash("Password updated successfully.", "success")

        elif action == "update_preferences":
            email_notifs = bool(request.form.get("email_notifications"))
            theme = request.form.get("theme_preference", "dark")
            if theme not in ("dark", "light"):
                theme = "dark"
            current_user.email_notifications = email_notifs
            current_user.theme_preference = theme
            db.session.commit()
            flash("Preferences saved.", "success")

        return redirect(url_for("settings"))

    return render_template("settings.html")


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(429)
def rate_limited(e):
    return jsonify({"error": "Rate limit exceeded. Please wait before trying again."}), 429


# ---------------------------------------------------------------------------
# Database init & entry point
# ---------------------------------------------------------------------------
def create_tables():
    with app.app_context():
        db.create_all()


if __name__ == "__main__":
    create_tables()
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="127.0.0.1", port=5000)
