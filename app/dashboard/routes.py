"""
Dashboard Routes
"""
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.dashboard import dashboard_bp
from app.models import Alert, Feature, DetectionResult
from datetime import datetime, timedelta
from sqlalchemy import func


@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard page"""
    # Get summary stats for last 24 hours
    since = datetime.utcnow() - timedelta(hours=24)

    total_alerts = Alert.query.filter(Alert.timestamp >= since).count()
    unresolved_alerts = Alert.query.filter(
        Alert.timestamp >= since,
        Alert.is_resolved == 0
    ).count()

    high_alerts = Alert.query.filter(
        Alert.timestamp >= since,
        Alert.severity == 'High'
    ).count()

    medium_alerts = Alert.query.filter(
        Alert.timestamp >= since,
        Alert.severity == 'Medium'
    ).count()

    # Recent alerts
    recent_alerts = Alert.query.order_by(
        Alert.timestamp.desc()
    ).limit(10).all()

    return render_template('dashboard/index.html',
                         total_alerts=total_alerts,
                         unresolved_alerts=unresolved_alerts,
                         high_alerts=high_alerts,
                         medium_alerts=medium_alerts,
                         recent_alerts=recent_alerts)


@dashboard_bp.route('/alerts')
@login_required
def alerts():
    """Alerts page"""
    # Get all alerts
    all_alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(100).all()

    return render_template('dashboard/alerts.html', alerts=all_alerts)


@dashboard_bp.route('/metrics')
@login_required
def metrics():
    """Metrics page"""
    return render_template('dashboard/metrics.html')


@dashboard_bp.route('/logs')
@login_required
def logs():
    """Live logs page"""
    return render_template('dashboard/logs.html')
