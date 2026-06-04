"""
Script để train tất cả các ML models cho LogSentry AI

Chạy script này để train:
1. Isolation Forest
2. VAR (Vector Autoregression)
3. DeepLog (LSTM-based)

Usage:
    python train_all_models.py
"""
import sys
sys.path.insert(0, 'src')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from app import create_app, db
from app.models import LogEntry, MetricEntry, Feature
from detectors.ml_models import IsolationForestDetector
from detectors.statistical import VARDetector
from detectors.deeplog import DeepLogDetector


def extract_features_for_training():
    """Extract features từ database để train models"""

    app = create_app()

    with app.app_context():
        print("=" * 70)
        print("EXTRACTING FEATURES FROM DATABASE")
        print("=" * 70)

        # Get all features
        features = Feature.query.order_by(Feature.timestamp).all()

        if len(features) == 0:
            print("\n⚠️  Không có features trong database!")
            print("Vui lòng:")
            print("1. Chạy application và gửi logs/metrics")
            print("2. Hoặc import historical data: python import_pipeline_data.py")
            return None, None

        print(f"\n✓ Đã tìm thấy {len(features)} feature windows")

        # Convert to DataFrame
        features_df = pd.DataFrame([{
            'timestamp': f.timestamp,
            'error_count': f.error_count,
            'warn_count': f.warn_count,
            'info_count': f.info_count,
            'total_logs': f.total_logs,
            'error_rate': f.error_rate,
            'cpu_avg': f.cpu_avg,
            'mem_avg': f.mem_avg,
            'disk_io_avg': f.disk_io_avg,
            'network_in': f.network_in,
            'network_out': f.network_out
        } for f in features])

        print(f"✓ Features shape: {features_df.shape}")
        print(f"✓ Date range: {features_df['timestamp'].min()} to {features_df['timestamp'].max()}")

        # Get logs for DeepLog
        print(f"\nLoading logs...")
        logs = LogEntry.query.order_by(LogEntry.timestamp).all()

        if len(logs) > 0:
            logs_df = pd.DataFrame([{
                'timestamp': log.timestamp,
                'message': log.message,
                'level': log.level,
                'service': log.service,
                'host': log.host
            } for log in logs])
            print(f"✓ Đã load {len(logs_df)} logs")
        else:
            logs_df = None
            print("⚠️  Không có logs, DeepLog sẽ dùng features")

        return features_df, logs_df


def train_isolation_forest(features_df):
    """Train Isolation Forest model"""
    print("\n" + "=" * 70)
    print("1. TRAINING ISOLATION FOREST")
    print("=" * 70)

    try:
        detector = IsolationForestDetector(config={
            'contamination': 0.05,
            'n_estimators': 100,
            'random_state': 42
        })

        # Train
        detector.train(features_df)

        # Test detection
        result = detector.detect(features_df, train=False)
        stats = detector.get_statistics(result)

        print("\n--- Statistics ---")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

        # Save model
        detector.save_model('data/models/isolation_forest.pkl')
        print("\n✓ Model đã lưu vào: data/models/isolation_forest.pkl")

        return True

    except Exception as e:
        print(f"\n✗ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False


def train_var(features_df):
    """Train VAR model"""
    print("\n" + "=" * 70)
    print("2. TRAINING VAR (Vector Autoregression)")
    print("=" * 70)

    try:
        detector = VARDetector(config={
            'maxlags': 5,
            'train_ratio': 0.7,
            'threshold_sigma': 3
        })

        # Train
        detector.train(features_df)

        # Test detection
        result = detector.detect(features_df, train=False)
        stats = detector.get_statistics(result)

        print("\n--- Statistics ---")
        for key, value in stats.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.4f}")
            else:
                print(f"  {key}: {value}")

        print("\n✓ VAR model trained (stored in memory)")

        return True

    except Exception as e:
        print(f"\n✗ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False


def train_deeplog(features_df, logs_df):
    """Train DeepLog LSTM model"""
    print("\n" + "=" * 70)
    print("3. TRAINING DEEPLOG (LSTM)")
    print("=" * 70)

    try:
        detector = DeepLogDetector(config={
            'sequence_length': 10,
            'embedding_dim': 32,
            'lstm_units': 64,
            'epochs': 20,
            'batch_size': 32,
            'threshold': 0.5,
            'min_samples': 50
        })

        # Train
        detector.train(features_df, logs_df)

        if detector.model is not None:
            # Test detection
            result = detector.detect(features_df, logs_df, train=False)
            stats = detector.get_statistics(result)

            print("\n--- Statistics ---")
            for key, value in stats.items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")

            # Save model
            detector.save_model('data/models/deeplog')
            print("\n✓ Model đã lưu vào: data/models/deeplog")

            return True
        else:
            print("\n⚠️  DeepLog model không được train (không đủ data hoặc TensorFlow chưa cài)")
            return False

    except Exception as e:
        print(f"\n✗ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main training pipeline"""
    print("\n" + "=" * 70)
    print("LOGSENTRY AI - MODEL TRAINING PIPELINE")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now()}")

    # Extract features
    features_df, logs_df = extract_features_for_training()

    if features_df is None:
        print("\n✗ Không thể tiếp tục training")
        return

    # Train models
    results = {
        'isolation_forest': False,
        'var': False,
        'deeplog': False
    }

    results['isolation_forest'] = train_isolation_forest(features_df)
    results['var'] = train_var(features_df)
    results['deeplog'] = train_deeplog(features_df, logs_df)

    # Summary
    print("\n" + "=" * 70)
    print("TRAINING SUMMARY")
    print("=" * 70)

    for model, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"{model.upper()}: {status}")

    total_success = sum(results.values())
    print(f"\nTotal: {total_success}/3 models trained successfully")

    if total_success >= 2:
        print("\n✓ Training hoàn thành! Bạn có thể restart server để sử dụng models.")
    else:
        print("\n⚠️  Một số models không train được. Vui lòng check logs.")

    print(f"\nFinished at: {datetime.now()}")
    print("=" * 70)


if __name__ == '__main__':
    main()
