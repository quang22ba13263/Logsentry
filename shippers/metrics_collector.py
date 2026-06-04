"""
LogSentry AI - Metrics Collector
Thu thập system metrics và gửi tới LogSentry API

Cài đặt trên production server:
    pip install requests psutil

Sử dụng:
    python metrics_collector.py --api-url http://logsentry-server:5000 \
                                --api-key your-api-key \
                                --interval 60
"""
import argparse
import requests
import time
from datetime import datetime
import socket
import psutil


class MetricsCollector:
    """Thu thập và gửi system metrics"""

    def __init__(self, api_url, api_key, host=None, interval=60):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.host = host or socket.gethostname()
        self.interval = interval
        self.last_net_io = None
        self.last_disk_io = None
        self.last_time = None

    def collect_metrics(self):
        """Thu thập metrics hiện tại"""
        current_time = time.time()

        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory
        mem = psutil.virtual_memory()
        mem_percent = mem.percent

        # Disk I/O
        disk_io = psutil.disk_io_counters()
        if self.last_disk_io and self.last_time:
            time_delta = current_time - self.last_time
            disk_read_rate = (disk_io.read_bytes - self.last_disk_io.read_bytes) / time_delta
            disk_write_rate = (disk_io.write_bytes - self.last_disk_io.write_bytes) / time_delta
            disk_io_rate = int((disk_read_rate + disk_write_rate) / 1024)  # KB/s
        else:
            disk_io_rate = 0

        # Network I/O
        net_io = psutil.net_io_counters()
        if self.last_net_io and self.last_time:
            time_delta = current_time - self.last_time
            net_recv_rate = (net_io.bytes_recv - self.last_net_io.bytes_recv) / time_delta
            net_sent_rate = (net_io.bytes_sent - self.last_net_io.bytes_sent) / time_delta
            network_in = int(net_recv_rate / 1024)  # KB/s
            network_out = int(net_sent_rate / 1024)  # KB/s
        else:
            network_in = 0
            network_out = 0

        # Save for next iteration
        self.last_disk_io = disk_io
        self.last_net_io = net_io
        self.last_time = current_time

        metrics = {
            'timestamp': datetime.now().isoformat(),
            'host': self.host,
            'cpu': round(cpu_percent, 2),
            'memory': round(mem_percent, 2),
            'disk_io': disk_io_rate,
            'network_in': network_in,
            'network_out': network_out
        }

        return metrics

    def collect_detailed_metrics(self):
        """Thu thập metrics chi tiết (optional)"""
        metrics = self.collect_metrics()

        # Add more detailed info
        try:
            # Disk usage
            disk = psutil.disk_usage('/')
            metrics['disk_usage_percent'] = disk.percent

            # CPU per core
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            metrics['cpu_cores'] = len(cpu_per_core)
            metrics['cpu_max'] = max(cpu_per_core)

            # Memory details
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            metrics['memory_available_gb'] = round(mem.available / (1024**3), 2)
            metrics['swap_percent'] = swap.percent

            # Load average (Unix only)
            if hasattr(psutil, 'getloadavg'):
                load_avg = psutil.getloadavg()
                metrics['load_avg_1min'] = round(load_avg[0], 2)
                metrics['load_avg_5min'] = round(load_avg[1], 2)
                metrics['load_avg_15min'] = round(load_avg[2], 2)

        except Exception as e:
            print(f"[WARN] Could not collect detailed metrics: {e}")

        return metrics

    def send_metrics(self, metrics):
        """Gửi metrics lên server"""
        try:
            response = requests.post(
                f"{self.api_url}/api/metrics",
                json={'metrics': [metrics]},
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key
                },
                timeout=10
            )

            if response.status_code == 201:
                result = response.json()
                return True
            else:
                print(f"[ERROR] Failed to send metrics: {response.status_code}")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to send metrics: {e}")
            return False

    def run(self, detailed=False):
        """Chạy collector loop"""
        print(f"[INFO] Starting metrics collector...")
        print(f"  API: {self.api_url}")
        print(f"  Host: {self.host}")
        print(f"  Interval: {self.interval}s")
        print(f"  Detailed: {detailed}")
        print()
        print("[INFO] Collecting metrics... (Ctrl+C to stop)")
        print("-" * 70)

        # Initial collection to set baseline
        self.collect_metrics()
        time.sleep(2)

        while True:
            try:
                # Collect metrics
                if detailed:
                    metrics = self.collect_detailed_metrics()
                else:
                    metrics = self.collect_metrics()

                # Send to server
                if self.send_metrics(metrics):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"CPU: {metrics['cpu']:5.1f}% | "
                          f"MEM: {metrics['memory']:5.1f}% | "
                          f"Disk I/O: {metrics['disk_io']:6d} KB/s | "
                          f"Net In/Out: {metrics['network_in']:5d}/{metrics['network_out']:5d} KB/s")

                # Wait for next interval
                time.sleep(self.interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[ERROR] Collection error: {e}")
                time.sleep(self.interval)


def test_metrics():
    """Test metrics collection locally"""
    collector = MetricsCollector(
        api_url='http://localhost:5000',
        api_key='test'
    )

    print("Testing metrics collection...")
    print("=" * 70)

    # Basic metrics
    print("\nBasic Metrics:")
    metrics = collector.collect_metrics()
    for key, value in metrics.items():
        print(f"  {key:20s}: {value}")

    # Wait a bit
    time.sleep(2)

    # Detailed metrics
    print("\nDetailed Metrics:")
    detailed = collector.collect_detailed_metrics()
    for key, value in detailed.items():
        print(f"  {key:20s}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description='LogSentry AI - Metrics Collector',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Collect metrics every 60 seconds
  python metrics_collector.py

  # Custom interval and API endpoint
  python metrics_collector.py --interval 30 \\
      --api-url http://192.168.1.100:5000 \\
      --api-key my-secret-key

  # Collect detailed metrics
  python metrics_collector.py --detailed

  # Test locally (no API calls)
  python metrics_collector.py --test
        """
    )

    parser.add_argument('--api-url', default='http://localhost:5000',
                       help='LogSentry API URL (default: http://localhost:5000)')
    parser.add_argument('--api-key', default='logsentry-api-key-change-in-production',
                       help='API key for authentication')
    parser.add_argument('--host', default=None,
                       help='Host name (default: auto-detect)')
    parser.add_argument('--interval', type=int, default=60,
                       help='Collection interval in seconds (default: 60)')
    parser.add_argument('--detailed', action='store_true',
                       help='Collect detailed metrics')
    parser.add_argument('--test', action='store_true',
                       help='Test mode (no API calls)')

    args = parser.parse_args()

    if args.test:
        test_metrics()
        return

    collector = MetricsCollector(
        api_url=args.api_url,
        api_key=args.api_key,
        host=args.host,
        interval=args.interval
    )

    try:
        collector.run(detailed=args.detailed)
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopping metrics collector...")
        print("[INFO] Goodbye!")


if __name__ == '__main__':
    main()
