"""
Script để tạo synthetic logs và metrics cho hệ thống phát hiện anomaly
"""
import random
import datetime
import json
from typing import List, Dict
import os


class LogGenerator:
    """Tạo synthetic logs với normal và anomaly patterns"""

    LOG_LEVELS = ['INFO', 'WARN', 'ERROR', 'DEBUG']
    SERVICES = ['api-service', 'db-service', 'cache-service', 'auth-service', 'worker-service']

    NORMAL_MESSAGES = {
        'INFO': [
            'Request processed successfully',
            'User logged in',
            'Cache hit for key',
            'Database query executed',
            'API call completed',
            'Transaction committed',
            'Health check passed',
        ],
        'WARN': [
            'Slow query detected',
            'Cache miss for key',
            'Retry attempt',
            'Deprecated API usage',
        ],
        'ERROR': [
            'Connection timeout',
            'Invalid input parameter',
            'Resource not found',
        ],
        'DEBUG': [
            'Debug trace point',
            'Variable state captured',
        ]
    }

    ANOMALY_MESSAGES = {
        'ERROR': [
            'OutOfMemoryError: Java heap space',
            'Database connection pool exhausted',
            'NullPointerException in handler',
            'Timeout waiting for response',
            'Failed to acquire lock',
            'Disk space critically low',
            'Too many open files',
            'Segmentation fault',
        ],
        'WARN': [
            'High memory pressure detected',
            'Thread pool saturation',
            'Request queue backup',
            'Circuit breaker opened',
        ]
    }

    def __init__(self, start_time: datetime.datetime):
        self.current_time = start_time

    def generate_log_entry(self, is_anomaly: bool = False, anomaly_type: str = None) -> Dict:
        """Tạo một log entry"""

        if is_anomaly and anomaly_type == 'error_spike':
            level = random.choice(['ERROR', 'WARN'])
            if level == 'ERROR':
                message = random.choice(self.ANOMALY_MESSAGES['ERROR'])
            else:
                message = random.choice(self.ANOMALY_MESSAGES['WARN'])
        else:
            # Normal distribution: 70% INFO, 20% DEBUG, 8% WARN, 2% ERROR
            level = random.choices(
                self.LOG_LEVELS,
                weights=[70, 8, 2, 20],
                k=1
            )[0]

            if level in self.NORMAL_MESSAGES:
                message = random.choice(self.NORMAL_MESSAGES[level])
            else:
                message = "Generic message"

        service = random.choice(self.SERVICES)

        log_entry = {
            'timestamp': self.current_time.isoformat(),
            'level': level,
            'service': service,
            'message': message,
            'thread_id': random.randint(1, 50),
        }

        return log_entry

    def generate_system_metrics(self, is_anomaly: bool = False, anomaly_type: str = None) -> Dict:
        """Tạo system metrics"""

        if is_anomaly and anomaly_type == 'resource_spike':
            cpu_avg = random.uniform(80, 99)
            mem_avg = random.uniform(85, 98)
            disk_io = random.uniform(800, 1000)
        else:
            # Normal CPU: 20-50%, Memory: 40-70%
            cpu_avg = random.gauss(35, 10)
            cpu_avg = max(5, min(60, cpu_avg))  # Clamp to 5-60%

            mem_avg = random.gauss(55, 10)
            mem_avg = max(30, min(75, mem_avg))  # Clamp to 30-75%

            disk_io = random.gauss(200, 50)
            disk_io = max(50, min(400, disk_io))

        metrics = {
            'timestamp': self.current_time.isoformat(),
            'cpu_avg': round(cpu_avg, 2),
            'mem_avg': round(mem_avg, 2),
            'disk_io_avg': round(disk_io, 2),
            'network_in': round(random.gauss(500, 100), 2),
            'network_out': round(random.gauss(300, 80), 2),
        }

        return metrics


def generate_dataset(
    output_dir: str,
    num_days: int = 7,
    window_minutes: int = 5,
    logs_per_window: int = 100,
    anomaly_probability: float = 0.05
):
    """
    Tạo dataset với logs và metrics

    Args:
        output_dir: Thư mục output
        num_days: Số ngày data
        window_minutes: Kích thước time window (phút)
        logs_per_window: Số logs mỗi window
        anomaly_probability: Xác suất xuất hiện anomaly
    """

    start_time = datetime.datetime.now() - datetime.timedelta(days=num_days)
    generator = LogGenerator(start_time)

    # Tạo thư mục output
    os.makedirs(f"{output_dir}/raw", exist_ok=True)

    logs = []
    metrics = []

    total_windows = (num_days * 24 * 60) // window_minutes

    print(f"Đang tạo {total_windows} time windows...")

    for window_idx in range(total_windows):
        # Quyết định xem window này có anomaly không
        is_anomaly_window = random.random() < anomaly_probability
        anomaly_type = None

        if is_anomaly_window:
            # Random anomaly type
            anomaly_type = random.choice(['error_spike', 'resource_spike', 'combined'])

        # Tạo logs cho window này
        num_logs = logs_per_window
        if is_anomaly_window and anomaly_type in ['error_spike', 'combined']:
            # Tăng số logs khi có anomaly
            num_logs = int(logs_per_window * random.uniform(2, 5))

        for _ in range(num_logs):
            log_entry = generator.generate_log_entry(
                is_anomaly=is_anomaly_window,
                anomaly_type=anomaly_type
            )
            logs.append(log_entry)

            # Random timestamp trong window
            offset_seconds = random.randint(0, window_minutes * 60 - 1)
            log_entry['timestamp'] = (
                generator.current_time + datetime.timedelta(seconds=offset_seconds)
            ).isoformat()

        # Tạo metrics cho window này
        metrics_entry = generator.generate_system_metrics(
            is_anomaly=is_anomaly_window,
            anomaly_type=anomaly_type
        )
        metrics.append(metrics_entry)

        # Đánh dấu ground truth
        metrics_entry['is_anomaly'] = is_anomaly_window
        metrics_entry['anomaly_type'] = anomaly_type if is_anomaly_window else None

        # Di chuyển tới window tiếp theo
        generator.current_time += datetime.timedelta(minutes=window_minutes)

        if (window_idx + 1) % 500 == 0:
            print(f"  Đã tạo {window_idx + 1}/{total_windows} windows...")

    # Lưu logs
    print(f"\nLưu {len(logs)} log entries...")
    with open(f"{output_dir}/raw/application.log", 'w') as f:
        for log in logs:
            f.write(json.dumps(log) + '\n')

    # Lưu metrics
    print(f"Lưu {len(metrics)} metrics entries...")
    with open(f"{output_dir}/raw/system_metrics.jsonl", 'w') as f:
        for metric in metrics:
            f.write(json.dumps(metric) + '\n')

    print(f"\n✅ Dataset đã được tạo thành công!")
    print(f"   - Logs: {output_dir}/raw/application.log")
    print(f"   - Metrics: {output_dir}/raw/system_metrics.jsonl")
    print(f"   - Tổng số windows: {total_windows}")
    print(f"   - Số anomaly windows: {sum(1 for m in metrics if m['is_anomaly'])}")


if __name__ == '__main__':
    generate_dataset(
        output_dir='data',
        num_days=7,
        window_minutes=5,
        logs_per_window=100,
        anomaly_probability=0.05
    )
