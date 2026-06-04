"""
Generate Anomaly Scenarios - Tạo tình huống bất thường để trigger alerts
"""
import requests
import time
from datetime import datetime
import random

API_URL = "http://localhost:5000"
API_KEY = "logsentry-api-key-change-in-production"

def send_logs(logs):
    """Send logs to API"""
    response = requests.post(
        f"{API_URL}/api/logs",
        json={"logs": logs},
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
    )
    return response.status_code == 201

def send_metrics(metrics):
    """Send metrics to API"""
    response = requests.post(
        f"{API_URL}/api/metrics",
        json={"metrics": metrics},
        headers={
            "Content-Type": "application/json",
            "X-API-Key": API_KEY
        }
    )
    return response.status_code == 201

def scenario_error_spike():
    """Scenario 1: Error Spike - Spike lỗi đột ngột"""
    print("\n🔴 SCENARIO 1: ERROR SPIKE")
    print("Tạo spike lỗi đột ngột (50+ errors trong 1 phút)")

    errors = [
        "Database connection timeout after 30s",
        "Redis connection refused - Connection reset by peer",
        "HTTP 500 Internal Server Error - NullPointerException",
        "OutOfMemoryError: Java heap space",
        "Failed to execute SQL query - Deadlock detected",
        "API Gateway timeout - Service unavailable",
        "Authentication failed - Invalid token",
        "Rate limit exceeded - 429 Too Many Requests"
    ]

    logs = []
    for i in range(60):  # 60 errors
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": "ERROR",
            "message": random.choice(errors),
            "service": "production-api",
            "host": "hodung-mbey"
        })

    if send_logs(logs):
        print(f"✓ Sent {len(logs)} ERROR logs")
        return True
    return False

def scenario_high_cpu():
    """Scenario 2: High CPU - CPU tăng đột ngột"""
    print("\n🟡 SCENARIO 2: HIGH CPU USAGE")
    print("Tạo spike CPU (90%+ trong vài phút)")

    metrics = []
    for i in range(10):
        metrics.append({
            "timestamp": datetime.now().isoformat(),
            "host": "hodung-mbey",
            "cpu": random.uniform(88, 98),  # Very high!
            "memory": random.uniform(75, 85),
            "disk_io": random.randint(4000, 8000),
            "network_in": random.randint(800, 1500),
            "network_out": random.randint(600, 1200)
        })
        time.sleep(0.5)

    if send_metrics(metrics):
        print(f"✓ Sent {len(metrics)} HIGH CPU metrics")
        return True
    return False

def scenario_memory_leak():
    """Scenario 3: Memory Leak - Memory tăng dần"""
    print("\n🟠 SCENARIO 3: MEMORY LEAK")
    print("Tạo memory leak (memory tăng dần lên 90%+)")

    logs = []
    metrics = []

    # Some memory-related errors
    for i in range(15):
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": "WARN",
            "message": f"Memory usage high: {80 + i}% - GC running",
            "service": "production-api",
            "host": "hodung-mbey"
        })

    # Memory metrics climbing
    for i in range(8):
        mem = 75 + (i * 2)  # 75%, 77%, 79%... up to 89%
        metrics.append({
            "timestamp": datetime.now().isoformat(),
            "host": "hodung-mbey",
            "cpu": random.uniform(60, 75),
            "memory": mem,
            "disk_io": random.randint(1000, 2000),
            "network_in": random.randint(200, 500),
            "network_out": random.randint(100, 300)
        })
        time.sleep(0.5)

    send_logs(logs)
    if send_metrics(metrics):
        print(f"✓ Sent {len(logs)} WARN logs + {len(metrics)} metrics")
        return True
    return False

def scenario_cascade_failure():
    """Scenario 4: Cascade Failure - Lỗi dây chuyền"""
    print("\n🔴 SCENARIO 4: CASCADE FAILURE")
    print("Tạo cascade failure (nhiều service lỗi dây chuyền)")

    services = [
        "auth-service",
        "payment-service",
        "order-service",
        "notification-service",
        "email-service"
    ]

    logs = []

    # Each service fails one after another
    for service in services:
        for i in range(10):
            logs.append({
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"{service} - Service unavailable - Cannot connect to upstream",
                "service": service,
                "host": "hodung-mbey"
            })

    # High resource usage during cascade
    metrics = []
    for i in range(5):
        metrics.append({
            "timestamp": datetime.now().isoformat(),
            "host": "hodung-mbey",
            "cpu": random.uniform(85, 95),
            "memory": random.uniform(82, 92),
            "disk_io": random.randint(5000, 10000),
            "network_in": random.randint(1000, 2000),
            "network_out": random.randint(800, 1500)
        })
        time.sleep(0.5)

    send_logs(logs)
    if send_metrics(metrics):
        print(f"✓ Sent {len(logs)} ERROR logs from {len(services)} services")
        return True
    return False

def main():
    print("="*70)
    print("🚨 ANOMALY GENERATOR - TẠO CẢNH BÁO")
    print("="*70)
    print("\nChọn scenario để tạo anomaly:\n")
    print("1. Error Spike          - 60 errors đột ngột (HIGH severity)")
    print("2. High CPU             - CPU 90%+ (MEDIUM severity)")
    print("3. Memory Leak          - Memory tăng dần lên 90%+ (MEDIUM)")
    print("4. Cascade Failure      - Nhiều service lỗi dây chuyền (HIGH)")
    print("5. ALL SCENARIOS        - Chạy tất cả scenarios")
    print()

    choice = input("Chọn (1-5): ").strip()

    scenarios = {
        '1': scenario_error_spike,
        '2': scenario_high_cpu,
        '3': scenario_memory_leak,
        '4': scenario_cascade_failure
    }

    print()
    print("="*70)

    if choice == '5':
        print("Chạy TẤT CẢ scenarios...")
        for func in scenarios.values():
            func()
            time.sleep(2)
    elif choice in scenarios:
        scenarios[choice]()
    else:
        print("❌ Invalid choice")
        return

    print()
    print("="*70)
    print("✅ HOÀN TẤT!")
    print("="*70)
    print()
    print("Đợi 60 giây để auto-processor xử lý...")
    print("Sau đó:")
    print("  1. Vào http://103.90.225.38:5000/alerts")
    print("  2. Reload trang để thấy alerts mới")
    print("  3. Dashboard sẽ hiển thị cảnh báo!")
    print()

if __name__ == '__main__':
    main()
