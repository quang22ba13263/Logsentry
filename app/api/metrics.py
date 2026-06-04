"""
API endpoints for receiving system metrics
"""
from flask import request, jsonify, current_app
from app.api import api_bp
from app.api.auth import require_api_key
from app.models import MetricEntry
from app import db
from datetime import datetime


@api_bp.route('/metrics', methods=['POST'])
@require_api_key
def receive_metrics():
    """
    Receive system metrics from servers

    Request body:
    {
        "metrics": [
            {
                "timestamp": "2024-10-12T10:30:00",
                "host": "server-01",
                "cpu": 85.5,
                "memory": 78.2,
                "disk_io": 120,
                "network_in": 1500,
                "network_out": 800
            }
        ]
    }
    """
    try:
        data = request.get_json()

        if not data or 'metrics' not in data:
            return jsonify({'error': 'Invalid request format'}), 400

        metrics = data['metrics']
        if not isinstance(metrics, list):
            return jsonify({'error': 'metrics must be an array'}), 400

        saved_count = 0
        for metric_data in metrics:
            try:
                # Parse timestamp
                timestamp_str = metric_data.get('timestamp')
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = datetime.utcnow()

                # Create metric entry
                metric_entry = MetricEntry(
                    timestamp=timestamp,
                    host=metric_data.get('host'),
                    cpu=metric_data.get('cpu'),
                    memory=metric_data.get('memory'),
                    disk_io=metric_data.get('disk_io'),
                    network_in=metric_data.get('network_in'),
                    network_out=metric_data.get('network_out')
                )

                db.session.add(metric_entry)
                saved_count += 1

            except Exception as e:
                current_app.logger.error(f"Error parsing metric entry: {e}")
                continue

        # Commit all metrics
        db.session.commit()

        # Add to processing queue
        from app.workers import log_queue
        log_queue.put({'type': 'metrics_received', 'count': saved_count})

        return jsonify({
            'status': 'success',
            'received': len(metrics),
            'saved': saved_count
        }), 201

    except Exception as e:
        current_app.logger.error(f"Error receiving metrics: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get recent metrics"""
    try:
        limit = request.args.get('limit', 100, type=int)
        host = request.args.get('host')

        query = MetricEntry.query

        if host:
            query = query.filter_by(host=host)

        metrics = query.order_by(MetricEntry.timestamp.desc()).limit(limit).all()

        return jsonify({
            'metrics': [m.to_dict() for m in metrics],
            'count': len(metrics)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500
