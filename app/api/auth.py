"""
API Authentication Helpers
"""
from functools import wraps
from flask import request, jsonify, current_app


def require_api_key(f):
    """Decorator to require API key for endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'API key is required'}), 401

        # Check if API key is valid
        valid_keys = current_app.config.get('API_KEYS', {}).values()
        if api_key not in valid_keys:
            return jsonify({'error': 'Invalid API key'}), 401

        return f(*args, **kwargs)

    return decorated_function
