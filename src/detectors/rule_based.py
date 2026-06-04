"""
Rule-based Anomaly Detector

Phát hiện anomaly dựa trên các rule đơn giản được định nghĩa trước
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class RuleBasedDetector:
    """
    Detector sử dụng các rule đơn giản để phát hiện anomaly

    Rules:
    1. error_count > threshold → ALERT
    2. error_rate > threshold → ALERT
    3. cpu_avg > threshold → ALERT
    4. mem_avg > threshold → ALERT
    5. Kết hợp nhiều điều kiện
    """

    def __init__(self, config: Dict = None):
        """
        Args:
            config: Dictionary chứa thresholds cho các rules
        """
        self.config = config or self._default_config()

    def _default_config(self) -> Dict:
        """Default thresholds"""
        return {
            'error_count_threshold': 5,
            'error_rate_threshold': 0.05,  # 5%
            'warn_count_threshold': 20,
            'cpu_threshold': 80,  # %
            'mem_threshold': 85,  # %
            'total_logs_spike_factor': 3,  # 3x normal
        }

    def detect(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Phát hiện anomaly trong features

        Args:
            features_df: DataFrame chứa features

        Returns:
            DataFrame với column 'rule_anomaly' (0/1) và 'rule_reasons'
        """

        result = features_df.copy()
        result['rule_anomaly'] = 0
        result['rule_reasons'] = ''
        result['rule_score'] = 0.0

        for idx, row in result.iterrows():
            is_anomaly = False
            reasons = []
            score = 0.0

            # Rule 1: Error count
            if row.get('error_count', 0) > self.config['error_count_threshold']:
                is_anomaly = True
                reasons.append(f"error_count={row['error_count']:.0f}")
                score += 0.3

            # Rule 2: Error rate
            if row.get('error_rate', 0) > self.config['error_rate_threshold']:
                is_anomaly = True
                reasons.append(f"error_rate={row['error_rate']:.2%}")
                score += 0.2

            # Rule 3: Warn count
            if row.get('warn_count', 0) > self.config['warn_count_threshold']:
                is_anomaly = True
                reasons.append(f"warn_count={row['warn_count']:.0f}")
                score += 0.1

            # Rule 4: CPU high
            if row.get('cpu_avg', 0) > self.config['cpu_threshold']:
                is_anomaly = True
                reasons.append(f"cpu={row['cpu_avg']:.1f}%")
                score += 0.2

            # Rule 5: Memory high
            if row.get('mem_avg', 0) > self.config['mem_threshold']:
                is_anomaly = True
                reasons.append(f"mem={row['mem_avg']:.1f}%")
                score += 0.2

            # Rule 6: Log spike
            if 'total_logs' in result.columns:
                median_logs = result['total_logs'].median()
                if row['total_logs'] > median_logs * self.config['total_logs_spike_factor']:
                    is_anomaly = True
                    reasons.append(f"log_spike={row['total_logs']:.0f}")
                    score += 0.15

            if is_anomaly:
                result.at[idx, 'rule_anomaly'] = 1
                result.at[idx, 'rule_reasons'] = '; '.join(reasons)
                result.at[idx, 'rule_score'] = min(score, 1.0)  # Cap at 1.0

        return result

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê về kết quả detection"""

        total = len(result_df)
        detected = result_df['rule_anomaly'].sum()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
        }

        # Nếu có ground truth
        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['rule_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['rule_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['rule_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()
            true_negatives = ((result_df['rule_anomaly'] == 0) & (result_df['is_anomaly'] == False)).sum()

            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            stats.update({
                'true_positives': int(true_positives),
                'false_positives': int(false_positives),
                'false_negatives': int(false_negatives),
                'true_negatives': int(true_negatives),
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
            })

        return stats


if __name__ == '__main__':
    # Test với sample data
    import sys
    sys.path.append('.')

    # Load features
    features_df = pd.read_csv('data/processed/features.csv')

    # Khởi tạo detector
    detector = RuleBasedDetector()

    # Detect
    print("Đang chạy Rule-based detector...")
    result = detector.detect(features_df)

    # Stats
    stats = detector.get_statistics(result)
    print("\n=== Rule-based Detector Statistics ===")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    # Lưu kết quả
    result.to_csv('data/processed/rule_based_results.csv', index=False)
    print("\nKết quả đã lưu vào: data/processed/rule_based_results.csv")
