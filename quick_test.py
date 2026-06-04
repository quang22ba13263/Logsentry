"""
Quick test - Send data and verify dashboard
"""
import requests
import time
from datetime import datetime
import random
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://127.0.0.1:5000"
API_KEY = "logsentry-api-key-change-in-production"

print("=" * 70)
print("QUICK TEST - LogSentry Data Generation")
print("=" * 70)

# Step 1: Send logs
print("\n[Step 1] Sending 20 test logs...")
logs = []
for i in range(20):
    level = random.choice(['INFO'] * 7 + ['WARN'] * 2 + ['ERROR'])
    logs.append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "message": f"Test message {i+1}",
        "service": "test-service",
        "host": "test-host"
    })

try:
    response = requests.post(
        f"{API_URL}/api/logs",
        json={"logs": logs},
        headers={"X-API-Key": API_KEY},
        timeout=5
    )
    if response.status_code in [200, 201]:
        print(f"[OK] Sent {len(logs)} logs successfully")
    else:
        print(f"[ERROR] Failed: {response.status_code} - {response.text}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] {e}")
    print("\nMake sure Flask server is running: python run.py")
    sys.exit(1)

# Step 2: Send metrics
print("\n[Step 2] Sending 5 test metrics...")
for i in range(5):
    metric = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "host": "test-host",
        "cpu": round(random.uniform(30, 70), 2),
        "memory": round(random.uniform(40, 75), 2),
        "disk_io": round(random.uniform(50, 150), 2),
        "network_in": round(random.uniform(1000, 5000), 2),
        "network_out": round(random.uniform(500, 2000), 2)
    }

    response = requests.post(
        f"{API_URL}/api/metrics",
        json={"metrics": [metric]},
        headers={"X-API-Key": API_KEY},
        timeout=5
    )

    if response.status_code in [200, 201]:
        print(f"  [OK] Metric {i+1}/5 sent (CPU: {metric['cpu']}%, MEM: {metric['memory']}%)")
    else:
        print(f"  [ERROR] Failed to send metric {i+1}")

    time.sleep(1)

# Step 3: Check database
print("\n[Step 3] Checking database...")
try:
    import sqlite3
    from datetime import timedelta

    conn = sqlite3.connect('data/logsentry.db')
    cur = conn.cursor()

    recent_logs = cur.execute(
        'SELECT COUNT(*) FROM log_entries WHERE timestamp >= datetime("now", "-10 minutes")'
    ).fetchone()[0]

    recent_metrics = cur.execute(
        'SELECT COUNT(*) FROM metric_entries WHERE timestamp >= datetime("now", "-10 minutes")'
    ).fetchone()[0]

    print(f"  Logs in last 10 min: {recent_logs}")
    print(f"  Metrics in last 10 min: {recent_metrics}")

    conn.close()

except Exception as e:
    print(f"  [ERROR] {e}")

# Step 4: Wait for processing
print("\n[Step 4] Waiting for background worker...")
print("  The worker processes data every 5 minutes.")
print("  Current time:", datetime.now().strftime('%H:%M:%S'))
print("\n  Waiting 2 minutes before checking...")

for i in range(12):
    time.sleep(10)
    dots = "." * ((i % 3) + 1)
    print(f"  Waiting{dots}   ", end='\r')

# Step 5: Check features
print("\n\n[Step 5] Checking if features were created...")
try:
    conn = sqlite3.connect('data/logsentry.db')
    cur = conn.cursor()

    recent_features = cur.execute(
        'SELECT COUNT(*) FROM features WHERE timestamp >= datetime("now", "-30 minutes")'
    ).fetchone()[0]

    print(f"  Features in last 30 min: {recent_features}")

    if recent_features > 0:
        latest = cur.execute(
            'SELECT timestamp, error_count, cpu_avg, mem_avg FROM features ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
        print(f"\n  Latest feature:")
        print(f"    Time: {latest[0]}")
        print(f"    Errors: {latest[1]}")
        print(f"    CPU: {latest[2]:.2f}%")
        print(f"    Memory: {latest[3]:.2f}%")
        print("\n  [OK] Dashboard should now show data!")
    else:
        print("\n  [WARN] No features yet. Worker might need more time.")
        print("  Wait another 3-4 minutes and check dashboard.")

    conn.close()

except Exception as e:
    print(f"  [ERROR] {e}")

# Summary
print("\n" + "=" * 70)
print("NEXT STEPS")
print("=" * 70)
print("\n1. Open browser: http://127.0.0.1:5000")
print("2. Login: admin / admin123")
print("3. Check Dashboard and Metrics pages")
print("\nIf dashboard is still empty:")
print("  - Wait 5 more minutes (full processing cycle)")
print("  - Run this script again: python quick_test.py")
print("  - Or run continuous mode: python send_test_data.py")
print("\n" + "=" * 70)
