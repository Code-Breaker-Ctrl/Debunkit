import os

class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production-xyz123")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///debunkit.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Cohere AI
    COHERE_API_KEY = os.environ.get("COHERE_API_KEY", "YOUR_COHERE_KEY")
    COHERE_MODEL = os.environ.get("COHERE_MODEL", "command-r-plus")
    COHERE_URL = "https://api.cohere.com/v2/chat"
    COHERE_TIMEOUT = 30

    # Rate limiting
    RATELIMIT_DEFAULT = "100 per hour"
    RATELIMIT_STORAGE_URI = "memory://"

    # Session / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True

config = Config()
