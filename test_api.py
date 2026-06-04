"""
Test LogSentry API endpoints
"""
import requests
import json
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://127.0.0.1:5000"

print("=" * 70)
print("TESTING LOGSENTRY API")
print("=" * 70)

# Test 1: Server is running
print("\n[Test 1] Checking if server is running...")
try:
    response = requests.get(f"{API_URL}/", timeout=5)
    if response.status_code in [200, 302, 401]:
        print(f"[OK] Server is UP (status: {response.status_code})")
    else:
        print(f"[WARN] Unexpected status: {response.status_code}")
except Exception as e:
    print(f"[ERROR] Server is DOWN: {e}")
    exit(1)

# Test 2: Get metrics (no auth required for GET)
print("\n[Test 2] GET /api/metrics")
try:
    response = requests.get(f"{API_URL}/api/metrics?limit=10", timeout=5)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"[OK] Got {data.get('count', 0)} metrics")
        if data.get('count', 0) > 0:
            print(f"  Sample: {json.dumps(data['metrics'][0], indent=2)}")
    else:
        print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 3: Get dashboard data (requires auth)
print("\n[Test 3] GET /api/dashboard/data?range=24h")
print("Note: This requires authentication, testing without login...")
try:
    response = requests.get(f"{API_URL}/api/dashboard/data?range=24h", timeout=5)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"[OK] Got dashboard data:")
        print(f"  Features: {len(data.get('features', []))}")
        print(f"  Detections: {len(data.get('detections', []))}")
        print(f"  Alerts: {len(data.get('alerts', []))}")

        if len(data.get('features', [])) > 0:
            print(f"\n  Sample feature:")
            print(f"  {json.dumps(data['features'][0], indent=4)}")
        else:
            print("  [WARN] No features in last 24h")

    elif response.status_code == 401:
        print("[WARN] Authentication required (expected for dashboard)")
        print("  Dashboard data requires login")
    else:
        print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"[ERROR] Error: {e}")

# Test 4: Check database content
print("\n[Test 4] Checking database content...")
try:
    import sqlite3
    from datetime import datetime, timedelta

    conn = sqlite3.connect('data/logsentry.db')
    cur = conn.cursor()

    # Get recent features
    since_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    recent_features = cur.execute(
        'SELECT COUNT(*) FROM features WHERE timestamp >= ?',
        (since_24h,)
    ).fetchone()[0]

    total_features = cur.execute('SELECT COUNT(*) FROM features').fetchone()[0]

    print(f"  Total features in DB: {total_features}")
    print(f"  Features in last 24h: {recent_features}")

    if recent_features > 0:
        # Get latest feature
        latest = cur.execute(
            'SELECT timestamp, error_count, cpu_avg, mem_avg FROM features ORDER BY timestamp DESC LIMIT 1'
        ).fetchone()
        print(f"\n  Latest feature:")
        print(f"    Timestamp: {latest[0]}")
        print(f"    Errors: {latest[1]}")
        print(f"    CPU: {latest[2]}")
        print(f"    Memory: {latest[3]}")
    else:
        print("  [WARN] No features in last 24h - this is why dashboard is empty!")

        # Show oldest and newest
        oldest = cur.execute('SELECT timestamp FROM features ORDER BY timestamp ASC LIMIT 1').fetchone()
        newest = cur.execute('SELECT timestamp FROM features ORDER BY timestamp DESC LIMIT 1').fetchone()

        if oldest and newest:
            print(f"\n  Data range in DB:")
            print(f"    Oldest: {oldest[0]}")
            print(f"    Newest: {newest[0]}")
            print(f"    -> Data is too old for 24h view")

    conn.close()

except Exception as e:
    print(f"[ERROR] Database error: {e}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

print("\nTo fix the empty dashboard:")
print("1. Run: python send_test_data.py")
print("2. Choose [1] Normal mode or [3] Quick test")
print("3. Wait 5 minutes for processing")
print("4. Refresh dashboard")

print("\nCurrent issues detected from logs:")
print("[WARN] IF detector: Feature count mismatch (needs fixing)")
print("[WARN] VAR model: Not enough historical data")
print("[WARN] UNIQUE constraint: Duplicate timestamp in features table")
