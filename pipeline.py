"""
Main Pipeline - LogSentry AI

Pipeline đầy đủ cho anomaly detection:
1. Generate synthetic data (optional)
2. Extract features
3. Run detectors (Rule-based, VAR, ML models)
4. Fusion & Severity scoring
5. Generate alerts
"""
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_generation.generate_logs import generate_dataset
from feature_extraction.extract_features import FeatureExtractor
from detectors.rule_based import RuleBasedDetector
from detectors.statistical import VARDetector
from detectors.ml_models import IsolationForestDetector, AutoencoderDetector
from fusion.fusion import AnomalyFusion

import pandas as pd
import os
from datetime import datetime


class LogSentryPipeline:
    """Pipeline chính cho anomaly detection"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.features_df = None
        self.results_df = None

    def step1_generate_data(self, num_days=7, window_minutes=5):
        """Bước 1: Tạo synthetic data"""
        print("\n" + "=" * 70)
        print("BƯỚC 1: TẠO SYNTHETIC DATA")
        print("=" * 70)

        generate_dataset(
            output_dir='data',
            num_days=num_days,
            window_minutes=window_minutes,
            logs_per_window=100,
            anomaly_probability=0.05
        )

    def step2_extract_features(self):
        """Bước 2: Trích xuất features"""
        print("\n" + "=" * 70)
        print("BƯỚC 2: TRÍCH XUẤT FEATURES")
        print("=" * 70)

        extractor = FeatureExtractor(window_minutes=5)
        self.features_df = extractor.process_and_save(
            log_file='data/raw/application.log',
            metrics_file='data/raw/system_metrics.jsonl',
            output_file='data/processed/features.csv'
        )

    def step3_run_detectors(self):
        """Bước 3: Chạy các detectors"""
        print("\n" + "=" * 70)
        print("BƯỚC 3: CHẠY CÁC DETECTORS")
        print("=" * 70)

        if self.features_df is None:
            print("Loading features từ file...")
            self.features_df = pd.read_csv('data/processed/features.csv')

        results = self.features_df.copy()

        # 3.1 Rule-based detector
        print("\n[1/4] Rule-based Detector")
        print("-" * 70)
        rule_detector = RuleBasedDetector()
        results = rule_detector.detect(results)

        stats = rule_detector.get_statistics(results)
        print(f"  ✓ Phát hiện: {stats['anomalies_detected']}/{stats['total_windows']} windows")
        if 'f1_score' in stats:
            print(f"  ✓ F1-Score: {stats['f1_score']:.4f}")

        # 3.2 VAR detector
        print("\n[2/4] VAR Statistical Detector")
        print("-" * 70)
        var_detector = VARDetector()
        results = var_detector.detect(results, train=True)

        stats = var_detector.get_statistics(results)
        print(f"  ✓ Phát hiện: {stats['anomalies_detected']}/{stats['total_windows']} windows")
        if 'f1_score' in stats:
            print(f"  ✓ F1-Score: {stats['f1_score']:.4f}")

        # 3.3 Isolation Forest
        print("\n[3/4] Isolation Forest Detector")
        print("-" * 70)
        if_detector = IsolationForestDetector()
        if_results = if_detector.detect(results, train=True)
        results['if_anomaly'] = if_results['if_anomaly']
        results['if_score'] = if_results['if_score']

        stats = if_detector.get_statistics(if_results)
        print(f"  ✓ Phát hiện: {stats['anomalies_detected']}/{stats['total_windows']} windows")
        if 'f1_score' in stats:
            print(f"  ✓ F1-Score: {stats['f1_score']:.4f}")

        # Save model
        if_detector.save_model('data/models/isolation_forest.pkl')

        # 3.4 Autoencoder
        print("\n[4/4] Autoencoder Detector")
        print("-" * 70)
        ae_detector = AutoencoderDetector()
        ae_results = ae_detector.detect(results, train=True)
        results['ae_anomaly'] = ae_results['ae_anomaly']
        results['ae_score'] = ae_results['ae_score']

        stats = ae_detector.get_statistics(ae_results)
        print(f"  ✓ Phát hiện: {stats['anomalies_detected']}/{stats['total_windows']} windows")
        if 'f1_score' in stats:
            print(f"  ✓ F1-Score: {stats['f1_score']:.4f}")

        self.results_df = results

    def step4_fusion(self):
        """Bước 4: Fusion và xác định severity"""
        print("\n" + "=" * 70)
        print("BƯỚC 4: FUSION & SEVERITY SCORING")
        print("=" * 70)

        if self.results_df is None:
            raise ValueError("Chưa có results từ detectors. Hãy chạy step3_run_detectors() trước.")

        fusion = AnomalyFusion()
        self.results_df = fusion.fuse(self.results_df)

        # Statistics
        stats = fusion.get_statistics(self.results_df)
        print("\nKết quả Fusion:")
        print(f"  Tổng anomalies: {stats['anomalies_detected']}/{stats['total_windows']}")
        print(f"  - High severity: {stats['severity_high']}")
        print(f"  - Medium severity: {stats['severity_medium']}")
        print(f"  - Low severity: {stats['severity_low']}")

        if 'f1_score' in stats:
            print(f"\n  Precision: {stats['precision']:.4f}")
            print(f"  Recall: {stats['recall']:.4f}")
            print(f"  F1-Score: {stats['f1_score']:.4f}")

        # Vote distribution
        print(f"\n  Vote distribution:")
        for votes, count in stats['vote_distribution'].items():
            print(f"    {votes} votes: {count} windows")

        # Save results
        self.results_df.to_csv('data/processed/final_results.csv', index=False)
        print(f"\n  ✓ Kết quả đã lưu vào: data/processed/final_results.csv")

    def step5_generate_alerts(self, output_file='data/processed/alerts.csv'):
        """Bước 5: Tạo alerts"""
        print("\n" + "=" * 70)
        print("BƯỚC 5: TẠO ALERTS")
        print("=" * 70)

        if self.results_df is None:
            print("Loading results từ file...")
            self.results_df = pd.read_csv('data/processed/final_results.csv')

        fusion = AnomalyFusion()

        # Get all alerts
        all_alerts = fusion.get_alerts(self.results_df)

        print(f"\nTổng số alerts: {len(all_alerts)}")

        # Show by severity
        for severity in ['High', 'Medium', 'Low']:
            alerts = fusion.get_alerts(self.results_df, severity_filter=severity)
            print(f"  {severity} severity: {len(alerts)}")

            if len(alerts) > 0:
                print(f"\n  Top {min(3, len(alerts))} {severity} alerts:")
                for idx, row in alerts.head(3).iterrows():
                    print(f"    - {row['timestamp']}: score={row['final_score']:.3f}, "
                          f"votes={row['votes']}, detectors={row['detector_agreement']}")

        # Save alerts
        all_alerts.to_csv(output_file, index=False)
        print(f"\n  ✓ Alerts đã lưu vào: {output_file}")

    def run_full_pipeline(self, generate_data=True):
        """Chạy toàn bộ pipeline"""
        print("\n")
        print("╔" + "=" * 68 + "╗")
        print("║" + " " * 20 + "LOGSENTRY AI PIPELINE" + " " * 27 + "║")
        print("╚" + "=" * 68 + "╝")

        start_time = datetime.now()

        try:
            if generate_data:
                self.step1_generate_data()

            self.step2_extract_features()
            self.step3_run_detectors()
            self.step4_fusion()
            self.step5_generate_alerts()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print("\n" + "=" * 70)
            print("✅ PIPELINE HOÀN TẤT THÀNH CÔNG!")
            print("=" * 70)
            print(f"Thời gian chạy: {duration:.2f} giây")
            print(f"\nKết quả:")
            print(f"  - Features: data/processed/features.csv")
            print(f"  - Final results: data/processed/final_results.csv")
            print(f"  - Alerts: data/processed/alerts.csv")
            print(f"  - Models: data/models/")

        except Exception as e:
            print(f"\n❌ LỖI: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='LogSentry AI Pipeline')
    parser.add_argument('--no-generate', action='store_true',
                        help='Skip data generation (sử dụng data có sẵn)')
    parser.add_argument('--days', type=int, default=7,
                        help='Số ngày data để generate (default: 7)')

    args = parser.parse_args()

    pipeline = LogSentryPipeline()
    pipeline.run_full_pipeline(generate_data=not args.no_generate)


if __name__ == '__main__':
    main()
