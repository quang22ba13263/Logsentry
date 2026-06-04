"""
Send test logs and metrics to LogSentry - Real-time data generator
Generates data with current timestamps for testing dashboard
"""
import requests
import time
import random
from datetime import datetime, timedelta
import socket

# Configuration
API_URL = "http://127.0.0.1:5000"
API_KEY = "logsentry-api-key-change-in-production"  # From .env
HOST = socket.gethostname()
SERVICE = "test-app"

def send_logs(count=10, error_probability=0.1):
    """Send test logs to LogSentry"""
    logs = []

    for i in range(count):
        # Random log level based on probability
        if random.random() < error_probability:
            level = "ERROR"
            messages = [
                "Database connection timeout",
                "Failed to process request",
                "Authentication failed",
                "Resource not found",
                "Internal server error"
            ]
        elif random.random() < 0.3:
            level = "WARN"
            messages = [
                "Slow query detected",
                "High memory usage warning",
                "Deprecated API called",
                "Rate limit approaching"
            ]
        else:
            level = "INFO"
            messages = [
                "Request processed successfully",
                "User logged in",
                "Cache hit",
                "Task completed",
                "Service healthy"
            ]

        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": random.choice(messages),
            "service": SERVICE,
            "host": HOST
        }
        logs.append(log_entry)

    try:
        response = requests.post(
            f"{API_URL}/api/logs",
            json={"logs": logs},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )

        if response.status_code in [200, 201]:
            print(f"✓ Sent {len(logs)} logs")
            return True
        else:
            print(f"✗ Failed to send logs: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error sending logs: {e}")
        return False


def send_metrics(cpu_spike=False, mem_spike=False):
    """Send test metrics to LogSentry"""
    # Normal ranges
    cpu = random.uniform(20, 60)
    memory = random.uniform(40, 70)

    # Simulate anomalies
    if cpu_spike:
        cpu = random.uniform(85, 95)
    if mem_spike:
        memory = random.uniform(88, 96)

    metric = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "host": HOST,
        "cpu": round(cpu, 2),
        "memory": round(memory, 2),
        "disk_io": round(random.uniform(50, 150), 2),
        "network_in": round(random.uniform(1000, 5000), 2),
        "network_out": round(random.uniform(500, 2000), 2)
    }

    try:
        response = requests.post(
            f"{API_URL}/api/metrics",
            json={"metrics": [metric]},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )

        if response.status_code in [200, 201]:
            print(f"✓ Sent metric: CPU={metric['cpu']}%, MEM={metric['memory']}%")
            return True
        else:
            print(f"✗ Failed to send metrics: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error sending metrics: {e}")
        return False


def run_normal_mode(duration_minutes=10, interval_seconds=30):
    """
    Run continuous data generation in normal mode

    Args:
        duration_minutes: How long to run (0 = infinite)
        interval_seconds: Interval between sends
    """
    print("=" * 70)
    print("LOGSENTRY TEST DATA GENERATOR - NORMAL MODE")
    print("=" * 70)
    print(f"API URL: {API_URL}")
    print(f"Interval: {interval_seconds} seconds")
    print(f"Duration: {'Infinite' if duration_minutes == 0 else f'{duration_minutes} minutes'}")
    print("=" * 70)
    print("\nGenerating normal traffic...")
    print("Press Ctrl+C to stop\n")

    start_time = datetime.now()
    iteration = 0

    try:
        while True:
            iteration += 1
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Iteration {iteration}")

            # Send logs (10% error rate)
            send_logs(count=random.randint(5, 15), error_probability=0.1)

            # Send metrics (normal)
            send_metrics(cpu_spike=False, mem_spike=False)

            # Check duration
            if duration_minutes > 0:
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                if elapsed >= duration_minutes:
                    print(f"\n✓ Completed {duration_minutes} minutes of data generation")
                    break

            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\nStopped by user")
        elapsed = (datetime.now() - start_time).total_seconds() / 60
        print(f"Generated data for {elapsed:.1f} minutes ({iteration} iterations)")


def run_anomaly_mode():
    """Generate anomalous data to trigger alerts"""
    print("=" * 70)
    print("LOGSENTRY TEST DATA GENERATOR - ANOMALY MODE")
    print("=" * 70)
    print("Generating anomalous traffic to trigger alerts...\n")

    # Scenario 1: Error burst
    print("[Scenario 1] Error burst...")
    for i in range(3):
        send_logs(count=20, error_probability=0.6)  # 60% errors!
        send_metrics(cpu_spike=False, mem_spike=False)
        time.sleep(2)

    print("\nWaiting 30 seconds...\n")
    time.sleep(30)

    # Scenario 2: CPU spike
    print("[Scenario 2] CPU spike...")
    for i in range(3):
        send_logs(count=10, error_probability=0.2)
        send_metrics(cpu_spike=True, mem_spike=False)
        time.sleep(2)

    print("\nWaiting 30 seconds...\n")
    time.sleep(30)

    # Scenario 3: Combined anomaly (errors + high CPU + high memory)
    print("[Scenario 3] Combined anomaly (errors + CPU + memory)...")
    for i in range(3):
        send_logs(count=25, error_probability=0.7)
        send_metrics(cpu_spike=True, mem_spike=True)
        time.sleep(2)

    print("\n" + "=" * 70)
    print("✓ Anomaly scenarios completed!")
    print("=" * 70)
    print("\nCheck your dashboard:")
    print(f"  - Main page: {API_URL}/")
    print(f"  - Alerts: {API_URL}/alerts")
    print(f"  - Metrics: {API_URL}/metrics")
    print("\nNote: Alerts will appear after the next 5-minute window is processed")
    print("      (Background worker processes windows every minute)")


def check_connection():
    """Check if LogSentry server is reachable"""
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code in [200, 302]:  # 302 = redirect to login
            print("✓ LogSentry server is reachable")
            return True
        else:
            print(f"⚠ Unexpected status code: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot connect to LogSentry server: {e}")
        print(f"\nMake sure the server is running:")
        print(f"  python run.py")
        return False


if __name__ == "__main__":
    import sys

    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "LOGSENTRY TEST DATA GENERATOR" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    # Check connection first
    if not check_connection():
        sys.exit(1)

    print("\nSelect mode:")
    print("  1. Normal mode - Continuous data generation")
    print("  2. Anomaly mode - Generate anomalies to test detection")
    print("  3. Quick test - Send one batch and exit")

    try:
        choice = input("\nEnter choice (1/2/3): ").strip()

        if choice == "1":
            duration = input("Duration in minutes (0 for infinite): ").strip()
            duration = int(duration) if duration else 10

            interval = input("Interval in seconds (default 30): ").strip()
            interval = int(interval) if interval else 30

            run_normal_mode(duration_minutes=duration, interval_seconds=interval)

        elif choice == "2":
            confirm = input("\nThis will generate anomalous data. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                run_anomaly_mode()
            else:
                print("Cancelled")

        elif choice == "3":
            print("\nSending test batch...")
            send_logs(count=10, error_probability=0.1)
            send_metrics()
            print("\n✓ Test batch sent successfully")
            print("\nTo see data on dashboard, wait for next processing cycle (up to 5 minutes)")

        else:
            print("Invalid choice")

    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\nError: {e}")
