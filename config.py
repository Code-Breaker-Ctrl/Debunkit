# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    DEBUG = False
    TESTING = False
    
    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")

    # Session Configuration
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 604800  # 7 days in seconds

    # Password validation
    MIN_PASSWORD_LENGTH = 8
    PASSWORD_COMPLEXITY_REGEX = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'

    # Cache Freshness
    CACHE_MAX_AGE_HOURS_TEXT = 24
    CACHE_MAX_AGE_HOURS_URL = 6

    # Fact-Checking Thresholds
    OFFICIAL_ANNOUNCEMENT_BOOST = 10  
    CREDIBLE_SIGNAL_THRESHOLD = 3     
    FAKE_THRESHOLD_LOCAL = 35         
    MIN_CREDIBLE_HITS = 2             
    
    # API Configuration
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    COHERE_URL = "https://api.cohere.com/v2/chat"
    COHERE_TIMEOUT = int(os.getenv("COHERE_TIMEOUT", "30")) 
    COHERE_MODEL = "command-r-08-2024"
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.getenv("RATELIMIT_ENABLED", "True") == "True"
    RATELIMIT_DEFAULT = "20 per minute"  
                       
    # Input Validation
    MAX_TEXT_LENGTH = 10000
    MIN_TEXT_LENGTH = 4
    MAX_URL_LENGTH = 2048
    MIN_WORDS_FOR_ANALYSIS = 4
    
    # Web Scraping
    SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "10"))
    SCRAPER_MAX_CHARS = 3000
    SCRAPER_MIN_WORDS = 20
    
    # RAG Engine
    RAG_SEARCH_RESULTS = 3
    RAG_TIMEOUT = int(os.getenv("RAG_TIMEOUT", "15"))
    
    # CORS Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000").split(",")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/debunkit.log")
    LOG_MAX_BYTES = 10485760  # 10MB
    LOG_BACKUP_COUNT = 5

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///debunkit.db"  # Default to SQLite for development
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # Verify connections before using
        "pool_recycle": 3600,   # Recycle connections every hour
    }

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    # In production, ensure COHERE_API_KEY is set
    
class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    COHERE_API_KEY = "test-key"

# Select config based on environment
ENV = os.getenv("FLASK_ENV", "development").lower()
if ENV == "production":
    config = ProductionConfig()
elif ENV == "testing":
    config = TestingConfig()
else:
    config = DevelopmentConfig()