from flask import Flask, request, jsonify, render_template, redirect, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta

from config import config
from Core.database import (
    db,
    init_db,
    save_analysis,
    get_analysis_history,
    get_analysis_by_id,
    search_analyses,
    get_statistics,
    Analysis
)
from Core.user_model import User
from Core.ai_engine import hybrid_analyze
from Core.rag_engine import scrape_article
from utils.validators import validate_text_input, validate_url_input, ValidationError

import logging
import os
import re
import hashlib
import secrets
import hmac
import joblib


# ===== LOGGING CONFIGURATION =====

log_dir = os.path.dirname(config.LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ===== INITIALIZE FLASK APP - ONLY ONCE =====

app = Flask(__name__, template_folder="Template", static_folder="Static")
app.config.from_object(config)


# ===== CSRF PROTECTION =====

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_SESSION_KEY = "_csrf_token"


def generate_csrf_token():
    """
    Generate one CSRF token per browser session.
    This token is stored server-side in Flask session and sent to frontend pages.
    """
    if CSRF_SESSION_KEY not in session:
        session[CSRF_SESSION_KEY] = secrets.token_urlsafe(32)
    return session[CSRF_SESSION_KEY]


@app.context_processor
def inject_csrf_token():
    """
    Makes csrf_token() available inside all Jinja templates.
    """
    return dict(csrf_token=generate_csrf_token)


@app.before_request
def csrf_protect():
    """
    Require CSRF token for every unsafe request.
    Safe methods like GET/HEAD/OPTIONS are ignored.
    """
    if request.method not in UNSAFE_METHODS:
        return

    session_token = session.get(CSRF_SESSION_KEY)

    request_token = (
        request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )

    if not session_token or not request_token or not hmac.compare_digest(session_token, request_token):
        logger.warning(
            f"CSRF blocked: method={request.method}, path={request.path}, ip={request.remote_addr}"
        )
        return jsonify({"error": "Invalid or missing CSRF token"}), 403


# ===== HELPER FUNCTIONS =====

def validate_password_strength(password):
    """
    Validate password using project config.
    Must have uppercase, lowercase, number, special character, and min length.
    """
    if not password:
        return False, "Password is required"

    if len(password) < config.MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {config.MIN_PASSWORD_LENGTH} characters long"

    if not re.match(config.PASSWORD_COMPLEXITY_REGEX, password):
        return False, (
            "Password must contain at least one uppercase letter, one lowercase letter, "
            "one number, and one special character"
        )

    return True, None


def is_cached_analysis_fresh(analysis, input_type):
    """
    Decide whether a cached analysis is fresh enough to reuse.

    News changes fast, so URL/article checks expire sooner than text/headline checks.
    Defaults:
        URL cache: 6 hours
        Text/headline cache: 24 hours
    """
    if not analysis or not analysis.timestamp:
        return False

    text_cache_hours = getattr(config, "CACHE_MAX_AGE_HOURS_TEXT", 24)
    url_cache_hours = getattr(config, "CACHE_MAX_AGE_HOURS_URL", 6)

    if input_type == "url":
        max_age = timedelta(hours=url_cache_hours)
    else:
        max_age = timedelta(hours=text_cache_hours)

    age = datetime.utcnow() - analysis.timestamp
    return age <= max_age


def mask_email_for_logs(email):
    """
    Avoid logging raw email addresses during failed login attempts.
    """
    if not email or "@" not in email:
        return "invalid-email"

    name, domain = email.split("@", 1)
    safe_name = name[:2] + "***" if len(name) >= 2 else "***"

    return f"{safe_name}@{domain}"


def hash_identifier(value):
    """
    Hash identifiers for safer security logs.
    """
    if not value:
        return "unknown"

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


# ===== INITIALIZE EXTENSIONS =====

init_db(app)

CORS(app, origins=config.CORS_ORIGINS)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[config.RATELIMIT_DEFAULT],
    storage_uri="memory://"
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."


@login_manager.user_loader
def load_user(user_id):
    """
    Load user for Flask-Login.
    Uses db.session.get() to avoid SQLAlchemy legacy Query.get warning.
    """
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ===== ML MODEL LOAD - OPTIONAL =====

MODEL_PATH = "fake_news_tfidf_logreg.joblib"
ml_model = None

try:
    ml_model = joblib.load(MODEL_PATH)
    logger.info(f"Loaded ML model: {MODEL_PATH}")
except Exception as e:
    logger.error(f"Failed to load ML model '{MODEL_PATH}': {e}")


def ml_analyze_text(text: str):
    """
    Analyze text using TF-IDF + LogisticRegression model.
    This model is only a text-style classifier. It cannot prove that a claim is true.
    """
    if ml_model is None:
        raise RuntimeError("ML model is not loaded")

    prob_real = float(ml_model.predict_proba([text])[0][1])

    if 0.40 <= prob_real <= 0.60:
        verdict = "INSUFFICIENT EVIDENCE"
        confidence = 50
    elif prob_real >= 0.60:
        verdict = "INSUFFICIENT EVIDENCE"
        confidence = int(round(prob_real * 100))
    else:
        verdict = "LOW CREDIBILITY"
        confidence = int(round((1 - prob_real) * 100))

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reason": (
            f"TF-IDF + LogisticRegression risk signal (p_real={prob_real:.4f}). "
            "This is not direct source verification."
        ),
        "fact_check": [],
        "red_flags": [],
        "sources": [],
        "mode": "ml_model"
    }


logger.info("=" * 60)
logger.info("DEBUNK.IT Core Engine initialized")
logger.info(f"Mode: {'DEBUG' if app.debug else 'PRODUCTION'}")
if app.debug:
    logger.warning("Running in DEBUG mode - disable for production!")
logger.info("=" * 60)


# ===== FRONTEND ROUTES =====

@app.route("/")
def index():
    """Serve landing/main page."""
    if current_user.is_authenticated:
        return redirect("/dashboard")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def register():
    """User registration."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")

        if not username or len(username) < 3:
            return jsonify({"error": "Username must be at least 3 characters"}), 400

        if not email or "@" not in email:
            return jsonify({"error": "Invalid email address"}), 400

        is_valid_password, password_error = validate_password_strength(password)
        if not is_valid_password:
            return jsonify({"error": password_error}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already taken"}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 400

        user = User(username=username, email=email)
        user.set_password(password)

        try:
            db.session.add(user)
            db.session.commit()
            logger.info(f"New user registered: {username}")
            return jsonify({
                "status": "success",
                "message": "Account created! Please log in."
            }), 201

        except Exception as e:
            logger.error(f"Registration error: {e}")
            db.session.rollback()
            return jsonify({"error": "Registration failed"}), 500

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    """User login."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        email = data.get("email", "").strip()
        password = data.get("password", "")

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            logger.warning(
                f"Failed login attempt from {request.remote_addr} "
                f"for {mask_email_for_logs(email)} "
                f"(id={hash_identifier(email)})"
            )
            return jsonify({"error": "Invalid email or password"}), 401

        login_user(user, remember=data.get("remember", False))
        logger.info(f"User logged in: {user.username}")

        return jsonify({
            "status": "success",
            "redirect": "/dashboard"
        }), 200

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    """User logout."""
    logger.info(f"User logged out: {current_user.username}")
    logout_user()

    return jsonify({
        "status": "success",
        "redirect": "/"
    }), 200


@app.route("/profile")
@login_required
def profile():
    """User profile page."""
    return render_template("profile.html", user=current_user)


@app.route("/settings")
@login_required
def settings():
    """User settings page."""
    return render_template("settings.html", user=current_user)


@app.route("/dashboard")
@login_required
def dashboard():
    """User dashboard."""
    return render_template("index.html")


# ===== API ROUTES =====

def analyze_limit():
    """
    Dynamic rate limit for analyze endpoint.
    """
    if not current_user.is_authenticated:
        return "10 per day"
    return config.RATELIMIT_DEFAULT


@app.route("/analyze", methods=["POST"])
@limiter.limit(analyze_limit)
def analyze():
    """Main analysis endpoint with caching, validation, and scraping."""
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        raw_input = data.get("text", "")
        input_type = data.get("type", "text")

        try:
            if input_type == "url":
                valid_input = validate_url_input(raw_input)
            else:
                valid_input = validate_text_input(raw_input)

        except ValidationError as e:
            return jsonify({"error": str(e)}), 400

        logger.info(
            f"Processing {input_type} request from {request.remote_addr} "
            f"(user: {current_user.username if current_user.is_authenticated else 'guest'})"
        )

        # Check cache only if it is fresh enough
        if current_user.is_authenticated:
            cached_result = (
                Analysis.query
                .filter_by(text_analyzed=valid_input[:5000], user_id=current_user.id)
                .order_by(Analysis.timestamp.desc())
                .first()
            )

            if cached_result and is_cached_analysis_fresh(cached_result, input_type):
                logger.info("[*] FRESH CACHE HIT! Serving recent cached result.")
                result_dict = cached_result.to_dict()
                result_dict["reason"] = (
                    (result_dict.get("reason") or "") + " (Served from recent cache)"
                )
                result_dict["cache_status"] = "fresh"
                return jsonify(result_dict), 200

            if cached_result:
                logger.info("[*] STALE CACHE FOUND. Re-fetching fresh sources.")

        # Scrape if URL
        if input_type == "url":
            scraped_text, error_msg = scrape_article(valid_input)

            if error_msg:
                return jsonify({"error": error_msg}), 400

            text_to_analyze = scraped_text[:config.SCRAPER_MAX_CHARS]
        else:
            text_to_analyze = valid_input

        # Hybrid analysis: AI first, local fallback
        result = hybrid_analyze(
            text_to_analyze,
            input_type=input_type,
            source_url=valid_input if input_type == "url" else None,
            source_text=text_to_analyze if input_type == "url" else None)

        # Save only if logged in
        if current_user.is_authenticated:
            db_result = save_analysis(
                text=valid_input,
                verdict=result.get("verdict"),
                confidence=result.get("confidence"),
                reason=result.get("reason"),
                fact_check=result.get("fact_check"),
                red_flags=result.get("red_flags"),
                sources=result.get("sources"),
                mode=result.get("mode"),
                user=current_user,
                request=request
            )

            result["analysis_id"] = db_result.id if db_result else None
        else:
            result["analysis_id"] = None

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error in /analyze: {e}")
        return jsonify({"error": "Analysis failed"}), 500


@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    """Get analysis history for current user."""
    try:
        limit = min(int(request.args.get("limit", 50)), 100)
        offset = int(request.args.get("offset", 0))

        history = get_analysis_history(
            user=current_user,
            limit=limit,
            offset=offset
        )

        return jsonify({
            "total": len(history),
            "limit": limit,
            "offset": offset,
            "analyses": history
        }), 200

    except Exception as e:
        logger.error(f"Error in /api/history: {e}")
        return jsonify({"error": "Failed to fetch history"}), 500


@app.route("/api/analysis/<int:analysis_id>", methods=["GET"])
@login_required
def api_analysis_detail(analysis_id):
    """Get specific analysis by ID."""
    try:
        analysis = get_analysis_by_id(analysis_id)

        if not analysis:
            return jsonify({"error": "Analysis not found"}), 404

        if analysis["user_id"] != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403

        return jsonify(analysis), 200

    except Exception as e:
        logger.error(f"Error in /api/analysis/{analysis_id}: {e}")
        return jsonify({"error": "Failed to fetch analysis"}), 500


@app.route("/api/search", methods=["GET"])
@login_required
@limiter.limit("20 per minute")
def api_search():
    """Search past analyses for current user."""
    try:
        query = request.args.get("q", "").strip()

        if not query or len(query) < 2:
            return jsonify({"error": "Search query must be at least 2 characters"}), 400

        limit = min(int(request.args.get("limit", 50)), 100)

        results = search_analyses(
            query,
            user=current_user,
            limit=limit
        )

        return jsonify({
            "query": query,
            "total": len(results),
            "results": results
        }), 200

    except Exception as e:
        logger.error(f"Error in /api/search: {e}")
        return jsonify({"error": "Search failed"}), 500


@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    """Get statistics for current user."""
    try:
        stats = get_statistics(user=current_user)
        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error in /api/stats: {e}")
        return jsonify({"error": "Failed to fetch statistics"}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "mode": "debug" if app.debug else "production"
    }), 200


@app.route("/api/clear-database", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def clear_database():
    """Clear all analyses for current user."""
    try:
        count = Analysis.query.filter_by(user_id=current_user.id).count()

        Analysis.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()

        logger.warning(
            f"Database cleared for user {current_user.username}: {count} analyses deleted"
        )

        return jsonify({
            "status": "success",
            "message": "Database cleared successfully",
            "deleted": count
        }), 200

    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to clear database"}), 500


@app.route("/api/user/profile", methods=["GET", "PUT"])
@login_required
def api_user_profile():
    """Get or update current user profile."""
    if request.method == "GET":
        return jsonify(current_user.to_dict()), 200

    try:
        data = request.get_json(silent=True) or {}

        if "username" in data:
            new_username = data["username"].strip()

            if len(new_username) < 3:
                return jsonify({"error": "Username must be at least 3 characters"}), 400

            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != current_user.id:
                return jsonify({"error": "Username already taken"}), 400

            current_user.username = new_username

        if "email" in data:
            new_email = data["email"].strip()

            if "@" not in new_email:
                return jsonify({"error": "Invalid email address"}), 400

            existing = User.query.filter_by(email=new_email).first()
            if existing and existing.id != current_user.id:
                return jsonify({"error": "Email already registered"}), 400

            current_user.email = new_email

        db.session.commit()
        logger.info(f"Profile updated for user: {current_user.username}")

        return jsonify({
            "status": "success",
            "message": "Profile updated successfully"
        }), 200

    except Exception as e:
        logger.error(f"Profile update error: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to update profile"}), 500


@app.route("/api/user/settings", methods=["PUT"])
@login_required
def api_user_settings():
    """Update user settings."""
    try:
        data = request.get_json(silent=True) or {}

        if "theme" in data:
            theme = data["theme"]

            if theme not in ["dark", "light", "system"]:
                return jsonify({"error": "Invalid theme value"}), 400

            current_user.theme = theme

        if "email_notifications" in data:
            current_user.email_notifications = bool(data["email_notifications"])

        if "new_password" in data and data["new_password"]:
            current_password = data.get("current_password", "")
            new_password = data.get("new_password", "")

            if not current_password:
                return jsonify({"error": "Current password is required"}), 400

            if not current_user.check_password(current_password):
                logger.warning(
                    f"Failed password change attempt for user_id={current_user.id} "
                    f"from {request.remote_addr}"
                )
                return jsonify({"error": "Current password is incorrect"}), 401

            is_valid_password, password_error = validate_password_strength(new_password)
            if not is_valid_password:
                return jsonify({"error": password_error}), 400

            if current_user.check_password(new_password):
                return jsonify({
                    "error": "New password must be different from current password"
                }), 400

            current_user.set_password(new_password)

        db.session.commit()
        logger.info(f"Settings updated for user: {current_user.username}")

        return jsonify({
            "status": "success",
            "message": "Settings saved"
        }), 200

    except Exception as e:
        logger.error(f"Settings update error: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to update settings"}), 500


@app.route("/api/user/delete", methods=["DELETE"])
@login_required
def api_delete_account():
    """Delete user account and all associated data."""
    try:
        user = current_user._get_current_object()
        username = user.username
        user_id = user.id

        Analysis.query.filter_by(user_id=user_id).delete()

        db.session.delete(user)
        db.session.commit()

        logger.warning(f"Account deleted: {username}")
        logout_user()

        return jsonify({
            "status": "success",
            "message": "Account deleted"
        }), 200

    except Exception as e:
        logger.error(f"Account deletion error: {e}")
        db.session.rollback()
        return jsonify({"error": "Failed to delete account"}), 500


# ===== ERROR HANDLERS =====

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded."""
    logger.warning(f"Rate limit exceeded from {request.remote_addr}")

    if current_user.is_authenticated:
        return jsonify({
            "error": "Rate limit exceeded. Please wait and try again."
        }), 429

    return jsonify({
        "error": "Guest limit reached. Please log in to continue."
    }), 429


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {e}")
    return jsonify({"error": "Internal server error"}), 500


# ===== MAIN =====

if __name__ == "__main__":
    logger.info("Starting Debunk.IT server...")
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=app.debug
    )