# LogSentry AI - Tài Liệu Cấu Trúc Hệ Thống

> **Phiên bản:** PoC V2 | **Cập nhật:** 2026-04-16

---

## Tổng quan kiến trúc

LogSentry AI là hệ thống phát hiện anomaly realtime cho môi trường DevOps. Hệ thống thu thập log và metrics từ server sản xuất, xử lý qua pipeline gồm 4 detector AI, tổng hợp kết quả (fusion), rồi sinh cảnh báo. Dashboard web cho phép người dùng theo dõi và xử lý alert.

```
Luồng dữ liệu chính:
  [Server thực] → [Log Shipper / Metrics Shipper]
       → [POST /api/logs, /api/metrics]
       → [Database SQLite]
       → [Background Worker: LogProcessor]
       → [4 Detectors: Rule + VAR + IF + DeepLog]
       → [Fusion & Scoring]
       → [Alert DB + SSE Push]
       → [Dashboard hiển thị realtime]
```

---

## Cấu Trúc Thư Mục

```
LogSentry-AI-PoC-V2/
├── app/                          # Flask Web Application Layer
│   ├── __init__.py               # Application factory (create_app)
│   ├── config.py                 # Cấu hình môi trường (Dev/Prod/Test)
│   ├── models.py                 # ORM Models (SQLAlchemy)
│   ├── api/                      # RESTful API Blueprints
│   │   ├── __init__.py           # Khởi tạo Blueprint api_bp
│   │   ├── auth.py               # Middleware xác thực API key
│   │   ├── logs.py               # POST/GET /api/logs
│   │   ├── metrics.py            # POST/GET /api/metrics
│   │   ├── alerts.py             # GET /api/alerts + dashboard data
│   │   └── stream.py             # Server-Sent Events (SSE)
│   ├── auth/                     # Xác thực người dùng web
│   │   ├── __init__.py           # Khởi tạo Blueprint auth_bp
│   │   └── routes.py             # Login / Logout / Register
│   ├── dashboard/                # Web Dashboard
│   │   ├── __init__.py           # Khởi tạo Blueprint dashboard_bp
│   │   └── routes.py             # Trang chính, alerts, metrics, logs
│   ├── templates/                # Jinja2 HTML Templates
│   │   ├── base.html             # Template gốc (layout chung)
│   │   ├── auth/
│   │   │   ├── login.html        # Trang đăng nhập
│   │   │   └── register.html     # Trang đăng ký
│   │   └── dashboard/
│   │       ├── index.html        # Dashboard chính (charts, stats)
│   │       ├── alerts.html       # Trang quản lý cảnh báo
│   │       ├── metrics.html      # Trang xem system metrics
│   │       └── logs.html         # Trang xem log stream
│   └── workers/                  # Background Processing
│       ├── __init__.py           # Worker lifecycle (start/stop/status)
│       └── processor.py          # LogProcessor - xử lý log realtime
├── src/                          # Core Business Logic (AI/ML)
│   ├── __init__.py               # Package init
│   ├── detectors/                # 4 Anomaly Detectors
│   │   ├── __init__.py           # Package init
│   │   ├── rule_based.py         # Detector dựa trên rule cứng
│   │   ├── statistical.py        # VAR (Vector Autoregression) Detector
│   │   ├── ml_models.py          # Isolation Forest + Autoencoder
│   │   └── deeplog.py            # DeepLog LSTM Detector
│   ├── feature_extraction/       # Trích xuất đặc trưng
│   │   ├── __init__.py           # Package init
│   │   └── extract_features.py   # FeatureExtractor (log → features)
│   ├── fusion/                   # Fusion kết quả từ nhiều detector
│   │   ├── __init__.py           # Package init
│   │   └── fusion.py             # AnomalyFusion (voting + scoring)
│   └── data_generation/          # Sinh dữ liệu tổng hợp (PoC)
│       ├── __init__.py           # Package init
│       └── generate_logs.py      # LogGenerator (normal + anomaly)
├── log_shipper/                  # Agent thu thập dữ liệu từ server thực
│   ├── shipper.py                # LogShipper – đọc file log và gửi API
│   ├── metrics_shipper.py        # MetricsShipper – thu thập system metrics
│   └── config_example.yaml       # Cấu hình mẫu cho log shipper
├── shippers/                     # (Legacy) Agent shipper cũ
│   ├── shipper.py                # Log shipper phiên bản cũ
│   ├── metrics_shipper.py        # Metrics shipper phiên bản cũ
│   └── config_example.yaml       # Config mẫu phiên bản cũ
├── data/                         # Lưu trữ dữ liệu hệ thống
│   ├── logsentry.db              # SQLite database chính
│   ├── models/                   # Mô hình ML đã train
│   │   ├── isolation_forest.pkl  # Mô hình Isolation Forest
│   │   ├── deeplog_meta.pkl      # Metadata DeepLog (vocab, config)
│   │   └── deeplog_model.h5      # LSTM weights DeepLog
│   ├── raw/                      # Dữ liệu thô chưa xử lý
│   │   ├── application.log       # Log tổng hợp (JSONL)
│   │   └── system_metrics.jsonl  # Metrics tổng hợp (JSONL)
│   └── processed/                # Dữ liệu đã xử lý
│       ├── features.csv          # Feature vectors theo time window
│       ├── final_results.csv     # Kết quả tổng hợp từ 4 detector
│       └── alerts.csv            # Danh sách cảnh báo
├── run.py                        # Entrypoint phát triển (Flask dev server)
├── wsgi.py                       # Entrypoint production (Gunicorn/uWSGI)
├── pipeline.py                   # Pipeline độc lập (offline batch)
├── train_all_models.py           # Script train lại toàn bộ ML models
├── validate.py                   # Script kiểm tra/đánh giá hệ thống
├── seeder.py                     # Nạp dữ liệu mẫu vào hệ thống
├── generate_anomalies.py         # Tạo anomaly data để test
├── import_pipeline_data.py       # Import CSV vào database
├── process_historical.py         # Xử lý lại dữ liệu lịch sử
├── migrate_add_deeplog.py        # Migration schema thêm cột DeepLog
├── check_data.py                 # Kiểm tra dữ liệu trong database
├── quick_test.py                 # Test nhanh các API endpoint
├── test_api.py                   # Test API tổng hợp
├── test_send.py                  # Test gửi logs/metrics
├── send_test_data.py             # Gửi batch dữ liệu test
├── requirements.txt              # Dependencies cho src/ pipeline
├── requirements_flask.txt        # Dependencies cho Flask app
├── .env.example                  # Template biến môi trường
├── start.bat                     # Khởi động nhanh (Windows)
├── start.sh                      # Khởi động nhanh (Linux/Mac)
├── kichbandemo.txt               # Kịch bản demo hệ thống
└── README.md                     # Tài liệu tổng quan dự án
```

---

## Chi Tiết Từng File

---

### `app/__init__.py` — Application Factory

**Vai trò:** Điểm khởi tạo ứng dụng Flask theo pattern *Application Factory*.

**Logic chính:**
- Hàm `create_app(config_name)` tạo instance Flask, load config theo môi trường (`development` / `production` / `testing`).
- Khởi tạo các Flask extensions: `SQLAlchemy` (ORM) và `Flask-Login` (session).
- Tự động tạo thư mục `data/models`, `data/processed`, `data/raw` nếu chưa tồn tại.
- Đăng ký 3 Blueprint: `api_bp` → `/api`, `dashboard_bp` → `/`, `auth_bp` → `/auth`.
- Tạo bảng database và khởi tạo user admin mặc định (`admin/admin123`) nếu chưa có.
- Gọi `start_worker(app)` để khởi động luồng xử lý background ngay khi app start.

```python
# Pattern sử dụng:
app = create_app('development')  # hoặc 'production'
```

---

### `app/config.py` — Cấu Hình Hệ Thống

**Vai trò:** Định nghĩa toàn bộ thông số cấu hình theo từng môi trường.

**Các class cấu hình:**

| Class | Mục đích |
|-------|----------|
| `Config` | Base config chung |
| `DevelopmentConfig` | `DEBUG=True`, dùng trong phát triển |
| `ProductionConfig` | `DEBUG=False`, cookie secure |
| `TestingConfig` | Dùng SQLite in-memory |

**Thông số quan trọng:**
- `WINDOW_MINUTES = 1` — Kích thước time window xử lý log (1 phút).
- `WINDOW_CHECK_INTERVAL = 10` — Worker kiểm tra window mới mỗi 10 giây.
- `QUEUE_MAXSIZE = 10000` — Tối đa 10.000 sự kiện trong hàng đợi.
- `API_KEYS` — Bảng key xác thực cho Log Shipper (header `X-API-Key`).
- `SQLALCHEMY_DATABASE_URI` — Đường dẫn tuyệt đối tới SQLite `data/logsentry.db`.

---

### `app/models.py` — ORM Database Models

**Vai trò:** Định nghĩa schema database thông qua SQLAlchemy ORM. Hệ thống có 5 bảng chính:

#### `User` — Quản lý người dùng
- Lưu thông tin đăng nhập (username, email, password hash).
- `set_password()` / `check_password()` sử dụng Werkzeug hash (bcrypt).
- `is_admin` phân quyền admin.
- Tích hợp `UserMixin` của Flask-Login để quản lý session.

#### `LogEntry` — Log thô từ server
- Lưu từng log gửi lên từ shipper: timestamp, level (`ERROR/WARN/INFO/DEBUG`), message, service, host.
- `extra_data`: JSON string chứa các trường tuỳ chỉnh.
- Index trên `timestamp`, `level`, `service`, `host` để truy vấn nhanh.

#### `MetricEntry` — System Metrics
- Lưu metrics theo từng điểm thời gian: CPU %, Memory %, Disk I/O, Network In/Out.
- Nguồn từ `MetricsShipper` chạy trên server thực.

#### `Feature` — Feature Vectors theo Time Window
- Kết quả tổng hợp log + metrics trong mỗi window 1 phút:
  - Đếm log theo level: `error_count`, `warn_count`, `info_count`, `total_logs`
  - Tỷ lệ lỗi: `error_rate`
  - Trung bình metrics: `cpu_avg`, `mem_avg`, `disk_io_avg`, `network_in`, `network_out`
- `unique=True` trên `timestamp` để tránh duplicate window.

#### `DetectionResult` — Kết Quả Phát Hiện
- Lưu kết quả của từng detector trên mỗi window:
  - `rule_anomaly`, `rule_score` — Rule-based
  - `var_anomaly`, `var_score` — VAR Statistical
  - `if_anomaly`, `if_score` — Isolation Forest
  - `ae_anomaly`, `ae_score` — Autoencoder (legacy, đang dùng DeepLog)
  - `deeplog_anomaly`, `deeplog_score` — DeepLog LSTM
  - `final_anomaly`, `final_score`, `severity`, `votes` — Kết quả tổng hợp
- `detector_agreement`: chuỗi tên các detector đồng ý có anomaly (vd: `"rule,if,var"`).

#### `Alert` — Cảnh Báo
- Sinh ra khi `final_anomaly = 1`.
- Lưu severity (`High/Medium/Low`), message mô tả nguyên nhân, context (error_count, cpu_avg, mem_avg).
- `is_resolved` / `resolved_at` / `resolved_by` — Vòng đời xử lý alert.
- Quan hệ FK tới `User` (người xử lý alert).

---

### `app/api/__init__.py` — API Blueprint

Tạo `api_bp = Blueprint('api', __name__)` và import các route module.

---

### `app/api/auth.py` — Xác Thực API

**Vai trò:** Middleware bảo vệ các API endpoint dành cho shipper.

```python
@require_api_key
def my_endpoint():
    ...
```

- Decorator `require_api_key` kiểm tra header `X-API-Key` với bảng key trong config.
- Trả `401 Unauthorized` nếu thiếu hoặc sai key.
- Không ảnh hưởng đến các route dashboard (dùng Flask-Login).

---

### `app/api/logs.py` — API Nhận Log

**Vai trò:** Endpoint nhận batch log từ Log Shipper.

**`POST /api/logs`** (cần `X-API-Key`):
- Nhận JSON `{"logs": [{timestamp, level, message, service, host, extra}]}`.
- Parse timestamp (hỗ trợ ISO 8601, tự động xử lý `Z` suffix).
- Lưu từng `LogEntry` vào DB, commit batch.
- Đẩy sự kiện `{type: "logs_received"}` vào `log_queue` để kích hoạt worker xử lý.
- Trả về số log đã `received` và `saved`.

**`GET /api/logs`** (không cần auth):
- Lấy log gần nhất, hỗ trợ filter `?limit=100&level=ERROR`.

---

### `app/api/metrics.py` — API Nhận Metrics

**Vai trò:** Endpoint nhận batch metrics từ Metrics Shipper.

**`POST /api/metrics`** (cần `X-API-Key`):
- Nhận JSON `{"metrics": [{timestamp, host, cpu, memory, disk_io, network_in, network_out}]}`.
- Lưu từng `MetricEntry`, đẩy sự kiện `metrics_received` vào queue.

**`GET /api/metrics`** (không cần auth):
- Lấy metrics gần nhất, filter theo `?host=server-01`.

---

### `app/api/alerts.py` — API Alerts & Dashboard Data

**`GET /api/alerts`** (cần login):
- Lấy danh sách alert với filter: `severity`, `resolved`, `hours`, `limit`.
- Sắp xếp theo timestamp giảm dần.

**`POST /api/alerts/<id>/resolve`** (cần login):
- Đánh dấu alert đã xử lý, ghi `resolved_at` và `resolved_by` (user hiện tại).

**`GET /api/dashboard/data`** (cần login):
- API tổng hợp cung cấp toàn bộ dữ liệu cho dashboard:
  - `summary`: tổng số alert chia theo severity và trạng thái.
  - `features`: danh sách feature theo time window.
  - `detections`: kết quả detection từng window.
  - `alerts`: danh sách cảnh báo.
- Hỗ trợ range: `?range=24h|7d|30d`.

---

### `app/api/stream.py` — Server-Sent Events (SSE)

**Vai trò:** Cung cấp kênh push realtime từ server → browser.

**`GET /api/stream/alerts`** (cần login):
- Kết nối SSE, client giữ kết nối HTTP mở.
- Khi `LogProcessor` phát hiện anomaly, gọi `send_sse_event('alert', data)` → đẩy vào `sse_queue`.
- Generator đọc từ queue và stream về client dạng `event: alert\ndata: {...}\n\n`.
- Gửi heartbeat `:heartbeat\n\n` mỗi 30 giây để giữ kết nối.

**`GET /api/stream/status`** (cần login):
- Gửi trạng thái worker mỗi 10 giây: `{running, processed_windows, alerts_generated}`.

**`sse_queue`**: `queue.Queue(maxsize=1000)` — buffer toàn cục cho các SSE event.

---

### `app/auth/__init__.py` — Auth Blueprint

Tạo `auth_bp = Blueprint('auth', __name__)`.

---

### `app/auth/routes.py` — Routes Xác Thực

**`GET/POST /auth/login`**:
- Hiển thị form đăng nhập, xác thực với DB, cập nhật `last_login`, tạo session với Flask-Login.
- Redirect tới `?next=` hoặc dashboard sau khi đăng nhập.

**`GET /auth/logout`**:
- Xoá session. Redirect về trang login.

**`GET/POST /auth/register`**:
- Form đăng ký với validation: email, password tối thiểu 6 ký tự, kiểm tra trùng.
- Tạo User mới (không có quyền admin).

---

### `app/dashboard/__init__.py` — Dashboard Blueprint

Tạo `dashboard_bp = Blueprint('dashboard', __name__)`.

---

### `app/dashboard/routes.py` — Routes Dashboard

**`GET /`** (cần login):
- Lấy summary 24h: tổng alert, unresolved, high/medium severity.
- 10 alert gần nhất.
- Render `dashboard/index.html`.

**`GET /alerts`** (cần login): Trang xem 100 alert gần nhất.

**`GET /metrics`** (cần login): Trang xem system metrics (data load qua AJAX).

**`GET /logs`** (cần login): Trang xem log stream (stream qua SSE hoặc AJAX).

---

### `app/templates/base.html` — Template Gốc

Layout HTML chung: navigation bar, flash messages, link đến static CSS/JS. Các template con kế thừa thông qua Jinja2 `{% extends "base.html" %}`.

---

### `app/templates/dashboard/index.html` — Dashboard Chính

Trang chủ dashboard với:
- **Stat cards**: tổng alert, unresolved, high severity, medium severity.
- **Charts** (Chart.js): time-series anomaly score, CPU/Memory trend, error rate.
- **Alert table**: 10 alert gần nhất với nút "Resolve".
- Gọi `GET /api/dashboard/data?range=24h` mỗi 10 giây để cập nhật biểu đồ.
- Kết nối SSE `GET /api/stream/alerts` để hiển thị alert popup realtime.

---

### `app/templates/dashboard/alerts.html` — Trang Alerts

Bảng tất cả alert với filter theo severity, trạng thái. Nút Resolve gọi `POST /api/alerts/<id>/resolve`.

---

### `app/templates/dashboard/metrics.html` — Trang Metrics

Biểu đồ CPU, Memory, Network theo thời gian. Data từ `GET /api/metrics` qua AJAX.

---

### `app/templates/dashboard/logs.html` — Trang Logs

Hiển thị log stream dạng bảng, lọc theo level. Data từ `GET /api/logs` qua AJAX polling.

---

### `app/workers/__init__.py` — Worker Lifecycle

**Vai trò:** Quản lý vòng đời của background worker thread.

**Thành phần:**
- `log_queue`: `queue.Queue(maxsize=10000)` — hàng đợi toàn cục nhận sự kiện từ API.
- `worker_thread`: tham chiếu thread hiện tại.
- `worker_status`: dict theo dõi trạng thái: `running`, `processed_windows`, `alerts_generated`, `errors`.

**Hàm:**
- `start_worker(app)`: Tạo `LogProcessor`, khởi động daemon thread. Nếu thread đã chạy thì skip.
- `get_worker_status()`: Trả về bản sao của `worker_status`.
- `stop_worker()`: Đẩy sự kiện `shutdown` vào queue, join thread.

---

### `app/workers/processor.py` — LogProcessor (Core xử lý)

**Vai trò:** Bộ xử lý trung tâm chạy trong background thread. Đây là file quan trọng nhất trong flow xử lý.

**Class `LogProcessor`:**

**`run()`** — Vòng lặp chính:
1. Khởi tạo 4 detector (`_init_detectors()`).
2. Loop vô hạn: đọc event từ queue, mỗi `WINDOW_CHECK_INTERVAL` giây gọi `_check_and_process_windows()`.

**`_init_detectors()`**:
- Khởi tạo: `RuleBasedDetector`, `IsolationForestDetector`, `VARDetector`, `DeepLogDetector`.
- Load model từ `data/models/` nếu có. Log cảnh báo nếu chưa có model (sẽ train tự động).

**`_check_and_process_windows()`**:
- Query `Feature` cuối cùng đã xử lý để xác định `start_time`.
- Duyệt qua tất cả window hoàn chỉnh (< window hiện tại) chưa xử lý.
- Gọi `_process_window(window_time)` cho từng window.

**`_process_window(window_start)`**:
1. Gọi `_extract_features(start, end)` — aggregate log + metrics trong window.
2. Kiểm tra duplicate (unique constraint), skip nếu đã tồn tại.
3. Lưu `Feature` object vào DB.
4. Nếu detector sẵn sàng, gọi `_run_detection(window_start, features)`.

**`_extract_features(start_time, end_time)`**:
- Query `LogEntry` và `MetricEntry` trong khoảng time window.
- Đếm log theo level → `error_count`, `warn_count`, `info_count`, `total_logs`, `error_rate`.
- Tính trung bình/tổng metrics → `cpu_avg`, `mem_avg`, `disk_io_avg`, `network_in`, `network_out`.
- Trả dict features dùng NumPy.

**`_run_detection(window_start, features)`** — Chạy 4 detector:
1. **Rule-based**: Gọi `rule_detector.detect(df)` → lấy `rule_anomaly`, `rule_score`.
2. **Isolation Forest**: Nếu model loaded, scale features với scaler, predict → `if_anomaly`, `if_score`.
3. **VAR**: Lấy 50 feature window gần nhất từ DB, detect → `var_anomaly`, `var_score`.
4. **DeepLog**: Lấy 100 log gần nhất, detect sequence → `deeplog_anomaly`, `deeplog_score`.
5. **Fusion** (weighted voting):
   - `votes` = tổng số detector phát hiện anomaly.
   - `final_score` = `rule*0.20 + IF*0.30 + VAR*0.25 + DeepLog*0.25`.
   - `final_anomaly = 1` nếu `votes >= 2` hoặc `final_score >= 0.6`.
   - `severity`: `High` (score ≥ 0.7), `Medium` (score ≥ 0.4), `Low` (score < 0.4).
6. Lưu `DetectionResult` vào DB.
7. Nếu anomaly → gọi `_generate_alert()`.

**`_generate_alert()`**:
- Tạo message mô tả: liệt kê error count, CPU cao, memory cao.
- Lưu `Alert` vào DB, cập nhật `worker_status['alerts_generated']`.
- Gọi `send_sse_event('alert', ...)` để push realtime tới browser.

---

### `src/detectors/rule_based.py` — Detector Dựa Trên Rule

**Class `RuleBasedDetector`:**

Phát hiện anomaly bằng ngưỡng cứng trên feature vector:

| Rule | Điều kiện | Score |
|------|-----------|-------|
| 1 | `error_count > 5` | +0.3 |
| 2 | `error_rate > 5%` | +0.2 |
| 3 | `warn_count > 20` | +0.1 |
| 4 | `cpu_avg > 80%` | +0.2 |
| 5 | `mem_avg > 85%` | +0.2 |
| 6 | `total_logs > 3× median` | +0.15 |

- `detect(features_df)`: Duyệt từng row, tính `rule_anomaly` (0/1), `rule_score` (0-1), `rule_reasons` (string lý do).
- `get_statistics()`: Tính Precision, Recall, F1 nếu có ground truth (`is_anomaly`).
- **Ưu điểm**: Không cần training, phản ứng ngay lập tức, dễ giải thích.
- **Nhược điểm**: Không học được patterns phức tạp.

---

### `src/detectors/statistical.py` — VAR Detector

**Class `VARDetector`:**

Phát hiện anomaly dựa trên **Vector Autoregression** — mô hình dự báo chuỗi thời gian đa biến.

**Nguyên lý:**
1. Train VAR model trên 70% data lịch sử (fit với `statsmodels.tsa.api.VAR`).
2. Với mỗi window mới: dùng model forecast giá trị kỳ vọng.
3. Tính `residual = actual - forecast`.
4. Anomaly nếu `|normalized_residual| > 3σ` (threshold_sigma = 3).
5. `var_score = min(max_normalized_residual / 10, 1.0)`.

**Fallback `_simple_baseline_detect()`**: Khi VAR không khả dụng, dùng rolling z-score (window 20) — phát hiện anomaly khi `|z-score| > 3`.

**Thông số:** `maxlags=5`, `train_ratio=0.7`, `threshold_sigma=3`.

---

### `src/detectors/ml_models.py` — Isolation Forest & Autoencoder

#### `IsolationForestDetector`

**Nguyên lý Isolation Forest:**
- Xây dựng nhiều cây quyết định ngẫu nhiên.
- Anomaly dễ bị "cô lập" (depth thấp hơn) → anomaly score âm hơn.
- `contamination=0.05` → giả định 5% data là anomaly.

**Flow:**
1. `_prepare_data()`: Chọn numeric features, chuẩn hoá với `StandardScaler`.
2. `train()`: Fit `sklearn.ensemble.IsolationForest`.
3. `detect()`: `model.predict()` → `-1` là anomaly. Score normalize về [0,1].
4. `save_model()` / `load_model()`: Pickle (`model + scaler + feature_columns`).

#### `AutoencoderDetector`

**Nguyên lý Autoencoder:**
- LSTM/Dense encoder-decoder học biểu diễn nén của data normal.
- Anomaly = reconstruction error cao (vượt threshold `p95` của training errors).

**Lưu ý:** Autoencoder hiện có trong file nhưng trong runtime thực tế đã được thay thế bởi **DeepLog**. `ae_anomaly` trong `DetectionResult` thường để 0.

---

### `src/detectors/deeplog.py` — DeepLog LSTM Detector

**Class `LogParser`:**
- `_extract_template(message)`: Trích xuất log template bằng regex — thay thế số, IP, hex, path thành `<*>`.
  - VD: `"User 123 logged in"` → `"User <*> logged in"` → event_id duy nhất.
- `parse(message)`: Trả về integer event_id (tạo mới nếu template chưa gặp).

**Class `DeepLogDetector`:**

**Nguyên lý DeepLog** (từ paper gốc):
1. Parse log messages thành chuỗi event_id (log keys).
2. Train LSTM để predict event_id tiếp theo trong sequence.
3. Anomaly = event xảy ra có prediction confidence thấp (< threshold 0.5).

**Architecture LSTM:**
```
Embedding(vocab_size, 32) → LSTM(64, return_seq=True) → Dropout(0.2)
                          → LSTM(64) → Dropout(0.2)
                          → Dense(vocab_size, softmax)
```

**Fallback `_prepare_features_sequences()`**: Khi không có log messages, encode feature values thành pseudo event codes: `event_code = error_level * 100 + warn_level * 10 + cpu_level`.

**`save_model()` / `load_model()`**: Lưu Keras `.h5` + pickle metadata (`parser`, `vocab_size`, `config`).

---

### `src/fusion/fusion.py` — AnomalyFusion

**Vai trò:** Tổng hợp kết quả từ nhiều detector thành quyết định cuối cùng.

**Logic Fusion:**

```
Trọng số mặc định:
  rule: 0.30, var: 0.25, if: 0.25, ae: 0.20

final_score = Σ(weight[d] × score[d])  (normalized)
votes = Σ anomaly[d]

Điều kiện anomaly:
  - votes >= 2 → final_anomaly = 1
  - votes == 1 AND score >= 0.4 → final_anomaly = 1 (Low severity)

Severity:
  - final_score >= 0.7 → High
  - final_score >= 0.4 → Medium
  - else             → Low
```

**`get_alerts(result_df, severity_filter)`**: Filter anomaly windows, chọn columns liên quan, sort theo severity + score.

---

### `src/feature_extraction/extract_features.py` — FeatureExtractor

**Vai trò:** Trích xuất feature vector từ file log thô (offline pipeline).

**Class `FeatureExtractor`:**
- `parse_logs(log_file)`: Đọc JSONL, parse thành DataFrame với timestamp.
- `parse_metrics(metrics_file)`: Đọc JSONL metrics.
- `extract_log_features(logs_df)`: Nhóm log theo time window (`pd.Grouper(freq='5min')`), đếm theo level, tính error_rate, unique_services.
- `combine_features(log_features, metrics_df)`: Merge log features với metrics theo timestamp (outer join). Fill NaN = 0.
- `process_and_save(log_file, metrics_file, output_file)`: Full pipeline → lưu `features.csv`.

**Sử dụng trong offline pipeline** (`pipeline.py`), không dùng trong realtime (realtime dùng `processor.py`).

---

### `src/data_generation/generate_logs.py` — Sinh Dữ Liệu Tổng Hợp

**Vai trò:** Tạo dataset log và metrics giả lập cho PoC/testing.

**Class `LogGenerator`:**
- Phân phối log bình thường: 70% INFO, 20% DEBUG, 8% WARN, 2% ERROR.
- Khi `is_anomaly`:
  - `error_spike`: tăng tỷ lệ ERROR/WARN, dùng ANOMALY_MESSAGES.
  - `resource_spike`: CPU 80-99%, Memory 85-98%.

**`generate_dataset()`**: Tạo `N` window theo khoảng thời gian, mỗi window có 100 logs + 1 metrics entry. Ground truth `is_anomaly` gán vào metadata. Xuất ra `data/raw/application.log` và `data/raw/system_metrics.jsonl`.

---

### `log_shipper/shipper.py` — Log Shipper Agent

**Vai trò:** Agent chạy trên server thực, đọc file log và gửi lên LogSentry API.

**Class `LogShipper`:**
- `parse_log_line(line)`: Hỗ trợ 2 format log phổ biến:
  - `YYYY-MM-DD HH:MM:SS LEVEL message`
  - `[LEVEL] YYYY-MM-DD HH:MM:SS - message`
  - Fallback: raw text → INFO level.
- `tail_file(log_file)`: Seek đến cuối file, real-time tail. Buffer 100 log hoặc 10 giây rồi flush.
- `flush_buffer()` / `send_logs(logs)`: Gửi batch qua `POST /api/logs` với header `X-API-Key`.

**Sử dụng:**
```bash
python log_shipper/shipper.py --api-url http://server:5000 --api-key KEY \
  --log-file /var/log/app.log --service my-app
```

---

### `log_shipper/metrics_shipper.py` — Metrics Shipper Agent

**Vai trò:** Thu thập system metrics từ OS và gửi định kỳ lên API.

**Class `MetricsShipper`:**
- `collect_metrics()`: Dùng `psutil` để thu thập:
  - `cpu_percent(interval=1)` — CPU usage %.
  - `virtual_memory().percent` — Memory usage %.
  - `disk_io_counters()` — tổng bytes read+write.
  - `net_io_counters()` — tính rate (bytes/sec) so với lần trước.
- `send_metrics(metrics)`: `POST /api/metrics` mỗi `interval` giây (default 60s).

**Sử dụng:**
```bash
python log_shipper/metrics_shipper.py --api-url http://server:5000 --api-key KEY --interval 60
```

---

### `log_shipper/config_example.yaml` — Cấu Hình Mẫu Shipper

Template YAML cấu hình cho shipper: URL API, API key, service name, log files cần monitor, batch size, retry settings, metrics collection interval.

---

### `run.py` — Entrypoint Phát Triển

```python
app = create_app(os.getenv('FLASK_ENV', 'development'))
app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
```

Khởi động Flask dev server. `threaded=True` để xử lý nhiều request đồng thời (cần thiết cho SSE).

---

### `wsgi.py` — Entrypoint Production

Dùng với **Gunicorn** hoặc **uWSGI**:
```bash
gunicorn -w 4 -b 0.0.0.0:5000 --timeout 120 wsgi:app
```

Load config `production` (DEBUG=False, cookie secure).

---

### `pipeline.py` — Pipeline Offline Batch

**Vai trò:** Chạy toàn bộ pipeline phát hiện anomaly offline trên dữ liệu lịch sử.

**Class `LogSentryPipeline`** - 5 bước:
1. `step1_generate_data()`: Gọi `generate_dataset()` tạo synthetic data.
2. `step2_extract_features()`: Dùng `FeatureExtractor` sinh `features.csv`.
3. `step3_run_detectors()`: Chạy 4 detector (Rule, VAR, IF, Autoencoder) → kết quả ghép vào DataFrame.
4. `step4_fusion()`: Dùng `AnomalyFusion.fuse()` → sinh `final_results.csv`.
5. `step5_generate_alerts()`: Filter anomaly → sinh `alerts.csv`.

**Sử dụng:**
```bash
python pipeline.py           # Tạo data + chạy pipeline
python pipeline.py --no-generate  # Dùng data có sẵn
```

---

### `train_all_models.py` — Script Train ML Models

**Vai trò:** Train lại 3 ML model từ dữ liệu trong database.

**Flow:**
1. `extract_features_for_training()`: Query toàn bộ `Feature` table → DataFrame.  Load toàn bộ `LogEntry` → `logs_df` cho DeepLog.
2. `train_isolation_forest(features_df)`: Train và lưu `data/models/isolation_forest.pkl`.
3. `train_var(features_df)`: Train VAR (không lưu file, refitted on-demand).
4. `train_deeplog(features_df, logs_df)`: Train LSTM, lưu `data/models/deeplog`.

**Sử dụng:** Chạy sau khi đã có đủ dữ liệu (~vài giờ) để tăng độ chính xác.
```bash
python train_all_models.py
```

---

### `validate.py` — Script Đánh Giá Hệ Thống

**Vai trò:** Kiểm tra toàn diện hệ thống qua 4 nhóm test.

**Class `LogSentryValidator`:**
1. **Technical Validation**: Kiểm tra file tồn tại, format CSV đúng schema.
2. **Logic Validation**:
   - Rule-based phải phát hiện ≥ 50% windows có `error_count > 10`.
   - Voting counts phải nhất quán (recalculate và so sánh).
   - Severity phân loại đúng theo ngưỡng score.
3. **Performance Validation**: Tính Precision, Recall, F1 từ `is_anomaly` ground truth. So sánh từng detector, kiểm tra Fusion ≥ best individual.
4. **Sanity Checks**: Không có NaN, scores ∈ [0,1], anomaly columns binary, severity values hợp lệ, alert count khớp.

Xuất báo cáo `validation_report.json`.

---

### `seeder.py` — Nạp Dữ Liệu Test

**Vai trò:** Tự động gửi dữ liệu realistically vào hệ thống đang chạy để test dashboard.

- `seed_historical_data(num_windows=30)`: Gửi 30 windows (2 giờ trước → hiện tại), 10% có anomaly (lỗi cao + CPU/Memory cao).
- `seed_recent_data()`: Gửi 3 windows gần nhất (sẽ được worker xử lý ngay).
- `check_results()`: Truy vấn SQLite để xác nhận data đã được xử lý.

```bash
python seeder.py  # Server phải đang chạy
```

---

### `generate_anomalies.py` — Sinh Anomaly Data

Tạo dữ liệu anomaly rõ ràng (high error rate, high CPU/memory) để test khả năng phát hiện của hệ thống.

---

### `import_pipeline_data.py` — Import CSV vào Database

Import kết quả từ offline pipeline (`features.csv`, `final_results.csv`) vào SQLite để hiển thị trên dashboard.

---

### `process_historical.py` — Xử Lý Lại Lịch Sử

Chạy lại detector + feature extraction trên dữ liệu đã có trong DB (không cần gửi lại từ shipper).

---

### `migrate_add_deeplog.py` — Database Migration

Thêm các cột `deeplog_anomaly`, `deeplog_score` vào bảng `detection_results` khi nâng cấp lên PoC V2. Chạy một lần duy nhất khi upgrade.

---

### `check_data.py` — Kiểm Tra Dữ Liệu Database

Script nhanh kiểm tra số records trong mỗi bảng, xem dữ liệu gần nhất, phát hiện vấn đề về dữ liệu.

---

### `quick_test.py` / `test_api.py` / `test_send.py` / `send_test_data.py` — Test Scripts

- `quick_test.py`: Test nhanh các endpoint chính (health check, login, gửi log/metric).
- `test_api.py`: Test toàn diện API.
- `test_send.py` / `send_test_data.py`: Gửi batch dữ liệu lớn để performance test.

---

### `requirements.txt` — Dependencies Core Pipeline

```
pandas, numpy, scikit-learn, statsmodels, tensorflow (optional)
```
Dùng cho `src/` (detectors, pipeline.py, validate.py).

---

### `requirements_flask.txt` — Dependencies Flask App

```
flask, flask-sqlalchemy, flask-login, werkzeug
pandas, numpy, scikit-learn, statsmodels, psutil
tensorflow (optional, cho DeepLog)
```
Dùng cho toàn bộ ứng dụng web.

---

### `.env.example` — Template Biến Môi Trường

Mẫu cấu hình biến môi trường:
```
SECRET_KEY=          # Flask secret key
DATABASE_URL=        # SQLite path (mặc định: data/logsentry.db)
FLASK_ENV=           # development | production
API_KEYS=            # API key cho shipper
```

---

### `start.bat` / `start.sh` — Script Khởi Động Nhanh

Script tự động:
1. Kiểm tra Python/pip.
2. Cài dependencies từ `requirements_flask.txt`.
3. Tạo thư mục `data/`.
4. Chạy `python run.py`.

---

### `kichbandemo.txt` — Kịch Bản Demo

Hướng dẫn từng bước trình bày demo hệ thống: khởi động server, seed data, mở dashboard, giải thích từng phần của UI, trigger anomaly thủ công, xem realtime alert.

---

## Luồng Dữ Liệu Chi Tiết

```
1. Thu thập dữ liệu
   LogShipper (server thực)     →  POST /api/logs    → LogEntry (DB)
   MetricsShipper (server thực) →  POST /api/metrics → MetricEntry (DB)
                                    ↓ (queue event)
2. Xử lý background (mỗi 10 giây)
   LogProcessor._check_and_process_windows()
     → LogEntry + MetricEntry (1 phút window)
     → _extract_features() → Feature (DB)
     → _run_detection():
         RuleBasedDetector.detect()   → rule_anomaly, rule_score
         VARDetector.detect()         → var_anomaly, var_score
         IsolationForestDetector      → if_anomaly, if_score
         DeepLogDetector.detect()     → deeplog_anomaly, deeplog_score
     → Fusion (weighted voting)       → final_anomaly, severity
     → DetectionResult (DB)
     → (if anomaly) Alert (DB)
     → send_sse_event('alert', ...)

3. Hiển thị realtime
   Browser (SSE) ← /api/stream/alerts ← sse_queue ← send_sse_event()
   Dashboard     ← /api/dashboard/data (polling 10s)
```

---

## Bảng Trọng Số Detector

| Detector         | Trọng số | Phương pháp             | Model file                              |
|------------------|----------|-------------------------|-----------------------------------------|
| Rule-based       | 30%      | Ngưỡng cứng             | Không cần                               |
| Isolation Forest | 25%      | Unsupervised ML         | `isolation_forest.pkl`                  |
| VAR              | 25%      | Time-series statistics  | In-memory                               |
| DeepLog LSTM     | 20%      | Deep Learning sequence  | `deeplog_model.h5` + `deeplog_meta.pkl` |

---

## Database Schema Tóm Tắt

| Bảng                | Mục đích                                  | Records điển hình |
|---------------------|-------------------------------------------|-------------------|
| `users`             | Tài khoản truy cập                        | Vài chục          |
| `log_entries`       | Raw logs từ shipper                       | Hàng triệu        |
| `metric_entries`    | System metrics                            | Hàng chục nghìn   |
| `features`          | Aggregated window features                | Hàng nghìn        |
| `detection_results` | Kết quả phát hiện mỗi window              | Hàng nghìn        |
| `alerts`            | Cảnh báo anomaly                          | Hàng trăm         |
