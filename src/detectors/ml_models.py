"""
Machine Learning Models cho Anomaly Detection

Bao gồm:
1. Isolation Forest
2. Autoencoder (Neural Network)
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import pickle
import os
import warnings
warnings.filterwarnings('ignore')


class IsolationForestDetector:
    """
    Anomaly detector sử dụng Isolation Forest

    Isolation Forest phát hiện anomaly bằng cách "cô lập" chúng.
    Anomalies dễ bị cô lập hơn normal points.
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.model = None
        self.scaler = None
        self.feature_columns = None

    def _default_config(self) -> Dict:
        return {
            'contamination': 0.05,  # Tỷ lệ anomaly dự kiến
            'n_estimators': 100,
            'random_state': 42,
        }

    def _prepare_data(self, features_df: pd.DataFrame) -> np.ndarray:
        """Chuẩn bị và normalize data"""

        # Chọn numeric features
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()
        exclude_cols = ['is_anomaly', 'rule_anomaly', 'rule_score', 'var_anomaly', 'var_score', 'timestamp']
        feature_cols = [col for col in numeric_cols if col not in exclude_cols]

        self.feature_columns = feature_cols

        # Extract và fill missing
        data = features_df[feature_cols].fillna(0).values

        # Normalize
        from sklearn.preprocessing import StandardScaler
        if self.scaler is None:
            self.scaler = StandardScaler()
            data_scaled = self.scaler.fit_transform(data)
        else:
            data_scaled = self.scaler.transform(data)

        return data_scaled

    def train(self, features_df: pd.DataFrame):
        """Train Isolation Forest model"""

        from sklearn.ensemble import IsolationForest

        print("Đang train Isolation Forest...")

        # Prepare data
        X = self._prepare_data(features_df)

        # Train model
        self.model = IsolationForest(
            contamination=self.config['contamination'],
            n_estimators=self.config['n_estimators'],
            random_state=self.config['random_state'],
            n_jobs=-1
        )

        self.model.fit(X)
        print(f"  Isolation Forest trained với {len(self.feature_columns)} features")

    def detect(self, features_df: pd.DataFrame, train: bool = True) -> pd.DataFrame:
        """
        Phát hiện anomaly

        Returns:
            DataFrame với columns: 'if_anomaly', 'if_score'
        """

        if train or self.model is None:
            self.train(features_df)

        # Prepare data
        X = self._prepare_data(features_df)

        # Predict
        predictions = self.model.predict(X)  # -1 for anomaly, 1 for normal
        scores = self.model.score_samples(X)  # Anomaly score (lower = more anomalous)

        # Convert to our format
        result = features_df.copy()
        result['if_anomaly'] = (predictions == -1).astype(int)

        # Normalize scores to 0-1 (higher = more anomalous)
        # Scores thường âm, nên ta scale
        score_min = scores.min()
        score_max = scores.max()
        if score_max > score_min:
            normalized_scores = 1 - (scores - score_min) / (score_max - score_min)
        else:
            normalized_scores = np.zeros_like(scores)

        result['if_score'] = normalized_scores

        return result

    def save_model(self, path: str):
        """Lưu model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'config': self.config
            }, f)

    def load_model(self, path: str):
        """Load model"""
        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.feature_columns = data['feature_columns']
            self.config = data['config']

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê"""

        total = len(result_df)
        detected = result_df['if_anomaly'].sum()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
        }

        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['if_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['if_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['if_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()

            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            stats.update({
                'true_positives': int(true_positives),
                'false_positives': int(false_positives),
                'false_negatives': int(false_negatives),
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
            })

        return stats


class AutoencoderDetector:
    """
    Anomaly detector sử dụng Autoencoder

    Autoencoder học cách nén và tái tạo dữ liệu normal.
    Anomaly = dữ liệu có reconstruction error cao.
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.model = None
        self.scaler = None
        self.feature_columns = None
        self.threshold = None

    def _default_config(self) -> Dict:
        return {
            'encoding_dim': 8,
            'epochs': 50,
            'batch_size': 32,
            'threshold_percentile': 95,  # Percentile để xác định threshold
        }

    def _prepare_data(self, features_df: pd.DataFrame) -> np.ndarray:
        """Chuẩn bị và normalize data"""

        # Chọn numeric features
        numeric_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()
        exclude_cols = ['is_anomaly', 'rule_anomaly', 'rule_score', 'var_anomaly', 'var_score', 'if_anomaly', 'if_score', 'timestamp']
        feature_cols = [col for col in numeric_cols if col not in exclude_cols]

        self.feature_columns = feature_cols

        data = features_df[feature_cols].fillna(0).values

        # Normalize
        from sklearn.preprocessing import StandardScaler
        if self.scaler is None:
            self.scaler = StandardScaler()
            data_scaled = self.scaler.fit_transform(data)
        else:
            data_scaled = self.scaler.transform(data)

        return data_scaled

    def _build_model(self, input_dim: int):
        """Build autoencoder model"""

        try:
            from tensorflow import keras
            from tensorflow.keras import layers
        except ImportError:
            print("⚠️  TensorFlow chưa được cài đặt. Autoencoder detector không khả dụng.")
            return None

        encoding_dim = self.config['encoding_dim']

        # Encoder
        encoder_input = keras.Input(shape=(input_dim,))
        encoded = layers.Dense(encoding_dim * 2, activation='relu')(encoder_input)
        encoded = layers.Dense(encoding_dim, activation='relu')(encoded)

        # Decoder
        decoded = layers.Dense(encoding_dim * 2, activation='relu')(encoded)
        decoded = layers.Dense(input_dim, activation='linear')(decoded)

        # Autoencoder
        autoencoder = keras.Model(encoder_input, decoded)
        autoencoder.compile(optimizer='adam', loss='mse')

        return autoencoder

    def train(self, features_df: pd.DataFrame):
        """Train Autoencoder"""

        print("Đang train Autoencoder...")

        # Prepare data
        X = self._prepare_data(features_df)

        # Build model
        self.model = self._build_model(X.shape[1])

        if self.model is None:
            return

        # Train (chỉ train trên normal data nếu có label)
        if 'is_anomaly' in features_df.columns:
            X_normal = X[~features_df['is_anomaly'].values]
        else:
            X_normal = X

        # Train
        self.model.fit(
            X_normal, X_normal,
            epochs=self.config['epochs'],
            batch_size=self.config['batch_size'],
            shuffle=True,
            verbose=0
        )

        # Tính threshold dựa trên reconstruction error của training data
        reconstructions = self.model.predict(X_normal, verbose=0)
        mse = np.mean(np.power(X_normal - reconstructions, 2), axis=1)
        self.threshold = np.percentile(mse, self.config['threshold_percentile'])

        print(f"  Autoencoder trained với {len(self.feature_columns)} features")
        print(f"  Reconstruction error threshold: {self.threshold:.4f}")

    def detect(self, features_df: pd.DataFrame, train: bool = True) -> pd.DataFrame:
        """Phát hiện anomaly"""

        if train or self.model is None:
            self.train(features_df)

        if self.model is None:
            # Fallback: return zeros
            result = features_df.copy()
            result['ae_anomaly'] = 0
            result['ae_score'] = 0.0
            return result

        # Prepare data
        X = self._prepare_data(features_df)

        # Reconstruct
        reconstructions = self.model.predict(X, verbose=0)

        # Calculate reconstruction error
        mse = np.mean(np.power(X - reconstructions, 2), axis=1)

        # Detect anomaly
        result = features_df.copy()
        result['ae_anomaly'] = (mse > self.threshold).astype(int)

        # Normalize scores
        max_mse = mse.max()
        if max_mse > 0:
            result['ae_score'] = np.clip(mse / max_mse, 0, 1)
        else:
            result['ae_score'] = 0.0

        return result

    def save_model(self, path: str):
        """Lưu model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Lưu keras model
        self.model.save(path + '_model.h5')

        # Lưu metadata
        with open(path + '_meta.pkl', 'wb') as f:
            pickle.dump({
                'scaler': self.scaler,
                'feature_columns': self.feature_columns,
                'threshold': self.threshold,
                'config': self.config
            }, f)

    def load_model(self, path: str):
        """Load model"""
        from tensorflow import keras

        # Load keras model
        self.model = keras.models.load_model(path + '_model.h5')

        # Load metadata
        with open(path + '_meta.pkl', 'rb') as f:
            data = pickle.load(f)
            self.scaler = data['scaler']
            self.feature_columns = data['feature_columns']
            self.threshold = data['threshold']
            self.config = data['config']

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê"""

        total = len(result_df)
        detected = result_df['ae_anomaly'].sum()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
        }

        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['ae_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['ae_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['ae_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()

            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

            stats.update({
                'true_positives': int(true_positives),
                'false_positives': int(false_positives),
                'false_negatives': int(false_negatives),
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

    print("=" * 60)
    print("Testing Isolation Forest Detector")
    print("=" * 60)

    # Isolation Forest
    if_detector = IsolationForestDetector()
    if_result = if_detector.detect(features_df, train=True)
    if_stats = if_detector.get_statistics(if_result)

    print("\n=== Isolation Forest Statistics ===")
    for key, value in if_stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    # Save model
    if_detector.save_model('data/models/isolation_forest.pkl')

    print("\n" + "=" * 60)
    print("Testing Autoencoder Detector")
    print("=" * 60)

    # Autoencoder
    ae_detector = AutoencoderDetector()
    ae_result = ae_detector.detect(features_df, train=True)
    ae_stats = ae_detector.get_statistics(ae_result)

    print("\n=== Autoencoder Statistics ===")
    for key, value in ae_stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    # Combine results
    combined = features_df.copy()
    combined['if_anomaly'] = if_result['if_anomaly']
    combined['if_score'] = if_result['if_score']
    combined['ae_anomaly'] = ae_result['ae_anomaly']
    combined['ae_score'] = ae_result['ae_score']

    combined.to_csv('data/processed/ml_results.csv', index=False)
    print("\nKết quả đã lưu vào: data/processed/ml_results.csv")
