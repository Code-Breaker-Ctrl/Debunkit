from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Preferences
    email_notifications = db.Column(db.Boolean, default=True)
    theme_preference = db.Column(db.String(20), default="dark")

    analyses = db.relationship("Analysis", backref="user", lazy=True,
                               cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def total_analyses(self):
        return len(self.analyses)

    def __repr__(self):
        return f"<User {self.username}>"


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    text = db.Column(db.Text, nullable=False)
    verdict = db.Column(db.String(20))
    confidence = db.Column(db.Integer)
    reason = db.Column(db.Text)
    fact_check = db.Column(db.Text)
    red_flags = db.Column(db.Text)      # JSON list stored as string
    sources = db.Column(db.Text)        # JSON list stored as string
    mode = db.Column(db.String(30))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Analysis {self.id} {self.verdict}>"
