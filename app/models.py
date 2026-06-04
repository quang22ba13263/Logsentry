"""
Database Models for LogSentry AI
"""
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class LogEntry(db.Model):
    """Raw log entries received from servers"""
    __tablename__ = 'log_entries'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    level = db.Column(db.String(20), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    service = db.Column(db.String(100), index=True)
    host = db.Column(db.String(100), index=True)
    extra_data = db.Column(db.Text)  # JSON string for additional fields
    received_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'service': self.service,
            'host': self.host,
            'received_at': self.received_at.isoformat()
        }


class MetricEntry(db.Model):
    """System metrics received from servers"""
    __tablename__ = 'metric_entries'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    host = db.Column(db.String(100), index=True)
    cpu = db.Column(db.Float)
    memory = db.Column(db.Float)
    disk_io = db.Column(db.Float)
    network_in = db.Column(db.Float)
    network_out = db.Column(db.Float)
    received_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'host': self.host,
            'cpu': self.cpu,
            'memory': self.memory,
            'disk_io': self.disk_io,
            'network_in': self.network_in,
            'network_out': self.network_out
        }


class Feature(db.Model):
    """Extracted features from time windows"""
    __tablename__ = 'features'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, unique=True, nullable=False, index=True)
    error_count = db.Column(db.Integer, default=0)
    warn_count = db.Column(db.Integer, default=0)
    info_count = db.Column(db.Integer, default=0)
    total_logs = db.Column(db.Integer, default=0)
    error_rate = db.Column(db.Float, default=0.0)
    cpu_avg = db.Column(db.Float)
    mem_avg = db.Column(db.Float)
    disk_io_avg = db.Column(db.Float)
    network_in = db.Column(db.Float)
    network_out = db.Column(db.Float)
    is_anomaly = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'error_count': self.error_count,
            'warn_count': self.warn_count,
            'info_count': self.info_count,
            'total_logs': self.total_logs,
            'error_rate': self.error_rate,
            'cpu_avg': self.cpu_avg,
            'mem_avg': self.mem_avg,
            'disk_io_avg': self.disk_io_avg,
            'network_in': self.network_in,
            'network_out': self.network_out
        }


class DetectionResult(db.Model):
    """Detection results from all detectors"""
    __tablename__ = 'detection_results'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, unique=True, nullable=False, index=True)
    rule_anomaly = db.Column(db.Integer)
    rule_score = db.Column(db.Float)
    var_anomaly = db.Column(db.Integer)
    var_score = db.Column(db.Float)
    if_anomaly = db.Column(db.Integer)
    if_score = db.Column(db.Float)
    ae_anomaly = db.Column(db.Integer)
    ae_score = db.Column(db.Float)
    deeplog_anomaly = db.Column(db.Integer)
    deeplog_score = db.Column(db.Float)
    final_anomaly = db.Column(db.Integer, index=True)
    final_score = db.Column(db.Float)
    severity = db.Column(db.String(20), index=True)
    votes = db.Column(db.Integer)
    detector_agreement = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'timestamp': self.timestamp.isoformat(),
            'rule_anomaly': self.rule_anomaly,
            'rule_score': self.rule_score,
            'var_anomaly': self.var_anomaly,
            'var_score': self.var_score,
            'if_anomaly': self.if_anomaly,
            'if_score': self.if_score,
            'ae_anomaly': self.ae_anomaly,
            'ae_score': self.ae_score,
            'deeplog_anomaly': self.deeplog_anomaly,
            'deeplog_score': self.deeplog_score,
            'final_anomaly': self.final_anomaly,
            'final_score': self.final_score,
            'severity': self.severity,
            'votes': self.votes,
            'detector_agreement': self.detector_agreement
        }


class Alert(db.Model):
    """Alerts generated from anomalies"""
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, index=True)
    final_score = db.Column(db.Float)
    votes = db.Column(db.Integer)
    detector_agreement = db.Column(db.Text)
    error_count = db.Column(db.Integer)
    cpu_avg = db.Column(db.Float)
    mem_avg = db.Column(db.Float)
    message = db.Column(db.Text)
    is_resolved = db.Column(db.Integer, default=0, index=True)
    resolved_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationship
    resolver = db.relationship('User', backref='resolved_alerts')

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'severity': self.severity,
            'final_score': self.final_score,
            'votes': self.votes,
            'detector_agreement': self.detector_agreement,
            'error_count': self.error_count,
            'cpu_avg': self.cpu_avg,
            'mem_avg': self.mem_avg,
            'message': self.message,
            'is_resolved': self.is_resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_at': self.created_at.isoformat()
        }
