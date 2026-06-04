"""
Metrics Shipper - Collects and sends system metrics to LogSentry AI API

Collects CPU, Memory, Disk I/O, Network metrics from the server
and sends them to LogSentry AI for anomaly detection.
"""
import time
import requests
import psutil
import argparse
from datetime import datetime


class MetricsShipper:
    """Collect and ship system metrics to LogSentry AI API"""

    def __init__(self, api_url, api_key, host_name, interval=60):
        """
        Initialize metrics shipper

        Args:
            api_url: LogSentry AI API URL
            api_key: API key for authentication
            host_name: Hostname of this server
            interval: Collection interval in seconds (default: 60)
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.host_name = host_name
        self.interval = interval
        self.last_net_io = None

    def collect_metrics(self):
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            mem = psutil.virtual_memory()
            mem_percent = mem.percent

            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_io_total = disk_io.read_bytes + disk_io.write_bytes

            # Network I/O
            net_io = psutil.net_io_counters()
            network_in = net_io.bytes_recv
            network_out = net_io.bytes_sent

            # Calculate network rate (bytes/sec since last measurement)
            if self.last_net_io:
                network_in_rate = (network_in - self.last_net_io['recv']) / self.interval
                network_out_rate = (network_out - self.last_net_io['sent']) / self.interval
            else:
                network_in_rate = 0
                network_out_rate = 0

            self.last_net_io = {
                'recv': network_in,
                'sent': network_out
            }

            return {
                'timestamp': datetime.utcnow().isoformat(),
                'host': self.host_name,
                'cpu': round(cpu_percent, 2),
                'memory': round(mem_percent, 2),
                'disk_io': disk_io_total,
                'network_in': round(network_in_rate, 2),
                'network_out': round(network_out_rate, 2)
            }

        except Exception as e:
            print(f"Error collecting metrics: {e}")
            return None

    def send_metrics(self, metrics):
        """Send metrics to API"""
        try:
            url = f"{self.api_url}/api/metrics"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key
            }
            data = {'metrics': [metrics]}

            response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code == 201:
                return True
            else:
                print(f"✗ Failed to send metrics: {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Error sending metrics: {e}")
            return False

    def run(self):
        """Main loop to collect and send metrics"""
        print(f"Starting metrics shipper...")
        print(f"  API URL: {self.api_url}")
        print(f"  Host: {self.host_name}")
        print(f"  Interval: {self.interval}s")
        print(f"\nCollecting metrics (Ctrl+C to stop)...\n")

        try:
            while True:
                # Collect metrics
                metrics = self.collect_metrics()

                if metrics:
                    # Print metrics
                    print(f"[{metrics['timestamp']}] "
                          f"CPU: {metrics['cpu']}% | "
                          f"MEM: {metrics['memory']}% | "
                          f"NET: ↓{metrics['network_in']/1024:.1f}KB/s ↑{metrics['network_out']/1024:.1f}KB/s")

                    # Send to API
                    if self.send_metrics(metrics):
                        print("  ✓ Sent")
                    else:
                        print("  ✗ Failed")

                # Wait for next interval
                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            print("Goodbye!")
        except Exception as e:
            print(f"\n✗ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description='LogSentry AI Metrics Shipper')
    parser.add_argument('--api-url', required=True, help='LogSentry AI API URL')
    parser.add_argument('--api-key', required=True, help='API key for authentication')
    parser.add_argument('--host', help='Hostname (default: auto-detect)')
    parser.add_argument('--interval', type=int, default=60, help='Collection interval in seconds')

    args = parser.parse_args()

    # Auto-detect hostname if not provided
    if not args.host:
        import socket
        args.host = socket.gethostname()

    # Create and run shipper
    shipper = MetricsShipper(
        api_url=args.api_url,
        api_key=args.api_key,
        host_name=args.host,
        interval=args.interval
    )

    shipper.run()


if __name__ == '__main__':
    main()
