"""
Debunkit – Flask web application.

Endpoints
---------
GET  /                   Serve the single-page UI
POST /api/analyse        Fact-check a claim
GET  /api/history        List recent analyses
GET  /api/stats          Aggregate statistics
POST /api/clear-database Delete all stored analyses
"""

import json
import logging
import os

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from Core.database import Analysis, db

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="Template", static_folder="Static")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///debunkit.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "debunkit-dev-secret")

db.init_app(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Initialise AI engine once at startup
from Core.ai_engine import AIEngine  # noqa: E402

engine = AIEngine()

# Create DB tables on first run
with app.app_context():
    db.create_all()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyse", methods=["POST"])
@limiter.limit("30 per minute")
def analyse():
    """Fact-check a claim, optionally searching the web for live sources."""
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    if len(text) > 5000:
        return jsonify({"error": "Text too long (max 5000 characters)"}), 400

    # Optionally fetch live web sources
    sources: list[dict] = []
    if data.get("use_web_sources", True):
        try:
            from Core.web_sources import search_sources  # noqa: PLC0415

            sources = search_sources(text, max_results=5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Web source search failed: %s", exc)

    result = engine.analyse(text, sources=sources)

    # Persist the result
    try:
        record = Analysis(
            text_analyzed=text,
            verdict=result["verdict"],
            confidence=result.get("confidence", 50),
            summary=result.get("summary", ""),
            red_flags=json.dumps(result.get("red_flags", [])),
            source_analysis=result.get("source_analysis", ""),
            domain=result.get("domain", "general"),
            mode="ai" if engine._client is not None else "local",
        )
        db.session.add(record)
        db.session.commit()
        result["id"] = record.id
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save analysis: %s", exc)
        db.session.rollback()

    result["sources_used"] = len(sources)
    return jsonify(result), 200


@app.route("/api/history")
@limiter.limit("60 per minute")
def history():
    """Return the most recent analyses."""
    try:
        limit = min(int(request.args.get("limit", 20)), 100)
    except (TypeError, ValueError):
        limit = 20

    records = (
        Analysis.query.order_by(Analysis.timestamp.desc()).limit(limit).all()
    )
    return jsonify({"analyses": [r.to_dict() for r in records]}), 200


@app.route("/api/stats")
@limiter.limit("30 per minute")
def stats():
    """Return aggregate statistics."""
    total = Analysis.query.count()
    if total == 0:
        return jsonify(
            {
                "total_analyses": 0,
                "average_confidence": 0,
                "verdict_breakdown": {},
                "mode_breakdown": {},
            }
        )

    from sqlalchemy import func  # noqa: PLC0415

    avg_conf = db.session.query(func.avg(Analysis.confidence)).scalar() or 0

    verdict_rows = (
        db.session.query(Analysis.verdict, func.count(Analysis.id))
        .group_by(Analysis.verdict)
        .all()
    )
    mode_rows = (
        db.session.query(Analysis.mode, func.count(Analysis.id))
        .group_by(Analysis.mode)
        .all()
    )

    return jsonify(
        {
            "total_analyses": total,
            "average_confidence": round(avg_conf, 1),
            "verdict_breakdown": {v: c for v, c in verdict_rows},
            "mode_breakdown": {m: c for m, c in mode_rows},
        }
    )


@app.route("/api/clear-database", methods=["POST"])
@limiter.limit("5 per minute")
def clear_database():
    """Delete all stored analyses."""
    try:
        count = Analysis.query.count()
        Analysis.query.delete()
        db.session.commit()
        logger.warning("Database cleared: %d analyses deleted.", count)
        return jsonify({"status": "success", "deleted": count}), 200
    except Exception as exc:  # noqa: BLE001
        logger.error("Error clearing database: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Failed to clear database"}), 500


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
