"""
API endpoints for receiving logs
"""
from flask import request, jsonify, current_app
from app.api import api_bp
from app.api.auth import require_api_key
from app.models import LogEntry
from app import db
from datetime import datetime
import json


@api_bp.route('/logs', methods=['POST'])
@require_api_key
def receive_logs():
    """
    Receive logs from log shipper

    Request body:
    {
        "logs": [
            {
                "timestamp": "2024-10-12T10:30:00",
                "level": "ERROR",
                "message": "Database connection failed",
                "service": "api-server",
                "host": "server-01"
            }
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or 'logs' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

        logs = data['logs']
        if not isinstance(logs, list):
            return jsonify({'error': 'logs must be an array'}), 400

        saved_count = 0
        for log_data in logs:
            try:
                # Parse timestamp
                timestamp_str = log_data.get('timestamp')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.utcnow()

                # Create log entry
                log_entry = LogEntry(
                    timestamp=timestamp,
                    level=log_data.get('level', 'INFO'),
                    message=log_data.get('message', ''),
                    service=log_data.get('service'),
                    host=log_data.get('host'),
                    extra_data=json.dumps(log_data.get('extra', {}))
                )

                db.session.add(log_entry)
                saved_count += 1

            except Exception as e:
                current_app.logger.error(f"Error parsing log entry: {e}")
                continue

        # Commit all logs
        db.session.commit()

        # Add to processing queue
        from app.workers import log_queue
        log_queue.put({'type': 'logs_received', 'count': saved_count})

        return jsonify({
            'status': 'success',
            'received': len(logs),
            'saved': saved_count
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error receiving logs: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/logs', methods=['GET'])
def get_logs():
    """Get recent logs (for debugging)"""
    try:
        limit = request.args.get('limit', 100, type=int)
        level = request.args.get('level')

        query = LogEntry.query

        if level:
            query = query.filter_by(level=level.upper())

        logs = query.order_by(LogEntry.timestamp.desc()).limit(limit).all()

        return jsonify({
            'logs': [log.to_dict() for log in logs],
            'count': len(logs)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting logs: {e}")
        return jsonify({'error': str(e)}), 500
