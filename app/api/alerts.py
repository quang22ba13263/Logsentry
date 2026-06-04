"""
API endpoints for alerts
"""
from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from app.api import api_bp
from app.models import Alert, DetectionResult, Feature
from app import db
from datetime import datetime, timedelta
from sqlalchemy import desc


@api_bp.route('/alerts', methods=['GET'])
@login_required
def get_alerts():
    """
    Get alerts with optional filtering

    Query params:
    - severity: Filter by severity (High/Medium/Low)
    - limit: Number of alerts to return (default 50)
    - resolved: Filter by resolved status (0/1)
    - hours: Get alerts from last N hours
    """
    try:
        severity = request.args.get('severity')
        limit = request.args.get('limit', 50, type=int)
        resolved = request.args.get('resolved', type=int)
        hours = request.args.get('hours', type=int)

        query = Alert.query

        # Apply filters
        if severity:
            query = query.filter_by(severity=severity)

        if resolved is not None:
            query = query.filter_by(is_resolved=resolved)

        if hours:
            since = datetime.now() - timedelta(hours=hours)
            query = query.filter(Alert.timestamp >= since)

        # Order by timestamp desc and limit
        alerts = query.order_by(desc(Alert.timestamp)).limit(limit).all()

        return jsonify({
            'alerts': [alert.to_dict() for alert in alerts],
            'count': len(alerts)
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting alerts: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@login_required
def resolve_alert(alert_id):
    """Mark alert as resolved"""
    try:
        alert = Alert.query.get_or_404(alert_id)

        alert.is_resolved = 1
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = current_user.id

        db.session.commit()

        return jsonify({
            'status': 'success',
            'alert': alert.to_dict()
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error resolving alert: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/dashboard/data', methods=['GET'])
@login_required
def get_dashboard_data():
    """
    Get comprehensive dashboard data

    Query params:
    - range: Time range (24h, 7d, 30d) default 24h
    """
    try:
        time_range = request.args.get('range', '24h')

        # Parse time range (use local time to match database)
        if time_range == '24h':
            since = datetime.now() - timedelta(hours=24)
        elif time_range == '7d':
            since = datetime.now() - timedelta(days=7)
        elif time_range == '30d':
            since = datetime.now() - timedelta(days=30)
        else:
            since = datetime.now() - timedelta(hours=24)

        # Get features
        features = Feature.query.filter(
            Feature.timestamp >= since
        ).order_by(Feature.timestamp).all()

        # Get detection results
        detections = DetectionResult.query.filter(
            DetectionResult.timestamp >= since
        ).order_by(DetectionResult.timestamp).all()

        # Get alerts
        alerts = Alert.query.filter(
            Alert.timestamp >= since
        ).order_by(desc(Alert.timestamp)).all()

        # Calculate summary stats
        total_alerts = len(alerts)
        high_severity = sum(1 for a in alerts if a.severity == 'High')
        medium_severity = sum(1 for a in alerts if a.severity == 'Medium')
        low_severity = sum(1 for a in alerts if a.severity == 'Low')
        unresolved = sum(1 for a in alerts if not a.is_resolved)

        return jsonify({
            'summary': {
                'total_windows': len(features),
                'total_alerts': total_alerts,
                'high_severity': high_severity,
                'medium_severity': medium_severity,
                'low_severity': low_severity,
                'unresolved_alerts': unresolved
            },
            'features': [f.to_dict() for f in features],
            'detections': [d.to_dict() for d in detections],
            'alerts': [a.to_dict() for a in alerts]
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'error': str(e)}), 500
