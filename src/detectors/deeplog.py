"""
DeepLog Detector - LSTM-based Anomaly Detection for Log Sequences

DeepLog sử dụng LSTM để học patterns từ log sequences và
phát hiện anomalies dựa trên unexpected patterns.

Reference:
- Paper: "DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning"
- Uses LSTM to model log sequences
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import pickle
import os
import re
from collections import Counter, defaultdict
import warnings
warnings.filterwarnings('ignore')


class LogParser:
    """
    Parse và tokenize log messages
    """

    def __init__(self):
        self.template_patterns = []
        self.event_id_map = {}
        self.next_event_id = 0

    def _extract_template(self, message: str) -> str:
        """
        Extract log template bằng cách thay thế dynamic content

        Ví dụ:
        "User 123 logged in" -> "User <*> logged in"
        "Connection timeout after 30s" -> "Connection timeout after <*>"
        """
        # Thay thế numbers
        template = re.sub(r'\d+', '<*>', message)

        # Thay thế hex/UUID
        template = re.sub(r'0x[0-9a-fA-F]+', '<*>', template)
        template = re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<*>', template)

        # Thay thế IP addresses
        template = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', '<*>', template)

        # Thay thế file paths
        template = re.sub(r'(/[\w/.-]+)+', '<PATH>', template)
        template = re.sub(r'([A-Z]:\\[\w\\.-]+)+', '<PATH>', template)

        return template

    def parse(self, message: str) -> int:
        """
        Parse log message và trả về event ID

        Args:
            message: Log message

        Returns:
            event_id: Unique ID cho log template
        """
        template = self._extract_template(message)

        # Tìm hoặc tạo event ID
        if template not in self.event_id_map:
            self.event_id_map[template] = self.next_event_id
            self.next_event_id += 1

        return self.event_id_map[template]

    def get_vocab_size(self) -> int:
        """Trả về số lượng unique log templates"""
        return len(self.event_id_map)


class DeepLogDetector:
    """
    DeepLog Detector sử dụng LSTM để học log sequence patterns

    Workflow:
    1. Parse logs thành event IDs (log templates)
    2. Tạo sequences từ event IDs
    3. Train LSTM để predict next event
    4. Detect anomaly nếu prediction confidence thấp
    """

    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        self.model = None
        self.parser = LogParser()
        self.sequence_length = self.config['sequence_length']
        self.vocab_size = None
        self.history_sequences = []  # Lưu sequences gần đây để real-time detection

    def _default_config(self) -> Dict:
        return {
            'sequence_length': 10,  # Độ dài sequence để train
            'embedding_dim': 32,
            'lstm_units': 64,
            'epochs': 20,
            'batch_size': 32,
            'threshold': 0.5,  # Threshold cho prediction probability
            'min_samples': 100,  # Số samples tối thiểu để train
        }

    def _prepare_log_sequences(self, logs_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Chuẩn bị sequences từ logs

        Args:
            logs_df: DataFrame với column 'message'

        Returns:
            X: Input sequences (samples, sequence_length)
            y: Target events (samples,)
        """
        # Parse logs thành event IDs
        event_ids = []
        for message in logs_df['message'].values:
            event_id = self.parser.parse(str(message))
            event_ids.append(event_id)

        # Tạo sequences
        X, y = [], []
        for i in range(len(event_ids) - self.sequence_length):
            sequence = event_ids[i:i + self.sequence_length]
            target = event_ids[i + self.sequence_length]
            X.append(sequence)
            y.append(target)

        return np.array(X), np.array(y)

    def _prepare_features_sequences(self, features_df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Chuẩn bị sequences từ features (fallback nếu không có logs)

        Sử dụng error_count pattern như một proxy cho log sequences
        """
        # Sử dụng error_count và level counts như pseudo-events
        # Quantize features thành discrete events
        pseudo_events = []

        for _, row in features_df.iterrows():
            # Tạo một "event code" từ features
            error_level = min(int(row.get('error_count', 0)), 10)  # 0-10
            warn_level = min(int(row.get('warn_count', 0) / 5), 5)  # 0-5
            cpu_level = min(int(row.get('cpu_avg', 0) / 20), 5)  # 0-5

            # Combine thành một số duy nhất
            event_code = error_level * 100 + warn_level * 10 + cpu_level
            pseudo_events.append(event_code)

        # Tạo sequences
        X, y = [], []
        for i in range(len(pseudo_events) - self.sequence_length):
            sequence = pseudo_events[i:i + self.sequence_length]
            target = pseudo_events[i + self.sequence_length]
            X.append(sequence)
            y.append(target)

        if len(X) == 0:
            return np.array([]), np.array([])

        return np.array(X), np.array(y)

    def _build_model(self, vocab_size: int):
        """Build LSTM model"""
        try:
            from tensorflow import keras
            from tensorflow.keras import layers
            import tensorflow as tf
        except ImportError:
            print("⚠️  TensorFlow chưa được cài đặt. DeepLog detector không khả dụng.")
            return None

        model = keras.Sequential([
            # Embedding layer
            layers.Embedding(
                input_dim=vocab_size,
                output_dim=self.config['embedding_dim'],
                input_length=self.sequence_length
            ),

            # LSTM layers
            layers.LSTM(self.config['lstm_units'], return_sequences=True),
            layers.Dropout(0.2),
            layers.LSTM(self.config['lstm_units']),
            layers.Dropout(0.2),

            # Dense layer
            layers.Dense(vocab_size, activation='softmax')
        ])

        model.compile(
            optimizer='adam',
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )

        return model

    def train(self, features_df: pd.DataFrame, logs_df: Optional[pd.DataFrame] = None):
        """
        Train DeepLog model

        Args:
            features_df: DataFrame với features (dùng nếu không có logs_df)
            logs_df: DataFrame với log messages (preferred)
        """
        print("Đang train DeepLog model...")

        # Chuẩn bị sequences
        if logs_df is not None and 'message' in logs_df.columns:
            X, y = self._prepare_log_sequences(logs_df)
            self.vocab_size = self.parser.get_vocab_size()
            print(f"  Sử dụng {len(logs_df)} logs, vocab_size={self.vocab_size}")
        else:
            X, y = self._prepare_features_sequences(features_df)
            self.vocab_size = int(X.max()) + 1 if len(X) > 0 else 1000
            print(f"  Sử dụng features sequences, vocab_size={self.vocab_size}")

        if len(X) < self.config['min_samples']:
            print(f"  ⚠️  Không đủ data để train ({len(X)} < {self.config['min_samples']})")
            print(f"  Sẽ sử dụng baseline detection")
            self.model = None
            return

        # Build model
        self.model = self._build_model(self.vocab_size)

        if self.model is None:
            return

        # Train model
        try:
            self.model.fit(
                X, y,
                epochs=self.config['epochs'],
                batch_size=self.config['batch_size'],
                validation_split=0.2,
                verbose=0
            )
            print(f"  DeepLog trained với {len(X)} sequences")
        except Exception as e:
            print(f"  ⚠️  Lỗi khi train DeepLog: {e}")
            self.model = None

    def _predict_sequence(self, sequence: np.ndarray) -> Tuple[int, float]:
        """
        Predict next event và confidence

        Returns:
            predicted_event, confidence
        """
        if self.model is None:
            return 0, 0.0

        # Ensure sequence is in correct shape
        if len(sequence.shape) == 1:
            sequence = sequence.reshape(1, -1)

        # Predict
        probs = self.model.predict(sequence, verbose=0)[0]
        predicted_event = np.argmax(probs)
        confidence = probs[predicted_event]

        return predicted_event, float(confidence)

    def detect(self, features_df: pd.DataFrame, logs_df: Optional[pd.DataFrame] = None,
               train: bool = True) -> pd.DataFrame:
        """
        Phát hiện anomaly sử dụng DeepLog

        Args:
            features_df: DataFrame với features
            logs_df: DataFrame với logs (optional)
            train: Có train model không

        Returns:
            DataFrame với columns: 'deeplog_anomaly', 'deeplog_score'
        """
        if train or self.model is None:
            self.train(features_df, logs_df)

        result = features_df.copy()
        result['deeplog_anomaly'] = 0
        result['deeplog_score'] = 0.0

        # Nếu không có model, return zeros
        if self.model is None:
            return result

        # Prepare sequences
        if logs_df is not None and 'message' in logs_df.columns:
            X, _ = self._prepare_log_sequences(logs_df)
        else:
            X, _ = self._prepare_features_sequences(features_df)

        if len(X) == 0:
            return result

        # Detect anomalies
        for i in range(len(X)):
            sequence = X[i]

            # Predict
            _, confidence = self._predict_sequence(sequence)

            # Anomaly nếu confidence thấp
            is_anomaly = confidence < self.config['threshold']
            anomaly_score = 1.0 - confidence  # Lower confidence = higher anomaly score

            # Map index to result dataframe
            result_idx = i + self.sequence_length
            if result_idx < len(result):
                result.at[result_idx, 'deeplog_anomaly'] = int(is_anomaly)
                result.at[result_idx, 'deeplog_score'] = anomaly_score

        return result

    def save_model(self, path: str):
        """Lưu model"""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if self.model is not None:
            # Lưu keras model
            self.model.save(path + '_model.h5')

        # Lưu metadata
        with open(path + '_meta.pkl', 'wb') as f:
            pickle.dump({
                'parser': self.parser,
                'vocab_size': self.vocab_size,
                'config': self.config,
                'sequence_length': self.sequence_length
            }, f)

    def load_model(self, path: str):
        """Load model"""
        try:
            from tensorflow import keras

            # Load metadata first
            with open(path + '_meta.pkl', 'rb') as f:
                data = pickle.load(f)
                self.parser = data['parser']
                self.vocab_size = data['vocab_size']
                self.config = data['config']
                self.sequence_length = data['sequence_length']

            # Load keras model with custom objects
            if os.path.exists(path + '_model.h5'):
                try:
                    self.model = keras.models.load_model(
                        path + '_model.h5',
                        compile=False  # Don't compile, we'll do it manually
                    )
                    # Re-compile model
                    self.model.compile(
                        optimizer='adam',
                        loss='sparse_categorical_crossentropy',
                        metrics=['accuracy']
                    )
                except Exception as e:
                    print(f"⚠️  Không thể load DeepLog model: {e}")
                    print(f"    Sẽ cần re-train model. Chạy: python train_all_models.py")
                    self.model = None
            else:
                self.model = None

        except Exception as e:
            print(f"⚠️  Lỗi khi load DeepLog metadata: {e}")
            self.model = None

    def get_statistics(self, result_df: pd.DataFrame) -> Dict:
        """Lấy thống kê"""
        total = len(result_df)
        detected = result_df['deeplog_anomaly'].sum()

        stats = {
            'total_windows': total,
            'anomalies_detected': int(detected),
            'anomaly_rate': detected / total if total > 0 else 0,
        }

        if 'is_anomaly' in result_df.columns:
            true_positives = ((result_df['deeplog_anomaly'] == 1) & (result_df['is_anomaly'] == True)).sum()
            false_positives = ((result_df['deeplog_anomaly'] == 1) & (result_df['is_anomaly'] == False)).sum()
            false_negatives = ((result_df['deeplog_anomaly'] == 0) & (result_df['is_anomaly'] == True)).sum()

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

    # Try to load logs
    try:
        from app.models import LogEntry
        from app import create_app, db

        app = create_app()
        with app.app_context():
            logs = LogEntry.query.order_by(LogEntry.timestamp).all()
            logs_df = pd.DataFrame([{
                'timestamp': log.timestamp,
                'message': log.message,
                'level': log.level
            } for log in logs])

        print(f"Loaded {len(logs_df)} logs from database")
    except:
        logs_df = None
        print("Không thể load logs, sử dụng features")

    print("=" * 60)
    print("Testing DeepLog Detector")
    print("=" * 60)

    # DeepLog
    deeplog_detector = DeepLogDetector()
    deeplog_result = deeplog_detector.detect(features_df, logs_df, train=True)
    deeplog_stats = deeplog_detector.get_statistics(deeplog_result)

    print("\n=== DeepLog Statistics ===")
    for key, value in deeplog_stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.4f}")
        else:
            print(f"{key}: {value}")

    # Save model
    deeplog_detector.save_model('data/models/deeplog')
    print("\nModel đã lưu vào: data/models/deeplog")

    # Save results
    deeplog_result.to_csv('data/processed/deeplog_results.csv', index=False)
    print("Kết quả đã lưu vào: data/processed/deeplog_results.csv")
