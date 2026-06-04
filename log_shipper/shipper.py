"""
Log Shipper - Sends logs from production servers to LogSentry AI API

This script runs on production servers, tails log files,
and sends them to the LogSentry AI API for processing.
"""
import time
import requests
import json
import argparse
from datetime import datetime
from pathlib import Path
import re


class LogShipper:
    """Ship logs to LogSentry AI API"""

    def __init__(self, api_url, api_key, service_name, host_name):
        """
        Initialize log shipper

        Args:
            api_url: LogSentry AI API URL (e.g., http://logsentry.example.com)
            api_key: API key for authentication
            service_name: Name of this service
            host_name: Hostname of this server
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.service_name = service_name
        self.host_name = host_name
        self.batch_size = 100
        self.batch_timeout = 10  # seconds
        self.log_buffer = []
        self.last_send_time = time.time()

    def parse_log_line(self, line):
        """
        Parse log line and extract level, timestamp, message

        Supports common log formats:
        - "2024-10-12 10:30:00 ERROR Database connection failed"
        - "[ERROR] 2024-10-12 10:30:00 - Database connection failed"
        - etc.
        """
        try:
            # Try to match common patterns
            # Pattern 1: timestamp level message
            match = re.match(
                r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\s+(\w+)\s+(.*)',
                line
            )
            if match:
                date, time_str, level, message = match.groups()
                timestamp = f"{date}T{time_str}"
                return {
                    'timestamp': timestamp,
                    'level': level.upper(),
                    'message': message.strip(),
                    'service': self.service_name,
                    'host': self.host_name
                }

            # Pattern 2: [LEVEL] timestamp - message
            match = re.match(
                r'\[(\w+)\]\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-\s+(.*)',
                line
            )
            if match:
                level, timestamp_str, message = match.groups()
                timestamp = timestamp_str.replace(' ', 'T')
                return {
                    'timestamp': timestamp,
                    'level': level.upper(),
                    'message': message.strip(),
                    'service': self.service_name,
                    'host': self.host_name
                }

            # Fallback: treat as INFO level
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'level': 'INFO',
                'message': line.strip(),
                'service': self.service_name,
                'host': self.host_name
            }

        except Exception as e:
            print(f"Error parsing log line: {e}")
            return None

    def send_logs(self, logs):
        """Send batch of logs to API"""
        try:
            url = f"{self.api_url}/api/logs"
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': self.api_key
            }
            data = {'logs': logs}

            response = requests.post(url, json=data, headers=headers, timeout=10)

            if response.status_code == 201:
                result = response.json()
                print(f"✓ Sent {result['saved']} logs")
                return True
            else:
                print(f"✗ Failed to send logs: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            print(f"✗ Error sending logs: {e}")
            return False

    def flush_buffer(self):
        """Flush log buffer to API"""
        if self.log_buffer:
            print(f"Flushing {len(self.log_buffer)} logs...")
            if self.send_logs(self.log_buffer):
                self.log_buffer = []
                self.last_send_time = time.time()

    def tail_file(self, log_file):
        """
        Tail log file and send logs to API

        Args:
            log_file: Path to log file to tail
        """
        print(f"Starting log shipper...")
        print(f"  Log file: {log_file}")
        print(f"  API URL: {self.api_url}")
        print(f"  Service: {self.service_name}")
        print(f"  Host: {self.host_name}")
        print(f"\nTailing log file (Ctrl+C to stop)...\n")

        try:
            with open(log_file, 'r') as f:
                # Seek to end of file
                f.seek(0, 2)

                while True:
                    line = f.readline()

                    if line:
                        # Parse and buffer log
                        log_entry = self.parse_log_line(line)
                        if log_entry:
                            self.log_buffer.append(log_entry)
                            print(f"[{log_entry['level']}] {log_entry['message'][:80]}...")

                        # Send if buffer is full or timeout reached
                        if (len(self.log_buffer) >= self.batch_size or
                            time.time() - self.last_send_time >= self.batch_timeout):
                            self.flush_buffer()
                    else:
                        # No new data, sleep briefly
                        time.sleep(0.1)

                        # Check timeout
                        if (self.log_buffer and
                            time.time() - self.last_send_time >= self.batch_timeout):
                            self.flush_buffer()

        except KeyboardInterrupt:
            print("\n\nShutting down...")
            self.flush_buffer()
            print("Goodbye!")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            self.flush_buffer()


def main():
    parser = argparse.ArgumentParser(description='LogSentry AI Log Shipper')
    parser.add_argument('--api-url', required=True, help='LogSentry AI API URL')
    parser.add_argument('--api-key', required=True, help='API key for authentication')
    parser.add_argument('--log-file', required=True, help='Log file to tail')
    parser.add_argument('--service', default='app', help='Service name')
    parser.add_argument('--host', help='Hostname (default: auto-detect)')

    args = parser.parse_args()

    # Auto-detect hostname if not provided
    if not args.host:
        import socket
        args.host = socket.gethostname()

    # Create shipper
    shipper = LogShipper(
        api_url=args.api_url,
        api_key=args.api_key,
        service_name=args.service,
        host_name=args.host
    )

    # Start tailing
    shipper.tail_file(args.log_file)


if __name__ == '__main__':
    main()
