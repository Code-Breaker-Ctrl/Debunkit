"""
Database models for Debunkit.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Analysis(db.Model):
    """Persisted fact-check result."""

    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    text_analyzed = db.Column(db.Text, nullable=False)
    verdict = db.Column(db.String(16), nullable=False)  # REAL / FAKE / UNCERTAIN
    confidence = db.Column(db.Float, nullable=False)
    summary = db.Column(db.Text, nullable=True)
    red_flags = db.Column(db.Text, nullable=True)   # JSON-encoded list
    source_analysis = db.Column(db.Text, nullable=True)
    domain = db.Column(db.String(32), nullable=True)
    mode = db.Column(db.String(16), nullable=False, default="ai")  # ai / local
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        import json  # noqa: PLC0415

        return {
            "id": self.id,
            "text_analyzed": self.text_analyzed,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "summary": self.summary,
            "red_flags": json.loads(self.red_flags) if self.red_flags else [],
            "source_analysis": self.source_analysis,
            "domain": self.domain,
            "mode": self.mode,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
