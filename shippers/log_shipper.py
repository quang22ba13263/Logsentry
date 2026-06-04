"""
LogSentry AI - Log Shipper
Đọc logs từ file và gửi real-time tới LogSentry API

Cài đặt trên production server:
    pip install requests watchdog

Sử dụng:
    python log_shipper.py --log-file /var/log/application.log \
                          --api-url http://logsentry-server:5000 \
                          --api-key your-api-key \
                          --service my-app \
                          --host server-01
"""
import argparse
import re
import requests
import time
from datetime import datetime
from pathlib import Path
import socket
import json


class LogShipper:
    """Ship logs từ file tới LogSentry API"""

    def __init__(self, api_url, api_key, service, host=None):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.service = service
        self.host = host or socket.gethostname()
        self.batch = []
        self.batch_size = 100
        self.batch_interval = 5  # seconds

        # Log patterns
        self.patterns = {
            # Python logging format
            'python': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - '
                r'(?P<level>\w+) - (?P<message>.*)'
            ),
            # Common log format (Apache/Nginx)
            'common': re.compile(
                r'(?P<ip>[\d.]+) - - \[(?P<timestamp>[^\]]+)\] '
                r'"(?P<method>\w+) (?P<path>[^"]*)" (?P<status>\d+) (?P<size>\d+)'
            ),
            # Syslog format
            'syslog': re.compile(
                r'(?P<month>\w+)\s+(?P<day>\d+) (?P<time>\d{2}:\d{2}:\d{2}) '
                r'(?P<hostname>\S+) (?P<program>\S+): (?P<message>.*)'
            ),
            # Generic: Any line with timestamp
            'generic': re.compile(
                r'(?P<timestamp>\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2})'
            )
        }

    def parse_log_line(self, line):
        """Parse một dòng log và trả về dict"""
        line = line.strip()
        if not line:
            return None

        # Try each pattern
        for pattern_name, pattern in self.patterns.items():
            match = pattern.search(line)
            if match:
                data = match.groupdict()

                # Convert to standard format
                log_entry = {
                    'timestamp': self._parse_timestamp(data.get('timestamp')),
                    'level': self._extract_level(line, data),
                    'message': data.get('message', line),
                    'service': self.service,
                    'host': self.host
                }

                return log_entry

        # Fallback: treat as INFO log
        return {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'message': line,
            'service': self.service,
            'host': self.host
        }

    def _parse_timestamp(self, ts_str):
        """Parse timestamp string"""
        if not ts_str:
            return datetime.now().isoformat()

        # Try common formats
        formats = [
            '%Y-%m-%d %H:%M:%S,%f',  # Python logging
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%dT%H:%M:%S',
            '%d/%b/%Y:%H:%M:%S',     # Apache
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(ts_str[:19], fmt[:19])
                return dt.isoformat()
            except ValueError:
                continue

        return datetime.now().isoformat()

    def _extract_level(self, line, data):
        """Extract log level"""
        if 'level' in data:
            return data['level'].upper()

        # Check for keywords in message
        line_upper = line.upper()
        for level in ['ERROR', 'FATAL', 'CRITICAL']:
            if level in line_upper:
                return 'ERROR'
        for level in ['WARN', 'WARNING']:
            if level in line_upper:
                return 'WARN'

        # Check HTTP status codes
        if 'status' in data:
            status = int(data['status'])
            if status >= 500:
                return 'ERROR'
            elif status >= 400:
                return 'WARN'

        return 'INFO'

    def add_to_batch(self, log_entry):
        """Thêm log vào batch"""
        if log_entry:
            self.batch.append(log_entry)

            if len(self.batch) >= self.batch_size:
                self.flush_batch()

    def flush_batch(self):
        """Gửi batch lên server"""
        if not self.batch:
            return

        try:
            response = requests.post(
                f"{self.api_url}/api/logs",
                json={'logs': self.batch},
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key
                },
                timeout=10
            )

            if response.status_code == 201:
                result = response.json()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Sent {result['saved']} logs")
                self.batch = []
            else:
                print(f"[ERROR] Failed to send logs: {response.status_code}")

        except Exception as e:
            print(f"[ERROR] Failed to send batch: {e}")

    def tail_file(self, file_path, start_from_end=True):
        """
        Đọc file và gửi logs real-time (như tail -f)

        Args:
            file_path: Path to log file
            start_from_end: If True, start from end of file (chỉ đọc logs mới)
        """
        print(f"[INFO] Starting log shipper...")
        print(f"  File: {file_path}")
        print(f"  API: {self.api_url}")
        print(f"  Service: {self.service}")
        print(f"  Host: {self.host}")
        print()

        file_path = Path(file_path)

        if not file_path.exists():
            print(f"[ERROR] File not found: {file_path}")
            return

        last_flush = time.time()

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Start from end if requested
            if start_from_end:
                f.seek(0, 2)  # Seek to end
                print("[INFO] Starting from end of file (only new logs)")

            print("[INFO] Watching for new logs... (Ctrl+C to stop)")
            print("-" * 60)

            while True:
                line = f.readline()

                if line:
                    # Process log line
                    log_entry = self.parse_log_line(line)
                    self.add_to_batch(log_entry)
                else:
                    # No new line, sleep and check for batch flush
                    time.sleep(0.1)

                    # Flush batch if interval exceeded
                    if time.time() - last_flush >= self.batch_interval:
                        self.flush_batch()
                        last_flush = time.time()


def main():
    parser = argparse.ArgumentParser(
        description='LogSentry AI - Log Shipper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Tail application logs
  python log_shipper.py --log-file /var/log/app.log --service my-app

  # Start from beginning of file
  python log_shipper.py --log-file app.log --service my-app --from-beginning

  # Custom API endpoint
  python log_shipper.py --log-file app.log \\
      --api-url http://192.168.1.100:5000 \\
      --api-key my-secret-key \\
      --service web-api \\
      --host prod-server-01
        """
    )

    parser.add_argument('--log-file', required=True,
                       help='Path to log file to tail')
    parser.add_argument('--api-url', default='http://localhost:5000',
                       help='LogSentry API URL (default: http://localhost:5000)')
    parser.add_argument('--api-key', default='logsentry-api-key-change-in-production',
                       help='API key for authentication')
    parser.add_argument('--service', required=True,
                       help='Service name (e.g., api-server, web-app)')
    parser.add_argument('--host', default=None,
                       help='Host name (default: auto-detect)')
    parser.add_argument('--from-beginning', action='store_true',
                       help='Start from beginning of file (default: from end)')

    args = parser.parse_args()

    shipper = LogShipper(
        api_url=args.api_url,
        api_key=args.api_key,
        service=args.service,
        host=args.host
    )

    try:
        shipper.tail_file(args.log_file, start_from_end=not args.from_beginning)
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopping log shipper...")
        shipper.flush_batch()
        print("[INFO] Goodbye!")


if __name__ == '__main__':
    main()
