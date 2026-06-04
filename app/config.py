"""
Configuration for LogSentry AI Flask Application
"""
import os
from datetime import timedelta

# Get base directory
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """Base configuration"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'logsentry-ai-secret-key-change-in-production'

    # Database (absolute path for cross-platform compatibility)
    # Use absolute path and normalize for Windows
    db_path = os.path.abspath(os.path.join(basedir, '..', 'data', 'logsentry.db'))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + db_path.replace('\\', '/')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = False  # Set True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # API
    API_TITLE = 'LogSentry AI API'
    API_VERSION = '1.0'

    # Processing
    WINDOW_MINUTES = 1  # Time window for aggregation (changed from 5 to 1 minute)
    QUEUE_MAXSIZE = 10000  # Max logs in queue
    WORKER_THREADS = 2  # Number of worker threads
    WINDOW_CHECK_INTERVAL = 10  # Check for new windows every 10 seconds (changed from 60)

    # Detection thresholds (can be overridden)
    RULE_ERROR_THRESHOLD = 5
    RULE_CPU_THRESHOLD = 80
    RULE_MEM_THRESHOLD = 85

    # Alert settings
    ALERT_RETENTION_DAYS = 30

    # Real-time streaming
    SSE_RETRY_TIMEOUT = 5000  # milliseconds

    # Log shipper authentication
    API_KEYS = {
        'default': 'logsentry-api-key-change-in-production'
    }


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
