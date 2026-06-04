"""
Module trích xuất features từ raw logs và metrics
"""
import json
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict
import os


class FeatureExtractor:
    """Trích xuất features từ logs và metrics theo time window"""

    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes

    def parse_logs(self, log_file: str) -> pd.DataFrame:
        """Parse log file thành DataFrame"""
        logs = []

        with open(log_file, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    logs.append(log_entry)
                except json.JSONDecodeError:
                    continue

        df = pd.DataFrame(logs)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def parse_metrics(self, metrics_file: str) -> pd.DataFrame:
        """Parse metrics file thành DataFrame"""
        metrics = []

        with open(metrics_file, 'r') as f:
            for line in f:
                try:
                    metric_entry = json.loads(line.strip())
                    metrics.append(metric_entry)
                except json.JSONDecodeError:
                    continue

        df = pd.DataFrame(metrics)
        if not df.empty:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        return df

    def extract_log_features(self, logs_df: pd.DataFrame) -> pd.DataFrame:
        """
        Trích xuất features từ logs theo time window

        Features:
        - error_count: Số lượng ERROR logs
        - warn_count: Số lượng WARN logs
        - info_count: Số lượng INFO logs
        - debug_count: Số lượng DEBUG logs
        - total_logs: Tổng số logs
        - error_rate: Tỷ lệ error
        - unique_services: Số service khác nhau
        """

        if logs_df.empty:
            return pd.DataFrame()

        # Set timestamp làm index và resample theo window
        logs_df = logs_df.set_index('timestamp')

        features = []

        # Group by time window
        for window_start, group in logs_df.groupby(pd.Grouper(freq=f'{self.window_minutes}min')):
            if group.empty:
                continue

            # Count by level
            level_counts = Counter(group['level'])

            feature_dict = {
                'timestamp': window_start,
                'error_count': level_counts.get('ERROR', 0),
                'warn_count': level_counts.get('WARN', 0),
                'info_count': level_counts.get('INFO', 0),
                'debug_count': level_counts.get('DEBUG', 0),
                'total_logs': len(group),
                'unique_services': group['service'].nunique(),
            }

            # Tính error rate
            if feature_dict['total_logs'] > 0:
                feature_dict['error_rate'] = feature_dict['error_count'] / feature_dict['total_logs']
            else:
                feature_dict['error_rate'] = 0.0

            features.append(feature_dict)

        features_df = pd.DataFrame(features)
        return features_df

    def combine_features(self, log_features: pd.DataFrame, metrics_df: pd.DataFrame) -> pd.DataFrame:
        """
        Kết hợp log features với system metrics

        Output: Features.csv với columns:
        - timestamp
        - error_count, warn_count, info_count, debug_count
        - total_logs, error_rate, unique_services
        - cpu_avg, mem_avg, disk_io_avg, network_in, network_out
        - is_anomaly, anomaly_type (ground truth)
        """

        # Đảm bảo cả hai có timestamp
        if log_features.empty or metrics_df.empty:
            return pd.DataFrame()

        # Merge theo timestamp
        combined = pd.merge(
            log_features,
            metrics_df,
            on='timestamp',
            how='outer'
        )

        # Fill NaN values
        combined = combined.fillna(0)

        # Sort by timestamp
        combined = combined.sort_values('timestamp')

        return combined

    def process_and_save(self, log_file: str, metrics_file: str, output_file: str):
        """
        Process logs và metrics, sau đó lưu features.csv
        """

        print("Đang parse logs...")
        logs_df = self.parse_logs(log_file)
        print(f"  Đã parse {len(logs_df)} log entries")

        print("Đang parse metrics...")
        metrics_df = self.parse_metrics(metrics_file)
        print(f"  Đã parse {len(metrics_df)} metric entries")

        print("Đang trích xuất features từ logs...")
        log_features = self.extract_log_features(logs_df)
        print(f"  Đã tạo {len(log_features)} time windows từ logs")

        print("Đang kết hợp features...")
        combined_features = self.combine_features(log_features, metrics_df)
        print(f"  Tổng số features: {len(combined_features)} windows")

        # Lưu file
        print(f"Đang lưu vào {output_file}...")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        combined_features.to_csv(output_file, index=False)

        print(f"\n✅ Features đã được lưu thành công!")
        print(f"   Shape: {combined_features.shape}")
        print(f"   Columns: {list(combined_features.columns)}")

        # Thống kê
        if 'is_anomaly' in combined_features.columns:
            num_anomalies = combined_features['is_anomaly'].sum()
            print(f"   Anomalies: {num_anomalies}/{len(combined_features)} ({num_anomalies/len(combined_features)*100:.2f}%)")

        return combined_features


if __name__ == '__main__':
    extractor = FeatureExtractor(window_minutes=5)

    extractor.process_and_save(
        log_file='data/raw/application.log',
        metrics_file='data/raw/system_metrics.jsonl',
        output_file='data/processed/features.csv'
    )
