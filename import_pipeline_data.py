"""
Import data từ pipeline CSV files vào Flask database

Sử dụng khi bạn đã chạy pipeline.py và muốn import kết quả vào UI
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app, db
from app.models import Feature, DetectionResult, Alert
import argparse


def import_features(csv_file):
    """Import features từ CSV"""
    print(f"\n[1/3] Importing features from {csv_file}...")

    if not Path(csv_file).exists():
        print(f"  [ERROR] File not found: {csv_file}")
        return 0

    df = pd.read_csv(csv_file)
    count = 0

    for _, row in df.iterrows():
        try:
            feature = Feature(
                timestamp=pd.to_datetime(row['timestamp']),
                error_count=int(row['error_count']),
                error_rate=float(row['error_rate']),
                cpu_avg=float(row.get('cpu_avg', 0)),
                cpu_max=float(row.get('cpu_max', 0)),
                mem_avg=float(row.get('mem_avg', 0)),
                mem_max=float(row.get('mem_max', 0)),
                disk_io_avg=float(row.get('disk_io_avg', 0)),
                network_in_avg=float(row.get('network_in_avg', 0)),
                network_out_avg=float(row.get('network_out_avg', 0)),
                unique_services=int(row.get('unique_services', 1))
            )
            db.session.add(feature)
            count += 1

            if count % 100 == 0:
                db.session.commit()
                print(f"  Imported {count} features...")

        except Exception as e:
            print(f"  [WARN] Skip row: {e}")
            continue

    db.session.commit()
    print(f"  [OK] Imported {count} features")
    return count


def import_results(csv_file):
    """Import detection results từ CSV"""
    print(f"\n[2/3] Importing detection results from {csv_file}...")

    if not Path(csv_file).exists():
        print(f"  [ERROR] File not found: {csv_file}")
        return 0

    df = pd.read_csv(csv_file)
    count = 0

    for _, row in df.iterrows():
        try:
            # Find corresponding feature
            timestamp = pd.to_datetime(row['timestamp'])
            feature = Feature.query.filter_by(timestamp=timestamp).first()

            if not feature:
                continue

            result = DetectionResult(
                feature_id=feature.id,
                timestamp=timestamp,
                rule_anomaly=bool(row.get('rule_anomaly', False)),
                rule_score=float(row.get('rule_score', 0)),
                var_anomaly=bool(row.get('var_anomaly', False)),
                var_score=float(row.get('var_score', 0)),
                if_anomaly=bool(row.get('if_anomaly', False)),
                if_score=float(row.get('if_score', 0)),
                ae_anomaly=bool(row.get('ae_anomaly', False)),
                ae_score=float(row.get('ae_score', 0))
            )
            db.session.add(result)
            count += 1

            if count % 100 == 0:
                db.session.commit()
                print(f"  Imported {count} results...")

        except Exception as e:
            print(f"  [WARN] Skip row: {e}")
            continue

    db.session.commit()
    print(f"  [OK] Imported {count} detection results")
    return count


def import_alerts(csv_file):
    """Import alerts từ CSV"""
    print(f"\n[3/3] Importing alerts from {csv_file}...")

    if not Path(csv_file).exists():
        print(f"  [ERROR] File not found: {csv_file}")
        return 0

    df = pd.read_csv(csv_file)
    count = 0

    for _, row in df.iterrows():
        try:
            # Find corresponding feature
            timestamp = pd.to_datetime(row['timestamp'])
            feature = Feature.query.filter_by(timestamp=timestamp).first()

            if not feature:
                continue

            alert = Alert(
                feature_id=feature.id,
                timestamp=timestamp,
                severity=row.get('severity', 'Low'),
                final_score=float(row.get('final_score', 0)),
                votes=int(row.get('votes', 0)),
                error_count=int(row.get('error_count', 0)),
                cpu_avg=float(row.get('cpu_avg', 0)),
                mem_avg=float(row.get('mem_avg', 0)),
                message=row.get('detector_agreement', 'Anomaly detected'),
                is_resolved=False
            )
            db.session.add(alert)
            count += 1

            if count % 100 == 0:
                db.session.commit()
                print(f"  Imported {count} alerts...")

        except Exception as e:
            print(f"  [WARN] Skip row: {e}")
            continue

    db.session.commit()
    print(f"  [OK] Imported {count} alerts")
    return count


def main():
    parser = argparse.ArgumentParser(description='Import pipeline data to database')
    parser.add_argument('--features', default='data/processed/features.csv',
                       help='Path to features CSV file')
    parser.add_argument('--results', default='data/processed/final_results.csv',
                       help='Path to results CSV file')
    parser.add_argument('--alerts', default='data/processed/alerts.csv',
                       help='Path to alerts CSV file')
    parser.add_argument('--clear', action='store_true',
                       help='Clear existing data before import')

    args = parser.parse_args()

    print("="*70)
    print("IMPORT PIPELINE DATA TO DATABASE")
    print("="*70)

    app = create_app('development')

    with app.app_context():
        if args.clear:
            print("\n[CLEAR] Clearing existing data...")
            Alert.query.delete()
            DetectionResult.query.delete()
            Feature.query.delete()
            db.session.commit()
            print("  [OK] Data cleared")

        # Import data
        feature_count = import_features(args.features)
        result_count = import_results(args.results)
        alert_count = import_alerts(args.alerts)

        print("\n" + "="*70)
        print("[SUCCESS] IMPORT COMPLETE")
        print("="*70)
        print(f"Features imported:  {feature_count}")
        print(f"Results imported:   {result_count}")
        print(f"Alerts imported:    {alert_count}")
        print("\nOpen dashboard: http://localhost:5000")


if __name__ == '__main__':
    main()
