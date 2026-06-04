"""
SEEDER - Populate LogSentry with test data
Automatically seeds logs and metrics for testing dashboard
"""
import requests
import time
import random
from datetime import datetime, timedelta
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://127.0.0.1:5000"
API_KEY = "logsentry-api-key-change-in-production"

def seed_historical_data(num_windows=30):
    """
    Seed historical data for multiple time windows
    Creates realistic patterns with some anomalies
    """
    print("=" * 70)
    print("SEEDING HISTORICAL DATA")
    print("=" * 70)
    print(f"\nGenerating {num_windows} windows of data...")
    print("Each window = 1 minute of logs + metrics")
    print()

    success_count = 0

    # Start from 2 hours ago
    start_time = datetime.utcnow() - timedelta(hours=2)

    for i in range(num_windows):
        window_time = start_time + timedelta(minutes=i)

        # Determine if this should be anomalous (10% chance)
        is_anomaly = random.random() < 0.1

        # Generate logs for this window
        logs = []
        num_logs = random.randint(15, 30)

        if is_anomaly:
            # Anomaly: high error rate
            error_prob = 0.5
            num_logs = random.randint(30, 50)
            print(f"[{i+1}/{num_windows}] Window {window_time.strftime('%H:%M')} - ANOMALY (High errors)")
        else:
            error_prob = 0.05
            print(f"[{i+1}/{num_windows}] Window {window_time.strftime('%H:%M')} - Normal", end='')

        for j in range(num_logs):
            log_time = window_time + timedelta(seconds=random.randint(0, 59))

            if random.random() < error_prob:
                level = "ERROR"
                message = random.choice([
                    "Database connection timeout",
                    "Failed to process request",
                    "Authentication failed",
                    "Service unavailable",
                    "Internal server error"
                ])
            elif random.random() < 0.2:
                level = "WARN"
                message = random.choice([
                    "Slow query detected",
                    "High memory usage",
                    "Rate limit warning",
                    "Cache miss"
                ])
            else:
                level = "INFO"
                message = random.choice([
                    "Request processed",
                    "User logged in",
                    "Task completed",
                    "Service healthy"
                ])

            logs.append({
                "timestamp": log_time.isoformat() + "Z",
                "level": level,
                "message": message,
                "service": "api-server",
                "host": "prod-server-01"
            })

        # Send logs
        try:
            response = requests.post(
                f"{API_URL}/api/logs",
                json={"logs": logs},
                headers={"X-API-Key": API_KEY},
                timeout=5
            )
            if response.status_code in [200, 201]:
                success_count += 1
            else:
                print(f" [ERROR: {response.status_code}]")
                continue
        except Exception as e:
            print(f" [ERROR: {e}]")
            continue

        # Generate metrics for this window
        metrics = []
        num_metrics = random.randint(5, 10)

        if is_anomaly:
            # Anomaly: high CPU/Memory
            cpu_range = (85, 95)
            mem_range = (88, 96)
        else:
            cpu_range = (20, 65)
            mem_range = (35, 75)

        for k in range(num_metrics):
            metric_time = window_time + timedelta(seconds=random.randint(0, 59))

            metrics.append({
                "timestamp": metric_time.isoformat() + "Z",
                "host": "prod-server-01",
                "cpu": round(random.uniform(*cpu_range), 2),
                "memory": round(random.uniform(*mem_range), 2),
                "disk_io": round(random.uniform(50, 200), 2),
                "network_in": round(random.uniform(1000, 5000), 2),
                "network_out": round(random.uniform(500, 2500), 2)
            })

        # Send metrics
        try:
            response = requests.post(
                f"{API_URL}/api/metrics",
                json={"metrics": metrics},
                headers={"X-API-Key": API_KEY},
                timeout=5
            )
            if response.status_code in [200, 201]:
                print(" [OK]")
            else:
                print(f" [ERROR: {response.status_code}]")
        except Exception as e:
            print(f" [ERROR: {e}]")

        # Small delay to avoid overwhelming the server
        time.sleep(0.1)

    print(f"\n[OK] Seeded {success_count}/{num_windows} windows successfully")
    return success_count > 0


def seed_recent_data():
    """Seed data for the last few minutes (will be processed soon)"""
    print("\n" + "=" * 70)
    print("SEEDING RECENT DATA (for immediate processing)")
    print("=" * 70)

    # Last 3 minutes
    for i in range(3):
        window_time = datetime.utcnow() - timedelta(minutes=2-i)

        print(f"\n[Window {i+1}/3] Time: {window_time.strftime('%H:%M')}")

        # Logs
        logs = []
        for j in range(20):
            log_time = window_time + timedelta(seconds=random.randint(0, 59))
            logs.append({
                "timestamp": log_time.isoformat() + "Z",
                "level": random.choice(['INFO'] * 8 + ['WARN'] * 1 + ['ERROR'] * 1),
                "message": f"Test message {j+1}",
                "service": "api-server",
                "host": "prod-server-01"
            })

        response = requests.post(
            f"{API_URL}/api/logs",
            json={"logs": logs},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
        print(f"  Logs: {response.status_code} - {len(logs)} sent")

        # Metrics
        metrics = []
        for k in range(5):
            metric_time = window_time + timedelta(seconds=random.randint(0, 59))
            metrics.append({
                "timestamp": metric_time.isoformat() + "Z",
                "host": "prod-server-01",
                "cpu": round(random.uniform(30, 70), 2),
                "memory": round(random.uniform(40, 75), 2),
                "disk_io": round(random.uniform(50, 150), 2),
                "network_in": round(random.uniform(1000, 4000), 2),
                "network_out": round(random.uniform(500, 2000), 2)
            })

        response = requests.post(
            f"{API_URL}/api/metrics",
            json={"metrics": metrics},
            headers={"X-API-Key": API_KEY},
            timeout=5
        )
        print(f"  Metrics: {response.status_code} - {len(metrics)} sent")


def check_results():
    """Check what was seeded"""
    print("\n" + "=" * 70)
    print("CHECKING RESULTS")
    print("=" * 70)

    try:
        import sqlite3
        conn = sqlite3.connect('data/logsentry.db')
        cur = conn.cursor()

        # Recent data (last 3 hours)
        since_3h = (datetime.utcnow() - timedelta(hours=3)).isoformat()

        logs = cur.execute(
            'SELECT COUNT(*) FROM log_entries WHERE timestamp >= ?',
            (since_3h,)
        ).fetchone()[0]

        metrics = cur.execute(
            'SELECT COUNT(*) FROM metric_entries WHERE timestamp >= ?',
            (since_3h,)
        ).fetchone()[0]

        features = cur.execute(
            'SELECT COUNT(*) FROM features WHERE timestamp >= ?',
            (since_3h,)
        ).fetchone()[0]

        alerts = cur.execute(
            'SELECT COUNT(*) FROM alerts WHERE timestamp >= ?',
            (since_3h,)
        ).fetchone()[0]

        print(f"\nData in last 3 hours:")
        print(f"  Logs:     {logs}")
        print(f"  Metrics:  {metrics}")
        print(f"  Features: {features}")
        print(f"  Alerts:   {alerts}")

        if features > 0:
            print("\n[OK] Features are being created - Worker is processing!")

            latest = cur.execute(
                'SELECT timestamp, error_count, cpu_avg, mem_avg FROM features ORDER BY timestamp DESC LIMIT 1'
            ).fetchone()
            print(f"\nLatest feature:")
            print(f"  Time: {latest[0]}")
            print(f"  Errors: {latest[1]}")
            print(f"  CPU: {latest[2]:.1f}%")
            print(f"  Memory: {latest[3]:.1f}%")
        else:
            print("\n[WARN] No features yet - Worker needs time to process")
            print("       Wait 1-2 minutes and check dashboard")

        conn.close()

    except Exception as e:
        print(f"[ERROR] {e}")


def main():
    print("\n")
    print("+" + "=" * 68 + "+")
    print("|" + " " * 24 + "LOGSENTRY SEEDER" + " " * 28 + "|")
    print("+" + "=" * 68 + "+")
    print()

    # Check if server is running
    print("Checking server...")
    try:
        response = requests.get(f"{API_URL}/", timeout=5)
        if response.status_code in [200, 302]:
            print("[OK] Server is running\n")
        else:
            print(f"[WARN] Unexpected status: {response.status_code}\n")
    except Exception as e:
        print(f"[ERROR] Cannot connect to server: {e}")
        print("\nMake sure Flask is running:")
        print("  python run.py\n")
        return

    # Seed historical data
    if not seed_historical_data(num_windows=30):
        print("[ERROR] Failed to seed historical data")
        return

    # Seed recent data
    seed_recent_data()

    print("\n" + "=" * 70)
    print("WAITING FOR PROCESSING")
    print("=" * 70)
    print("\nWorker processes windows every 10 seconds...")
    print("Wait 1-2 minutes for features to be created...\n")

    for i in range(12):
        time.sleep(10)
        dots = "." * ((i % 3) + 1)
        print(f"Waiting{dots}   [{i+1}/12]", end='\r')

    # Check results
    check_results()

    # Final instructions
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("\n1. Open browser: http://127.0.0.1:5000")
    print("2. Login: admin / admin123")
    print("3. Check pages:")
    print("   - Dashboard: Should show graphs")
    print("   - Metrics: Should have data")
    print("   - Alerts: May have some alerts (if anomalies detected)")
    print("\n4. Dashboard auto-refreshes every 10 seconds")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[CANCELLED] Seeding stopped by user")
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
