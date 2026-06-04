"""
Manually process historical log data

This script processes all unprocessed windows in the database
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app, db
from app.models import LogEntry, MetricEntry, Feature, DetectionResult, Alert
from detectors.rule_based import RuleBasedDetector
from detectors.ml_models import IsolationForestDetector
import pandas as pd
import numpy as np


def process_windows(app):
    """Process all unprocessed windows"""
    with app.app_context():
        # Get earliest log
        earliest_log = LogEntry.query.order_by(LogEntry.timestamp).first()
        if not earliest_log:
            print("[ERROR] No logs found")
            return

        # Get latest processed window
        latest_feature = Feature.query.order_by(Feature.timestamp.desc()).first()

        if latest_feature:
            start_time = latest_feature.timestamp + timedelta(minutes=1)
        else:
            # Round to 1-minute window
            start_time = round_to_window(earliest_log.timestamp)

        # Current window (use local time to match database)
        now = datetime.now()
        current_window = round_to_window(now)

        print(f"Start time: {start_time}")
        print(f"Current window: {current_window}")

        # Initialize detectors
        rule_detector = RuleBasedDetector()
        if_detector = IsolationForestDetector()
        try:
            if_detector.load_model('data/models/isolation_forest.pkl')
            print("[OK] Loaded Isolation Forest model")
        except:
            print("[WARN] IF model not found")

        # Process windows
        window_time = start_time
        processed = 0

        while window_time < current_window:
            print(f"\nProcessing window: {window_time}")
            process_single_window(window_time, rule_detector, if_detector)
            window_time += timedelta(minutes=1)
            processed += 1

        print(f"\n[SUCCESS] Processed {processed} windows")


def round_to_window(dt):
    """Round datetime to 1-minute window"""
    return dt.replace(second=0, microsecond=0)


def process_single_window(window_start, rule_detector, if_detector):
    """Process a single window"""
    window_end = window_start + timedelta(minutes=1)

    # Get logs
    logs = LogEntry.query.filter(
        LogEntry.timestamp >= window_start,
        LogEntry.timestamp < window_end
    ).all()

    # Get metrics
    metrics = MetricEntry.query.filter(
        MetricEntry.timestamp >= window_start,
        MetricEntry.timestamp < window_end
    ).all()

    print(f"  Logs: {len(logs)}, Metrics: {len(metrics)}")

    # Extract features
    error_count = sum(1 for log in logs if log.level == 'ERROR')
    warn_count = sum(1 for log in logs if log.level in ['WARN', 'WARNING'])
    info_count = sum(1 for log in logs if log.level == 'INFO')
    total_logs = len(logs)
    error_rate = error_count / total_logs if total_logs > 0 else 0.0

    cpu_avg = float(np.mean([m.cpu for m in metrics if m.cpu is not None])) if metrics else 0.0
    mem_avg = float(np.mean([m.memory for m in metrics if m.memory is not None])) if metrics else 0.0
    disk_io_avg = float(np.mean([m.disk_io for m in metrics if m.disk_io is not None])) if metrics else 0.0
    network_in = float(np.sum([m.network_in for m in metrics if m.network_in is not None])) if metrics else 0.0
    network_out = float(np.sum([m.network_out for m in metrics if m.network_out is not None])) if metrics else 0.0

    # Save feature
    feature = Feature(
        timestamp=window_start,
        error_count=error_count,
        warn_count=warn_count,
        info_count=info_count,
        total_logs=total_logs,
        error_rate=float(error_rate),
        cpu_avg=float(cpu_avg) if not np.isnan(cpu_avg) else 0.0,
        mem_avg=float(mem_avg) if not np.isnan(mem_avg) else 0.0,
        disk_io_avg=float(disk_io_avg) if not np.isnan(disk_io_avg) else 0.0,
        network_in=float(network_in),
        network_out=float(network_out)
    )
    db.session.add(feature)
    db.session.commit()

    print(f"  Features: errors={error_count}, CPU={cpu_avg:.1f}%, MEM={mem_avg:.1f}%")

    # Run detection
    rule_anomaly = 0
    rule_score = 0.0

    if error_count > 5:
        rule_anomaly = 1
        rule_score = min(error_count / 20.0, 1.0)

    if cpu_avg > 80:
        rule_anomaly = 1
        rule_score = max(rule_score, cpu_avg / 100.0)

    # IF detection
    if_anomaly = 0
    if_score = 0.0

    if if_detector.model is not None:
        try:
            X = pd.DataFrame([{
                'error_count': error_count,
                'error_rate': error_rate,
                'cpu_avg': cpu_avg,
                'mem_avg': mem_avg
            }])
            predictions = if_detector.model.predict(X)
            scores = if_detector.model.score_samples(X)
            if_anomaly = 1 if predictions[0] == -1 else 0
            if_score = float(abs(scores[0]))
        except Exception as e:
            print(f"  [WARN] IF detection failed: {e}")

    # Fusion
    final_anomaly = 1 if (rule_anomaly + if_anomaly) >= 1 else 0
    final_score = (rule_score + if_score) / 2.0

    if final_score >= 0.7:
        severity = 'High'
    elif final_score >= 0.4:
        severity = 'Medium'
    else:
        severity = 'Low'

    votes = rule_anomaly + if_anomaly
    detectors = []
    if rule_anomaly:
        detectors.append('rule')
    if if_anomaly:
        detectors.append('if')

    # Save detection
    detection = DetectionResult(
        timestamp=window_start,
        rule_anomaly=rule_anomaly,
        rule_score=rule_score,
        if_anomaly=if_anomaly,
        if_score=if_score,
        final_anomaly=final_anomaly,
        final_score=final_score,
        severity=severity if final_anomaly else 'Normal',
        votes=votes,
        detector_agreement=','.join(detectors)
    )
    db.session.add(detection)
    db.session.commit()

    print(f"  Detection: anomaly={final_anomaly}, score={final_score:.2f}, severity={severity}")

    # Generate alert if anomaly
    if final_anomaly:
        parts = []
        if error_count > 0:
            parts.append(f"Errors: {error_count}")
        if cpu_avg > 80:
            parts.append(f"High CPU: {cpu_avg:.1f}%")
        if mem_avg > 85:
            parts.append(f"High Memory: {mem_avg:.1f}%")

        message = " | ".join(parts) if parts else "Anomaly detected"

        alert = Alert(
            timestamp=window_start,
            severity=severity,
            final_score=final_score,
            votes=votes,
            detector_agreement=','.join(detectors),
            error_count=error_count,
            cpu_avg=cpu_avg,
            mem_avg=mem_avg,
            message=message,
            is_resolved=0
        )
        db.session.add(alert)
        db.session.commit()

        print(f"  [ALERT] {severity} - {message}")


if __name__ == '__main__':
    print("="*70)
    print("PROCESS HISTORICAL DATA")
    print("="*70)

    app = create_app('development')
    process_windows(app)

    print("\n" + "="*70)
    print("[SUCCESS] Processing complete")
    print("="*70)
    print("\nOpen dashboard: http://localhost:5000")
