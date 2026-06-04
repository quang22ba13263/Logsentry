"""
Statistical Anomaly Detector sử dụng VAR (Vector Autoregression) Model

Phát hiện anomaly dựa trên deviation từ baseline forecast
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class VARDetector:
    """
    Detector sử dụng VAR model để dự báo và phát hiện anomaly

    Nguyên lý:
    1. Train VAR model trên dữ liệu lịch sử (baseline)
    2. Forecast giá trị tiếp theo
    3. Tính residual = actual - forecast
    4. Anomaly nếu residual vượt threshold (based on std)
    """

    def __init__(self, config: Dict = None):
        """
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        self.model = None
        self.feature_columns = None
        self.mean_residuals = None
        self.std_residuals = None

    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'maxlags': 5,  # VAR model lags
            'train_ratio': 0.7,  # Tỷ lệ data dùng để train
            'threshold_sigma': 3,  # Số standard deviation để xác định anomaly
        }

    def _prepare_data(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """Chuẩn bị data cho VAR model"""

        # Chọn các numeric features
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()

        # Loại bỏ các column không cần thiết
        exclude_cols = ['is_anomaly', 'rule_anomaly', 'rule_score', 'timestamp']
        feature_cols = [col for col in numeric_cols if col not in exclude_cols]

        # Fill missing values
        data = features_df[feature_cols].copy()
        data = data.fillna(method='ffill').fillna(method='bfill').fillna(0)

        self.feature_columns = feature_cols

        return data

    def train(self, features_df: pd.DataFrame):
        """
        Train VAR model trên dữ liệu lịch sử

        Args:
            features_df: DataFrame chứa features
        """

        try:
            from statsmodels.tsa.api import VAR as VARModel
        except ImportError:
            print("⚠️  statsmodels chưa được cài đặt. Statistical detector sẽ dùng baseline đơn giản.")
            self.model = None
            return

        print("Đang train VAR model...")

        # Prepare data
        data = self._prepare_data(features_df)

        # Split train/test
        train_size = int(len(data) * self.config['train_ratio'])
        train_data = data.iloc[:train_size]

        # Train VAR model
        try:
            model = VARModel(train_data)
            maxlags = min(self.config['maxlags'], len(train_data) // 2)
            self.model = model.fit(maxlags=maxlags, ic='aic')

            print(f"  VAR model trained với {maxlags} lags")
            print(f"  Features: {self.feature_columns}")

        except Exception as e:
            print(f"  ⚠️  Lỗi khi train VAR model: {e}")
            print("  Sẽ sử dụng baseline đơn giản thay thế.")
            self.model = None

    def _simple_baseline_detect(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Fallback method: Sử dụng moving average và std làm baseline

        Nếu VAR model không khả dụng, sử dụng phương pháp đơn giản:
        - Baseline = rolling mean
        - Anomaly nếu value > mean + threshold * std
        """

        data = self._prepare_data(features_df)
        result = features_df.copy()

        result['var_anomaly'] = 0
        result['var_score'] = 0.0
        result['var_reasons'] = ''

        # Sử dụng rolling window
        window_size = 20

        for col in self.feature_columns:
            rolling_mean = data[col].rolling(window=window_size, min_periods=1).mean()
            rolling_std = data[col].rolling(window=window_size, min_periods=1).std()

            # Tính z-score
            z_scores = np.abs((data[col] - rolling_mean) / (rolling_std + 1e-6))

            # Anomaly nếu z-score > threshold
            anomalies = z_scores > self.config['threshold_sigma']

            for idx in anomalies[anomalies].index:
                result.at[idx, 'var_anomaly'] = 1
                current_score = result.at[idx, 'var_score']
                result.at[idx, 'var_score'] = min(current_score + z_scores[idx] / 10, 1.0)

                reasons = result.at[idx, 'var_reasons']
                new_reason = f"{col}_zscore={z_scores[idx]:.2f}"
                result.at[idx, 'var_reasons'] = f"{reasons}; {new_reason}" if reasons else new_reason

        return result

    def detect(self, features_df: pd.DataFrame, train: bool = True) -> pd.DataFrame:
        """
        Phát hiện anomaly sử dụng VAR model

        Args:
            features_df: DataFrame chứa features
            train: Có train model trước không

        Returns:
            DataFrame với columns: 'var_anomaly', 'var_score', 'var_reasons'
        """

        if train or self.model is None:
            self.train(features_df)

        # Nếu không có model, dùng baseline đơn giản
        if self.model is None:
            return self._simple_baseline_detect(features_df)

        # Prepare data
        data = self._prepare_data(features_df)

        result = features_df.copy()
        result['var_anomaly'] = 0
        result['var_score'] = 0.0
        result['var_reasons'] = ''

        # Forecast và tính residuals
        lag_order = self.model.k_ar

        for i in range(lag_order, len(data)):
            try:
                # Lấy history để forecast
                history = data.iloc[i - lag_order:i]

                # Forecast 1 step ahead
                forecast = self.model.forecast(history.values, steps=1)

                # Actual value
                actual = data.iloc[i].values

                # Residual
                residual = actual - forecast[0]

                # Tính anomaly score dựa trên residual
                # Sử dụng normalized residual (z-score)
                if i == lag_order:
                    # Initialize với residual đầu tiên
                    residual_history = [residual]
                else:
                    residual_history.append(residual)

                # Tính mean và std của residuals
                if len(residual_history) >= 10:
                    residual_array = np.array(residual_history[-50:])  # Chỉ dùng 50 windows gần nhất
                    mean_res = residual_array.mean(axis=0)
                    std_res = residual_array.std(axis=0) + 1e-6

                    # Normalized residual
                    normalized_residual = np.abs((residual - mean_res) / std_res)

                    # Anomaly nếu normalized residual vượt threshold
                    max_normalized = normalized_residual.max()

                    if max_normalized > self.config['threshold_sigma']:
                        result.at[i, 'var_anomaly'] = 1
                        result.at[i, 'var_score'] = min(max_normalized / 10, 1.0)

                        # Tìm feature có residual cao nhất
                        max_idx = normalized_residual.argmax()
                        max_feature = self.feature_columns[max_idx]
                        result.at[i, 'var_reasons'] = f"{max_feature}_residual={normalized_residual[max_idx]:.2f}sigma"

            except Exception as e:
                # Nếu có lỗi, bỏ qua window này
                continue

        return result

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê về kết quả detection"""

        total = len(result_df)
        detected = result_df['var_anomaly'].sum()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
        }

        # Nếu có ground truth
        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['var_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['var_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['var_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()
            true_negatives = ((result_df['var_anomaly'] == 0) & (result_df['is_anomaly'] == False)).sum()

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
    # Test
    import sys
    sys.path.append('.')

    # Load features
    features_df = pd.read_csv('data/processed/features.csv')

    # Khởi tạo detector
    detector = VARDetector()

    # Detect
    print("Đang chạy VAR detector...")
    result = detector.detect(features_df, train=True)

    # Stats
    stats = detector.get_statistics(result)
    print("\n=== VAR Detector Statistics ===")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    # Lưu kết quả
    result.to_csv('data/processed/var_results.csv', index=False)
    print("\nKết quả đã lưu vào: data/processed/var_results.csv")
