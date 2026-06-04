"""
Test sending logs and metrics with detailed error checking
"""
import requests
import json
from datetime import datetime

API_URL = "http://127.0.0.1:5000"
API_KEY = "logsentry-api-key-change-in-production"

print("=" * 70)
print("TESTING API ENDPOINTS WITH ERROR DETAILS")
print("=" * 70)

# Test 1: Send one log
print("\n[Test 1] Sending ONE log...")
log_data = {
    "logs": [
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "message": "Test error message",
            "service": "test-service",
            "host": "test-host"
        }
    ]
}

print(f"URL: {API_URL}/api/logs")
print(f"Headers: X-API-Key: {API_KEY[:20]}...")
print(f"Data: {json.dumps(log_data, indent=2)}")

try:
    response = requests.post(
        f"{API_URL}/api/logs",
        json=log_data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        },
        timeout=10
    )

    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")

    if response.status_code in [200, 201]:
        print("\n[OK] Log sent successfully")
        result = response.json()
        print(f"Saved: {result.get('saved', 'unknown')}")
    else:
        print(f"\n[ERROR] Failed with status {response.status_code}")

except Exception as e:
    print(f"\n[ERROR] Exception: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Send one metric
print("\n" + "=" * 70)
print("\n[Test 2] Sending ONE metric...")
metric_data = {
    "metrics": [
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "host": "test-host",
            "cpu": 45.5,
            "memory": 60.2,
            "disk_io": 100.0,
            "network_in": 2000.0,
            "network_out": 1000.0
        }
    ]
}

print(f"URL: {API_URL}/api/metrics")
print(f"Data: {json.dumps(metric_data, indent=2)}")

try:
    response = requests.post(
        f"{API_URL}/api/metrics",
        json=metric_data,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        },
        timeout=10
    )

    print(f"\nResponse Status: {response.status_code}")
    print(f"Response Body: {response.text}")

    if response.status_code in [200, 201]:
        print("\n[OK] Metric sent successfully")
        result = response.json()
        print(f"Saved: {result.get('saved', 'unknown')}")
    else:
        print(f"\n[ERROR] Failed with status {response.status_code}")

except Exception as e:
    print(f"\n[ERROR] Exception: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check database immediately
print("\n" + "=" * 70)
print("\n[Test 3] Checking database...")
try:
    import sqlite3
    from datetime import timedelta

    conn = sqlite3.connect('data/logsentry.db')
    cur = conn.cursor()

    now = datetime.utcnow()
    since = (now - timedelta(minutes=5)).isoformat()

    logs = cur.execute(
        'SELECT COUNT(*), MAX(timestamp) FROM log_entries WHERE timestamp >= ?',
        (since,)
    ).fetchone()

    metrics = cur.execute(
        'SELECT COUNT(*), MAX(timestamp) FROM metric_entries WHERE timestamp >= ?',
        (since,)
    ).fetchone()

    print(f"Logs in last 5 min: {logs[0]}")
    if logs[0] > 0:
        print(f"  Latest: {logs[1]}")

        # Get the actual log
        latest_log = cur.execute(
            'SELECT timestamp, level, message FROM log_entries ORDER BY id DESC LIMIT 1'
        ).fetchone()
        print(f"  Content: {latest_log}")

    print(f"\nMetrics in last 5 min: {metrics[0]}")
    if metrics[0] > 0:
        print(f"  Latest: {metrics[1]}")

        # Get the actual metric
        latest_metric = cur.execute(
            'SELECT timestamp, cpu, memory FROM metric_entries ORDER BY id DESC LIMIT 1'
        ).fetchone()
        print(f"  Content: {latest_metric}")

    conn.close()

    if logs[0] > 0 or metrics[0] > 0:
        print("\n[OK] Data is in database!")
    else:
        print("\n[ERROR] Data NOT in database despite successful HTTP response!")
        print("This means the API endpoint is not saving data.")
        print("\nCheck Flask server logs for errors!")

except Exception as e:
    print(f"[ERROR] Database check failed: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print("\nIf data is NOT in database:")
print("1. Check Flask terminal for errors")
print("2. Look for lines like:")
print("   - 'Error receiving logs: ...'")
print("   - 'Error receiving metrics: ...'")
print("3. The API might be working but db.session.commit() failing")
