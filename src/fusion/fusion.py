"""
Fusion Module - Kết hợp kết quả từ nhiều detectors

Kết hợp kết quả từ:
1. Rule-based detector
2. VAR statistical detector
3. ML models (Isolation Forest, Autoencoder)

Và xác định severity level: High, Medium, Low
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class AnomalyFusion:
    """
    Kết hợp kết quả từ nhiều detectors và xác định severity

    Fusion logic:
    - Voting: Số lượng detectors phát hiện anomaly
    - Weighted scoring: Kết hợp scores từ các detectors
    - Severity: High/Medium/Low dựa trên voting và scores
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()

    def _default_config(self) -> Dict:
        return {
            # Trọng số cho mỗi detector
            'weights': {
                'rule': 0.3,
                'var': 0.25,
                'if': 0.25,
                'ae': 0.2,
            },
            # Thresholds cho severity
            'high_threshold': 0.7,    # >= 0.7 → High
            'medium_threshold': 0.4,  # >= 0.4 → Medium
            # < 0.4 → Low hoặc không phải anomaly
            'min_votes': 2,  # Tối thiểu số detectors phải đồng ý để xác nhận anomaly
        }

    def fuse(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Kết hợp kết quả từ các detectors

        Args:
            results_df: DataFrame chứa kết quả từ tất cả detectors
                        Expected columns: rule_anomaly, var_anomaly, if_anomaly, ae_anomaly
                                        rule_score, var_score, if_score, ae_score

        Returns:
            DataFrame với columns:
            - final_anomaly: 0/1
            - final_score: 0-1
            - severity: 'High', 'Medium', 'Low', 'Normal'
            - votes: số detectors phát hiện
            - detector_agreement: danh sách detectors phát hiện
        """

        result = results_df.copy()

        # Khởi tạo columns
        result['votes'] = 0
        result['final_score'] = 0.0
        result['final_anomaly'] = 0
        result['severity'] = 'Normal'
        result['detector_agreement'] = ''

        # Detectors có sẵn
        available_detectors = []
        if 'rule_anomaly' in result.columns:
            available_detectors.append('rule')
        if 'var_anomaly' in result.columns:
            available_detectors.append('var')
        if 'if_anomaly' in result.columns:
            available_detectors.append('if')
        if 'ae_anomaly' in result.columns:
            available_detectors.append('ae')

        if not available_detectors:
            print("⚠️  Không có detector nào khả dụng!")
            return result

        # Normalize weights
        total_weight = sum(self.config['weights'][d] for d in available_detectors)
        normalized_weights = {d: self.config['weights'][d] / total_weight for d in available_detectors}

        # Fusion cho từng window
        for idx, row in result.iterrows():
            votes = 0
            weighted_score = 0.0
            detectors_voted = []

            for detector in available_detectors:
                anomaly_col = f'{detector}_anomaly'
                score_col = f'{detector}_score'

                # Vote
                if row.get(anomaly_col, 0) == 1:
                    votes += 1
                    detectors_voted.append(detector)

                # Weighted score
                score = row.get(score_col, 0.0)
                weighted_score += normalized_weights[detector] * score

            # Update kết quả
            result.at[idx, 'votes'] = votes
            result.at[idx, 'final_score'] = weighted_score
            result.at[idx, 'detector_agreement'] = ','.join(detectors_voted)

            # Xác định anomaly dựa trên min_votes
            if votes >= self.config['min_votes']:
                result.at[idx, 'final_anomaly'] = 1

                # Xác định severity
                if weighted_score >= self.config['high_threshold']:
                    result.at[idx, 'severity'] = 'High'
                elif weighted_score >= self.config['medium_threshold']:
                    result.at[idx, 'severity'] = 'Medium'
                else:
                    result.at[idx, 'severity'] = 'Low'
            elif votes == 1 and weighted_score >= self.config['medium_threshold']:
                # Trường hợp đặc biệt: chỉ 1 detector nhưng score cao
                result.at[idx, 'final_anomaly'] = 1
                result.at[idx, 'severity'] = 'Low'
            else:
                result.at[idx, 'final_anomaly'] = 0
                result.at[idx, 'severity'] = 'Normal'

        return result

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê về fusion results"""

        total = len(result_df)
        detected = result_df['final_anomaly'].sum()

        # Severity breakdown
        severity_counts = result_df['severity'].value_counts().to_dict()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
            'severity_high': severity_counts.get('High', 0),
            'severity_medium': severity_counts.get('Medium', 0),
            'severity_low': severity_counts.get('Low', 0),
            'severity_normal': severity_counts.get('Normal', 0),
        }

        # Voting statistics
        vote_counts = result_df['votes'].value_counts().sort_index().to_dict()
        stats['vote_distribution'] = vote_counts

        # Nếu có ground truth
        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['final_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['final_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['final_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()
            true_negatives = ((result_df['final_anomaly'] == 0) & (result_df['is_anomaly'] == False)).sum()

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

    def get_alerts(self, result_df: pd.DataFrame, severity_filter: str = None) -> pd.DataFrame:
        """
        Lấy danh sách alerts

        Args:
            result_df: Fused results
            severity_filter: 'High', 'Medium', 'Low', hoặc None (all)

        Returns:
            DataFrame chứa các anomaly windows
        """

        # Filter anomalies
        alerts = result_df[result_df['final_anomaly'] == 1].copy()

        # Filter by severity
        if severity_filter:
            alerts = alerts[alerts['severity'] == severity_filter]

        # Select relevant columns
        alert_cols = ['timestamp', 'severity', 'final_score', 'votes', 'detector_agreement']

        # Add feature columns for context
        feature_cols = ['error_count', 'warn_count', 'cpu_avg', 'mem_avg', 'total_logs']
        for col in feature_cols:
            if col in alerts.columns:
                alert_cols.append(col)

        # Add reasons if available
        if 'rule_reasons' in alerts.columns:
            alert_cols.append('rule_reasons')

        alerts = alerts[alert_cols]

        # Sort by severity and score
        severity_order = {'High': 0, 'Medium': 1, 'Low': 2}
        alerts['severity_order'] = alerts['severity'].map(severity_order)
        alerts = alerts.sort_values(['severity_order', 'final_score'], ascending=[True, False])
        alerts = alerts.drop('severity_order', axis=1)

        return alerts


if __name__ == '__main__':
    # Test
    import sys
    sys.path.append('.')

    # Giả sử ta đã có results từ các detectors
    # Load hoặc tạo mock data
    print("Testing Fusion Module...")

    # Mock data
    data = {
        'timestamp': pd.date_range('2024-01-01', periods=100, freq='5min'),
        'rule_anomaly': np.random.choice([0, 1], 100, p=[0.9, 0.1]),
        'rule_score': np.random.random(100) * 0.5,
        'var_anomaly': np.random.choice([0, 1], 100, p=[0.95, 0.05]),
        'var_score': np.random.random(100) * 0.4,
        'if_anomaly': np.random.choice([0, 1], 100, p=[0.93, 0.07]),
        'if_score': np.random.random(100) * 0.6,
        'ae_anomaly': np.random.choice([0, 1], 100, p=[0.94, 0.06]),
        'ae_score': np.random.random(100) * 0.5,
        'error_count': np.random.randint(0, 10, 100),
        'cpu_avg': np.random.uniform(20, 80, 100),
    }

    results_df = pd.DataFrame(data)

    # Fuse
    fusion = AnomalyFusion()
    fused = fusion.fuse(results_df)

    # Stats
    stats = fusion.get_statistics(fused)
    print("\n=== Fusion Statistics ===")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        elif isinstance(value, dict):
            print(f"{key}:")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")

    # Get alerts
    alerts = fusion.get_alerts(fused, severity_filter='High')
    print(f"\n=== High Severity Alerts ({len(alerts)}) ===")
    if len(alerts) > 0:
        print(alerts.head(10))

    # Save
    fused.to_csv('data/processed/fused_results.csv', index=False)
    print("\nFused results saved to: data/processed/fused_results.csv")
