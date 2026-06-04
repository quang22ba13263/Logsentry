"""
WSGI Entry Point for Production Deployment

Use with Gunicorn:
    gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 wsgi:app

Or with uWSGI:
    uwsgi --http :5000 --wsgi-file wsgi.py --callable app --processes 4
"""
from app import create_app
import os

# Create Flask app
app = create_app(os.getenv('FLASK_ENV', 'production'))

if __name__ == "__main__":
    # This won't be used in production, but useful for testing wsgi.py
    app.run()
