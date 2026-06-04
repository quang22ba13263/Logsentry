"""
LogSentry AI Flask Application Factory
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from pathlib import Path
import sys

# Add src to path for importing detection modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_name='development'):
    """
    Flask application factory

    Args:
        config_name: Configuration name (development/production/testing)

    Returns:
        Flask app instance
    """
    app = Flask(__name__)

    # Load config
    from app.config import config
    app.config.from_object(config[config_name])

    # Ensure data directory exists
    data_dir = Path('data')
    data_dir.mkdir(exist_ok=True)
    (data_dir / 'models').mkdir(exist_ok=True)
    (data_dir / 'processed').mkdir(exist_ok=True)
    (data_dir / 'raw').mkdir(exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Vui lòng đăng nhập để truy cập trang này.'

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from app.api import api_bp
    from app.dashboard import dashboard_bp
    from app.auth import auth_bp

    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(auth_bp, url_prefix='/auth')

    # Create database tables
    with app.app_context():
        db.create_all()

        # Create default admin user if not exists
        from app.models import User
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@logsentry.ai',
                is_admin=True
            )
            admin.set_password('admin123')  # Change in production!
            db.session.add(admin)
            db.session.commit()
            print("[OK] Created default admin user (username: admin, password: admin123)")

    # Start background worker
    from app.workers import start_worker
    start_worker(app)

    return app
