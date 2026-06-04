"""
Check data in database
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app, db
from app.models import LogEntry, MetricEntry, Feature, Alert

app = create_app('development')

with app.app_context():
    log_count = LogEntry.query.count()
    metric_count = MetricEntry.query.count()
    feature_count = Feature.query.count()
    alert_count = Alert.query.count()

    print("="*60)
    print("DATABASE DATA SUMMARY")
    print("="*60)
    print(f"Logs:     {log_count:6d}")
    print(f"Metrics:  {metric_count:6d}")
    print(f"Features: {feature_count:6d}")
    print(f"Alerts:   {alert_count:6d}")
    print("="*60)

    if alert_count > 0:
        print("\nRecent Alerts:")
        print("-"*60)
        alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(5).all()
        for alert in alerts:
            print(f"  [{alert.severity}] {alert.timestamp.strftime('%Y-%m-%d %H:%M')} - Score: {alert.final_score:.2f}")

    if log_count == 0:
        print("\n[WARNING] No logs found!")
        print("Run: python demo_data.py --mode both --duration 60")
