# Kế hoạch chính thức đánh giá LogSentry AI bằng dữ liệu log có ground truth

## 1. Mục tiêu và quyết định phạm vi

Tài liệu này là protocol triển khai chính thức cho giai đoạn đánh giá độ chính xác của LogSentry AI.

**Mục tiêu chính:** tạo kết quả Precision, Recall, F1-score và confusion matrix có thể tái lập được bằng dữ liệu log công khai có nhãn thật, để thay thế việc đánh giá chỉ trên dữ liệu tự sinh.

### Phạm vi được chấp nhận

- Đánh giá định lượng chỉ sử dụng **log data có ground truth** từ BGL và HDFS.
- Các detector dùng input hợp lệ từ log: Rule-based log-only, Isolation Forest log-feature, DeepLog sequence; VAR log-time-series chỉ chạy khi cấu trúc dữ liệu đáp ứng điều kiện.
- Fusion trong thí nghiệm được gọi là **log-only fusion**: chỉ gộp những detector có input hợp lệ trên dataset tương ứng.

### Ngoài phạm vi đánh giá định lượng

- CPU, memory, disk I/O, network I/O không được đưa vào bảng Precision/Recall/F1.
- Không tự sinh metrics từ label hoặc anomaly scenario.
- Không tuyên bố Fusion đủ 4 detector được benchmark độc lập bằng BGL/HDFS.

### Phạm vi vẫn giữ ở mức kiểm thử tích hợp

Luồng shipper → API → database → worker → alert → SSE → dashboard vẫn được kiểm thử bằng dữ liệu synthetic/realtime. Tuy nhiên, kết quả đó chỉ chứng minh hệ thống vận hành end-to-end; **không phải bằng chứng khoa học về độ chính xác detector**.

---

## 2. Tuyên bố phương pháp dùng trong báo cáo

Đoạn sau có thể dùng gần như nguyên văn trong Chương 5:

> Do các bộ dữ liệu công khai BGL và HDFS không cung cấp đồng thời system metrics và nhãn sự cố tương ứng, nghiên cứu giới hạn đánh giá định lượng ở dữ liệu log có ground truth công khai. Các feature liên quan CPU, memory, disk I/O và network vẫn thuộc kiến trúc LogSentry ở chế độ realtime, nhưng không được sử dụng để tính Precision, Recall và F1-score nhằm tránh suy diễn hoặc tự tạo dữ liệu metrics từ nhãn anomaly. Các kết quả fusion trong thí nghiệm được hiểu là log-only fusion, tức là hợp nhất các detector có dữ liệu đầu vào phù hợp trên từng benchmark.

Khi bị hỏi vì sao không có metric benchmark, câu trả lời là: **không tạo metrics giả để làm đầy feature vector vì điều đó làm mất tính độc lập giữa input và ground truth, dẫn đến circular validation.**

---

## 3. Quy tắc khoa học không được vi phạm

### 3.1. Không để nhãn rò rỉ vào input

Không được dùng trực tiếp hoặc gián tiếp các cột sau làm feature/model input:

- BGL: `Label`, alert category suy ra từ `Label`, hoặc biến đổi `Label != '-'` thành `ERROR`.
- HDFS: `Label`, `Type` nếu nó mô tả lỗi đã biết, `BlockId`.

Được dùng các trường quan sát được trước khi biết sự cố:

- BGL: timestamp, node, component/type gốc, level gốc, content, event ID/template.
- HDFS: chuỗi EventId, độ dài trace, occurrence count của EventId, time interval/latency nếu dùng nhưng không lấy label/type.

### 3.2. Không nhìn test set khi thiết kế model

Phân chia dữ liệu theo thứ tự thời gian/dòng log:

```text
Train       60–70% đầu tiên
Validation  10–20% tiếp theo
Test        20% cuối cùng
```

- Train dùng để fit baseline/model.
- Validation dùng để chọn threshold, rule threshold, fusion weights/minimum votes.
- Test chỉ chạy sau khi mọi config đã khóa.

Không random shuffle trước khi split. Không dùng test labels để chọn feature, hyperparameter, threshold hoặc “thử đến khi đẹp”.

### 3.3. Train normal-only cho anomaly model

Với Isolation Forest và DeepLog, baseline train chính thức là các sample normal thuộc train split.

```text
train_normal = train samples có ground truth normal
```

Nhãn được sử dụng để chọn subset normal trong giai đoạn offline benchmark; cần ghi rõ đây là one-class evaluation protocol. Nhãn test tuyệt đối không được dùng để fit model.

### 3.4. Không ép detector không phù hợp

Nếu dataset không có input cần thiết, detector ghi **N/A** kèm lý do. Không tự sinh feature để có đủ bốn cột score.

| Detector | BGL | HDFS | Lý do |
|---|---|---|---|
| Rule log-only | Có | Có | hạng mục bắt buộc; dựa trên volume/template/trace feature có trước nhãn |
| Isolation Forest | Có | Có | log-feature hoặc event-occurrence vector |
| DeepLog | Có | Có | EventId/template sequence |
| VAR | Có điều kiện | N/A mặc định | BGL có timestamp; HDFS benchmark là block trace, không phải time series liên tục |
| Fusion | Có, các detector khả dụng | Có, các detector khả dụng | luôn đặt tên log-only fusion |

---

## 4. Dataset và đơn vị đánh giá

### 4.1. BGL 2k

Đường dẫn nguồn:

```text
Dataset/BGL/BGL_2k.log_structured.csv
```

Kiểm tra hiện tại:

- 2.000 dòng log.
- 1.857 dòng nhãn normal (`-`).
- 143 dòng alert/anomaly (7,15%), thuộc nhiều category.
- Có `Timestamp`, `Node`, `Level`, `Content`, `EventId`, `EventTemplate`, `Label`.

**Đơn vị đánh giá chính:** event-count window gồm 20 log liên tiếp, không overlap ở phiên bản đầu.

Lý do: dữ liệu BGL 2k trải trên khoảng thời gian rất thưa; window 1 phút sẽ tạo quá nhiều window trống. Event-count window giữ được mật độ sequence để đánh giá log behavior. Đây là adaptation phục vụ benchmark, không thay đổi cách worker realtime production vẫn dùng time window.

Nhãn window:

```text
window_anomaly = 1 nếu trong window có ít nhất một dòng có Label != '-'
window_anomaly = 0 nếu tất cả dòng trong window có Label == '-'
```

Tất cả log của window vẫn là input; nhãn chỉ dùng sau đó để đo prediction.

**Thử nghiệm phụ trợ (không phải bảng chính):** time window theo ngày hoặc theo giờ, để quan sát log volume/time trend. Chỉ giữ nếu tạo đủ sample không rỗng và có ý nghĩa.

### 4.2. HDFS v1

Đường dẫn nguồn chính:

```text
Dataset/HDFS_v1/preprocessed/Event_traces.csv
Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv
Dataset/HDFS_v1/preprocessed/anomaly_label.csv
```

Kiểm tra hiện tại:

- 575.061 block traces.
- 558.223 normal; 16.838 anomaly (khoảng 2,93%).
- HDFS ground truth gán theo `BlockId`/trace, không phải theo time window.

**Đơn vị đánh giá:** một block trace là một sample. Không gộp trace thành time window, vì sẽ làm sai semantics của nhãn gốc.

Không dùng raw `HDFS.log` 1,58 GB ở vòng đầu. Preprocessed files chứa chính xác event sequence và occurrence matrix đủ cho DeepLog/IF, giúp thí nghiệm nhanh, tái lập và ít rủi ro parser.

---

## 5. Cấu trúc code và artifact đề xuất

Tạo code benchmark độc lập; không sửa trực tiếp worker realtime để phục vụ dataset research.

```text
evaluation/
  README.md
  evaluation_protocol.md
  config/
    bgl_v1.yaml
    hdfs_v1.yaml
  adapters/
    bgl_adapter.py
    hdfs_adapter.py
  features/
    log_only_features.py
  runners/
    run_bgl.py
    run_hdfs.py
    run_all.py
  reports/
    bgl/
    hdfs/
  tests/
    test_no_label_leakage.py
    test_bgl_adapter.py
    test_hdfs_adapter.py

data/processed/evaluation/
  bgl_v1/
  hdfs_v1/
```

Mỗi lần chạy phải tạo thư mục versioned, ví dụ `data/processed/evaluation/bgl_v1/`, gồm:

```text
manifest.json             dataset hash, commit hash, timestamp, random seed
split.csv                 sample_id, split; không đổi qua các lần chạy
features_train.parquet
features_validation.parquet
features_test.parquet
predictions.csv           score/prediction mọi detector và fusion
metrics.json              TP, FP, TN, FN, P/R/F1
confusion_matrices.csv
run_config.yaml
models/                   scaler, IF model, DeepLog model, metadata
figures/                  figure dùng cho báo cáo
```

`Dataset/` là input chỉ đọc. Không ghi output, cache, model hoặc file đã chuẩn hóa vào đó.

---

## 6. Data contract chung

Trước khi chạy detector, adapter phải tạo hai dạng dữ liệu.

### 6.1. Log event contract

```text
event_id                 ID duy nhất của log gốc
timestamp                thời gian nếu dataset có
host                     node/host nếu có
service                  component/type nếu có
level                    level gốc, không suy diễn từ label
message                  raw content
template_id              EventId/template ID
template                 EventTemplate
ground_truth             chỉ phục vụ split/evaluation, không phải feature
```

### 6.2. Sample contract

```text
sample_id                bgl_window_000001 hoặc hdfs_block_<id>
dataset                  BGL hoặc HDFS
split                    train, validation, test
ground_truth             0/1
sequence                 danh sách EventId/template ID
features                 vector numeric, không có label/ID
```

### 6.3. Prediction contract

Mọi detector phải trả cùng schema:

```text
sample_id
dataset
split
ground_truth
detector
raw_score
normalized_score
threshold
prediction
reason
model_version
config_version
```

Fusion chỉ dùng `normalized_score`/`prediction` từ detector đã hoàn thành tuning trên validation.

---

## 7. Giai đoạn A — Triển khai BGL

### A1. Viết BGL adapter

Input là `BGL_2k.log_structured.csv`. Map fields như sau:

| LogSentry benchmark field | BGL source field |
|---|---|
| `timestamp` | `Timestamp` chuyển từ epoch seconds |
| `host` | `Node` |
| `service` | `Component` hoặc `Type` |
| `level` | `Level` gốc |
| `message` | `Content` |
| `template_id` | `EventId` |
| `template` | `EventTemplate` |
| `ground_truth` | `Label != '-'` |

Kiểm tra adapter:

- Đủ 2.000 events sau parse.
- `ground_truth.sum() == 143`.
- Không cột feature nào tên/chứa `Label` hoặc category label.
- Timestamp tăng dần; nếu không, sort một lần và lưu thứ tự.

### A2. Tạo BGL event-count windows

Config v1:

```text
window_size = 20 events
stride = 20 events
```

Expected: khoảng 100 sample windows. Sau aggregation, in ra:

- số window normal/anomaly;
- số event trung bình/window;
- tỷ lệ anomaly window;
- số template/host/component unique.

Nếu test split có quá ít positive sample để metric ổn định, chỉ được thay window size/stride **trước khi nhìn performance detector**. Lý do và config mới phải ghi trong protocol. Không chọn window size theo F1 test.

### A3. Feature log-only BGL

Phiên bản v1 nên tối giản, giải thích được:

```text
total_logs
unique_templates
template_entropy
top_template_ratio
unique_hosts
unique_services_or_components
info_count
warn_count
error_count             chỉ theo Level gốc
message_length_mean
message_length_std
interarrival_time_mean  nếu timestamp hợp lệ
interarrival_time_std
template frequency vector (fit vocabulary từ train)
```

Không dùng raw label, anomaly category, hoặc bất cứ count nào phân loại dựa trên label.

### A4. Split BGL

Chia theo thứ tự sample/window:

```text
60% train
20% validation
20% test
```

Ngay sau khi chia, tạo `split.csv` và không thay đổi file này trong toàn bộ v1 benchmark.

Kiểm tra bắt buộc:

- Test có cả normal và anomaly.
- Validation có ít nhất một số anomaly để chọn threshold.
- Nếu một split không đủ anomaly, điều chỉnh boundary có giải trình trước khi train model; sau đó đóng băng split.

### A5. Rule-based log-only BGL

Rule runtime hiện tại dựa chủ yếu vào `error_count`, CPU và memory, nên không phù hợp nguyên trạng với BGL/HDFS log-only (thiếu metrics, và level gốc có thể không phản ánh alert label). Đây là **hạng mục bắt buộc trước benchmark final**. Giữ nguyên `src/detectors/rule_based.py` cho realtime; tạo detector benchmark riêng `evaluation/detectors/log_only_rule.py` với class `LogOnlyRuleDetector`. Cách này không thay đổi behavior hay rủi ro regression cho hệ thống Flask đang chạy.

Contract đề xuất:

```python
detector = LogOnlyRuleDetector(config=rule_config)
result = detector.detect(log_only_features)
```

Detector log-only chỉ được đọc cột thuộc allow-list benchmark. Nếu thiếu feature cần cho một rule, detector phải báo lỗi cấu hình rõ ràng, không âm thầm thay bằng 0.

Rule v1 không dùng nhãn. Chỉ định nghĩa từ train normal và validation:

- `total_logs` vượt percentile 99 của train normal.
- `template_entropy` lệch đáng kể khỏi dải train normal.
- tỷ trọng một template hiếm vượt threshold.
- xuất hiện template chưa thấy trong train normal.

**Kiểm thử bắt buộc cho detector mới:**

- `RuleBasedDetector` realtime vẫn giữ nguyên kết quả trên fixture có CPU/memory/error count.
- `LogOnlyRuleDetector` không yêu cầu CPU/memory/network.
- `LogOnlyRuleDetector` từ chối `Label`, `Type`, `BlockId`, `ground_truth` trong input feature.
- Mỗi prediction log-only có ít nhất một `reason` đọc được.

Lưu các threshold, percentile và reason vào config. Rule có thể score theo số điều kiện thỏa, nhưng score phải được normalize 0–1 rõ ràng.

### A6. Isolation Forest BGL

1. Fit vocabulary/template columns chỉ bằng train normal.
2. Fit scaler chỉ bằng train normal.
3. Fit Isolation Forest chỉ bằng train normal.
4. Dự đoán validation; chọn anomaly threshold trên validation theo mục tiêu đã công bố.
5. Khóa scaler, feature list, model và threshold.
6. Chạy test đúng một lần để sinh prediction chính thức.

`contamination` không được suy ra từ tỷ lệ anomaly test. Có thể chọn grid nhỏ trên validation hoặc đặt một prior rõ ràng rồi ghi lại.

### A7. DeepLog BGL

Input sequence chính thức là `EventId`, không phải raw message. Điều này dùng template được Loghub cấu trúc sẵn và tránh vocabulary bùng nổ bởi ID/number.

1. Chỉ lấy event trong train normal để train sequence model.
2. Dùng sequence length cố định, ví dụ 5 hoặc 10; chốt bằng validation.
3. Prediction score là độ bất ngờ/`1 - confidence` của event tiếp theo, rồi aggregate thành window score theo `max` hoặc percentile cao.
4. Chọn threshold bằng validation; không chỉnh bằng test.
5. Lưu model, vocabulary, sequence length, aggregation method và threshold.

### A8. VAR BGL — điều kiện chạy

VAR chỉ chạy nếu time-series samples từ BGL có độ đều/dày đủ. Dùng các series log-only như `total_logs`, entropy, template ratio; không đưa metrics giả.

Kiểm tra sơ bộ BGL 2k cho thấy 2.000 events chỉ nằm trên 166 ngày hoạt động trong 215 ngày lịch, median chỉ 3 log/ngày và chỉ 35 ngày chứa anomaly. Vì timestamp có lỗ hổng và phần lớn day windows rất thưa, **VAR là N/A mặc định trong BGL v1**. Chỉ mở lại VAR như một experiment phụ nếu data-quality gate chứng minh được một cách resample không tạo zero/missing giả và đủ support cho train/validation/test.

Nếu sequence thưa hoặc số sample không đủ để fit ổn định, kết quả chính thức là:

```text
VAR: N/A trên BGL v1 vì 2.000 log phân bố thưa theo thời gian,
không đủ chuỗi đều để đánh giá VAR đáng tin cậy.
```

Đây là quyết định đúng về phương pháp, không phải thất bại.

### A9. Log-only fusion BGL

Chỉ fusion Rule + IF + DeepLog (+ VAR nếu đạt điều kiện). Weights/min_votes được chọn toàn bộ trên validation.

Lưu rõ:

```text
available_detectors
weights
min_votes
score threshold
severity thresholds
config version
```

Không dùng weights trong README/worker production một cách mặc định; benchmark config phải độc lập, versioned và tái lập được.

---

## 8. Giai đoạn B — Triển khai HDFS

### B1. Viết HDFS adapter

Input chính:

- `Event_traces.csv`: sequence EventId theo block.
- `Event_occurrence_matrix.csv`: count EventId theo block.

Map output:

| Benchmark field | HDFS source |
|---|---|
| `sample_id` | `BlockId` |
| `sequence` | `Features` parse thành list EventId |
| `features` | `E1...E29` occurrence count và derived features |
| `ground_truth` | `Label == 'Anomaly'` |

Không dùng `Type` làm input. `BlockId` chỉ là ID join/report, không là feature.

### B2. Chia HDFS

Do dữ liệu lớn, chạy hai mức.

**Smoke benchmark v1:**

```text
train normal: 20.000 traces đầu tiên đủ điều kiện
validation: 5.000 traces tiếp theo
test: 10.000 traces tiếp theo
```

**Final benchmark:**

```text
70% train
10% validation
20% test
```

Split theo thứ tự record gốc hoặc thứ tự thời gian đã xác minh. Không random split.

Nếu test đầu tiên không có đủ anomaly vì thứ tự label quá lệch, tạo deterministic stratified temporal block split và ghi chính xác algorithm/seed. Không chọn test slice theo detector performance.

### B3. Isolation Forest HDFS

Input: E1–E29 occurrence counts + derived feature như trace length, unique event count, entropy event count.

Quy trình training/threshold giống BGL:

```text
fit vocabulary/scaler/model trên train normal
→ chọn threshold trên validation
→ khóa artifact
→ đo trên test
```

### B4. DeepLog HDFS

Input: `Features` sequence EventId theo block. Đây là benchmark sequence chính của dự án.

- Train bằng normal traces của train split.
- Padding/truncation phải thống nhất; ghi max sequence length.
- Score per trace cần strategy cụ thể: max surprisal hoặc percentile 95 của next-event anomaly score.
- Chọn score threshold ở validation.
- Lưu confusion matrix theo block trace trên test.

### B5. Rule và fusion HDFS

Rule chỉ được thêm sau khi định nghĩa feature/threshold không dùng `Label`/`Type`, ví dụ template unseen, trace length outlier, entropy outlier. Nếu rule chưa đủ căn cứ, report HDFS v1 chỉ gồm IF + DeepLog.

Fusion HDFS chỉ có ý nghĩa nếu có ít nhất hai detector độc lập. Nếu chỉ IF/DeepLog khả dụng, log-only fusion là 2-detector fusion; ghi rõ điều này.

VAR mặc định `N/A` vì HDFS v1 benchmark phân loại theo block trace, không cung cấp time-series window đều.

---

## 9. Calibration, threshold và fusion protocol

### 9.1. Raw score không là probability

Rule score, IF score, VAR residual và DeepLog surprise có ý nghĩa khác nhau. Không cộng raw score trực tiếp.

Mỗi detector cần:

```text
raw_score
→ normalization fit từ train/validation
→ normalized_score 0..1
→ threshold
→ prediction 0/1
```

Nếu chưa có calibration probability đúng nghĩa, gọi kết quả là `normalized anomaly score`, không gọi là xác suất incident.

### 9.2. Chọn threshold

Chọn một policy trước khi chạy:

```text
Policy A: threshold tối đa F1-score trên validation.
Policy B: threshold đạt recall >= 0.80, sau đó tối đa precision.
```

Khuyến nghị v1: Policy A cho tính đơn giản, đồng thời báo cáo precision/recall để tránh chỉ tối ưu một phía.

### 9.3. Chọn fusion config

1. Chọn detector khả dụng cho dataset.
2. Thử grid weights nhỏ và `min_votes` trên validation.
3. Chọn config bằng policy đã công bố.
4. Lưu YAML config; không thay sau khi thấy test result.
5. Chạy test một lần.

Nếu muốn giảm khả năng overfit validation, ưu tiên weights đều ở v1; chỉ tối ưu weights khi có đủ validation positives.

---

## 10. Metrics, báo cáo và tiêu chí kết quả hợp lệ

### 10.1. Metrics bắt buộc

Với mỗi detector khả dụng và fusion:

```text
TP, FP, TN, FN
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1-score  = 2 * Precision * Recall / (Precision + Recall)
Support normal, support anomaly
```

Kèm theo:

- confusion matrix;
- threshold; config version; feature list;
- thời gian train và inference;
- số sample/số anomaly ở mỗi split.

Không dùng accuracy là chỉ số chính vì anomaly hiếm.

### 10.2. Bảng kết quả chính thức

| Dataset | Đơn vị | Detector | Precision | Recall | F1 | Support anomaly | Ghi chú |
|---|---|---|---:|---:|---:|---:|---|
| BGL | event-count window | Rule log-only | | | | | |
| BGL | event-count window | Isolation Forest | | | | | |
| BGL | event-count window | DeepLog | | | | | |
| BGL | event-count window | VAR | N/A hoặc số liệu | | | | điều kiện time-series |
| BGL | event-count window | Log-only fusion | | | | | detector khả dụng |
| HDFS | block trace | Rule log-only | | | | | |
| HDFS | block trace | Isolation Forest | | | | | occurrence matrix |
| HDFS | block trace | DeepLog | | | | | EventId sequence |
| HDFS | block trace | VAR | N/A | | | | không phải time series |
| HDFS | block trace | Log-only fusion | | | | | detector khả dụng |

### 10.3. Không so sánh sai ngữ cảnh

- Không khẳng định BGL window F1 và HDFS trace F1 là cùng một bài toán.
- Không lấy trung bình hai F1 thành “F1 toàn hệ thống”.
- Không so sánh với paper gốc nếu protocol/đơn vị sample/split khác paper đó.
- Không gọi kết quả log-only là performance của production multi-modal deployment.

---

## 11. Kiểm thử bắt buộc trước benchmark

### Unit test

- BGL adapter giữ đúng 2.000 dòng và 143 positive lines.
- HDFS adapter parse được sequence và occurrence count; không có `Label`, `Type`, `BlockId` trong model feature columns.
- Window label BGL đúng: bất kỳ positive event nào làm window positive.
- Split không overlap sample ID; thứ tự train < validation < test.
- Feature vocabulary/scaler fit chỉ từ train normal.
- Metric calculator kiểm tra đúng TP/FP/TN/FN với fixture nhỏ.
- Fusion tính đúng vote/score với input định trước.

### Integration test

Chạy BGL mini subset từ adapter → feature → IF → prediction → metric CSV. Test này phải chạy được không cần Flask server, shipper, database hoặc GPU.

### Leakage audit

Trước final run, in và lưu:

```text
feature_columns
model input shape
label columns excluded
train/validation/test sample counts
normal/anomaly counts by split
```

Nếu `Label`, `Type`, `BlockId`, `ground_truth` xuất hiện trong feature columns: dừng benchmark và sửa trước khi chạy tiếp.

---

## 12. Trình tự thực hiện và Definition of Done

### Tuần tự bắt buộc

1. Tạo `evaluation/` và `evaluation_protocol.md`.
2. Viết/kiểm thử BGL adapter.
3. Tạo BGL windows, split cố định và leakage audit.
4. Tạo và unit-test `LogOnlyRuleDetector` trong evaluation; không thay đổi `RuleBasedDetector` realtime.
5. Chạy Rule log-only + IF BGL.
6. Chạy DeepLog BGL.
7. Quyết định VAR BGL theo điều kiện dữ liệu; chạy hoặc ghi N/A.
8. Tune fusion Rule + IF + DeepLog trên BGL validation, chạy BGL test, khóa report.
9. Viết/kiểm thử HDFS adapter trên smoke subset.
10. Chạy Rule + IF + DeepLog HDFS smoke benchmark.
11. Chạy HDFS final benchmark khi mọi test pass.
12. Sinh tables/figures/metrics artifacts.
13. Cập nhật Chương 5 và Chương 6 theo kết quả đã khóa.
14. Chạy synthetic realtime demo riêng để lấy ảnh kiến trúc/dashboard, không trộn metric accuracy.

### Definition of Done cho BGL/HDFS

Một benchmark chỉ được gọi là hoàn thành khi toàn bộ điều sau đúng:

- [ ] Dataset source, hash và version được lưu.
- [ ] Protocol, split và random seed được lưu.
- [ ] Không có label leakage trong model inputs.
- [ ] Train/validation/test không overlap.
- [ ] Model/scaler/feature vocabulary fit từ train normal.
- [ ] Threshold và fusion config chọn bằng validation.
- [ ] Test predictions, metrics và confusion matrix đã được lưu.
- [ ] Mỗi số trong báo cáo có thể tái tạo bằng một lệnh runner.
- [ ] Detector không phù hợp ghi N/A cùng lý do phương pháp.
- [ ] Chương 5 phân biệt rõ benchmark public và synthetic integration test.

---

## 13. Các bước triển khai chi tiết và phương án kỹ thuật

Phần này chuyển protocol thành các công việc code cụ thể. Không chạy final benchmark cho đến khi hoàn tất các checkpoint của từng bước.

### Bước 1 — Đóng băng môi trường và dữ liệu đầu vào

**Mục đích:** một kết quả phải biết chính xác nó được tạo bằng source, dataset và thư viện nào.

Việc cần làm:

1. Tạo một branch riêng, ví dụ `codex/log-only-evaluation`.
2. Ghi Python version, package version (`pandas`, `numpy`, `scikit-learn`, `tensorflow`) vào `evaluation/README.md` hoặc `manifest.json`.
3. Không chỉnh sửa file bên trong `Dataset/`.
4. Tính SHA-256 cho ba input chính: BGL structured CSV, HDFS Event traces, HDFS occurrence matrix.
5. Quy định random seed chung: `42` cho numpy, scikit-learn và TensorFlow.
6. Đưa mọi hyperparameter vào YAML, không rải literal numbers trong code runner.

**Phương án:**

- **A — YAML config, khuyến nghị:** `bgl_v1.yaml`/`hdfs_v1.yaml` chứa split, feature, threshold policy, model config. Dễ tái lập và so sánh experiment.
- **B — argparse thuần:** nhanh cho prototype, nhưng dễ quên command đã chạy. Chỉ dùng trong exploration; final run phải export lại config đầy đủ.

**Checkpoint:** chạy cùng runner và config hai lần phải tạo split/sample ID giống hệt nhau.

### Bước 2 — Xây adapter có kiểm soát leakage

Adapter chỉ làm nhiệm vụ chuyển dataset public thành contract chung; nó không train model, không chọn threshold và không tính F1.

#### BGL adapter

Thiết kế hàm:

```python
load_bgl_events(path) -> DataFrame
make_bgl_event_windows(events, size=20, stride=20) -> DataFrame
```

Adapter trả events có `ground_truth`, nhưng `make_feature_matrix()` phải nhận danh sách cột allow-list thay vì nhận toàn bộ DataFrame. Ví dụ:

```python
ALLOWED_BGL_INPUT = [
    "timestamp", "host", "service", "level", "message",
    "template_id", "template"
]
```

`Label` chỉ tồn tại trong object evaluation/result, không đi vào feature transformer.

#### HDFS adapter

Thiết kế hàm:

```python
load_hdfs_traces(event_traces_path, occurrence_path) -> DataFrame
parse_event_sequence(features_text) -> list[str]
```

Từ `Event_occurrence_matrix.csv`, chỉ select các cột có regex `^E\d+$`. `BlockId`, `Label`, `Type` phải nằm trong metadata, không nằm trong `X`.

**Phương án chống leakage:**

- **A — allow-list, khuyến nghị:** chỉ đưa các cột được liệt kê tường minh vào model.
- **B — deny-list:** loại `Label`, `Type`, `BlockId`. Không đủ an toàn vì file dataset tương lai có thể thêm cột leakage mới.

**Checkpoint:** unit test assert mọi tên feature không chứa `label`, `ground_truth`, `type`, `blockid` hoặc `id` định danh.

### Bước 3 — Tạo sample và nhãn evaluation trước khi feature engineering

#### BGL: event-count window

1. Sort events theo timestamp rồi reset index.
2. Gom tuần tự 20 event thành 1 window không overlap ở v1.
3. Sinh `sample_id = bgl_window_{index:06d}`.
4. Tạo sequence EventId và statistics raw cho từng window.
5. Gán ground truth window theo quy tắc OR: có một event anomaly là window anomaly.
6. Lưu bảng `bgl_samples_v1.csv` chứa sample ID, event range, timestamp range, label; không có prediction.

**Các phương án window:**

| Phương án | Khi dùng | Ưu điểm | Rủi ro |
|---|---|---|---|
| 20 event, non-overlap | v1 chính thức | đơn giản, không duplicate event giữa samples | số sample chỉ khoảng 100 |
| 10 event, non-overlap | khi validation/test ít positive | tăng số sample | context DeepLog ngắn hơn |
| sliding window | chỉ experiment phụ | nhiều sample, bắt anomaly gần điểm xuất hiện | correlation rất cao, dễ leakage giữa split |
| time window | analysis phụ | gần production worker | BGL 2k quá thưa, nhiều window rỗng |

**Quyết định v1:** bắt đầu 20 event non-overlap. Nếu test hoặc validation có quá ít positive sample, chuyển sang 10 event non-overlap trước khi train bất kỳ detector nào và ghi lại lý do. Không dùng sliding window trong benchmark v1 vì split rất dễ overlap event.

#### HDFS: block trace

1. Mỗi `BlockId` là một sample.
2. Parse `Features` thành list EventId; kiểm tra parser không biến một EventId thành nhiều token sai.
3. Join trace và occurrence matrix bằng `BlockId`.
4. Dùng `Label == 'Anomaly'` chỉ để tạo `ground_truth` 0/1.
5. Lưu sample metadata, sequence length, event-count features và ground truth.

**Checkpoint:** số sample sau join phải được log; mọi mismatch BlockId phải được report/dừng, không âm thầm drop.

### Bước 4 — Thiết kế split không có overlap

#### BGL split

Vì BGL window không overlap, split theo thứ tự window là đủ:

```text
0 .. 59%       train
60% .. 79%     validation
80% .. 100%    test
```

Trước khi model train, in bảng class distribution. Nếu validation/test không có positive:

1. Không đổi random seed để “tìm split đẹp”.
2. Chọn một boundary theo chronological blocks sao cho mỗi split có support anomaly tối thiểu đã định trước, ví dụ >= 10 positives nếu data cho phép.
3. Ghi boundary mới vào YAML và giải thích do class rarity/time concentration.
4. Lưu `split.csv` và không đổi nữa.

#### HDFS split

HDFS có 575k trace và class imbalance rõ. Có hai phương án:

- **A — chronological/index split, ưu tiên nếu sequence gốc giữ ý nghĩa thứ tự:** 70/10/20 theo thứ tự record. Đây là gần production nhất.
- **B — deterministic stratified split, fallback:** áp dụng khi index split khiến validation/test quá ít anomaly. Dùng `train_test_split(..., stratify=y, random_state=42)` sau khi đã ghi rõ là không có timestamp/trật tự session đáng tin trong artifact preprocessed.

Chỉ chọn một phương án cho HDFS v1. Nếu chọn B, không mô tả đó là temporal generalization; gọi đúng là benchmark stratified.

**Checkpoint:** `split.csv` có mỗi sample đúng một split; count normal/anomaly ở mỗi split; hash file split được ghi vào manifest.

### Bước 5 — Tạo feature transformers chỉ fit trên train

Tách rõ hai thao tác:

```text
fit(train_normal)
transform(train / validation / test)
```

Không được gọi `fit_transform()` trên concatenation cả ba split.

#### Feature cho Isolation Forest

**BGL:** count vector EventId/template của vocabulary từ train normal; thêm entropy, unique template, log level count, interarrival statistics.

**HDFS:** E1..E29 occurrence counts; thêm trace length, number of non-zero templates, entropy event count. Không đưa raw `BlockId`/`Type`.

**Scaling:** dùng `StandardScaler` hoặc `RobustScaler` fit train normal. Với count skew lớn, thử `log1p` trước scaling và quyết định bằng validation.

**Phương án vector template BGL:**

- **A — count vector, khuyến nghị v1:** dễ giải thích, stable với data nhỏ.
- **B — TF-IDF:** phù hợp document-like logs nhưng ít trực quan hơn ở level window.
- **C — embedding:** không ưu tiên; tăng độ phức tạp mà chưa cần cho mục tiêu bảo vệ.

**Checkpoint:** metadata model lưu đúng feature order, vocabulary và scaler; khi transform test, số cột phải hoàn toàn giống train.

### Bước 6 — Chạy Rule log-only trước để có baseline giải thích được

Rule phải là policy có thể mô tả bằng câu, không phải rule ngầm học từ test data.

#### Rule v1 đề xuất

- Template unseen: EventId/template không xuất hiện trong train normal.
- Template entropy cao/thấp bất thường so với percentile train normal.
- Trace/window length vượt percentile 99 train normal.
- Tỷ trọng dominant template hoặc rare-template count vượt ngưỡng train normal.

**Không dùng:** từ khóa được chọn sau khi đọc label test như `ERROR`, `FATAL`, `anomaly` nếu chúng vô tình mã hóa nhãn dataset. Có thể dùng level gốc hoặc content keyword chỉ khi được định nghĩa trước từ kiến thức domain và áp dụng bình đẳng cho mọi split.

**Phương án score rule:**

- **A — fraction of triggered rules, khuyến nghị:** số rule thỏa / tổng rule; đã ở scale 0–1.
- **B — weight thủ công:** chỉ dùng nếu có lý do domain rõ; mọi weight phải khóa trước test.

Threshold rule và percentile được chọn/tune trên validation. Lưu `reason` theo sample để đưa vào phần thảo luận.

### Bước 7 — Isolation Forest: one-class baseline đúng protocol

Quy trình v1:

1. Lấy `X_train_normal` sau transformer/scaler.
2. Train một IF với seed cố định.
3. Lấy raw anomaly score trên validation.
4. Normalize score theo empirical percentile hoặc min/max của train/validation đã khóa.
5. Chọn threshold validation theo policy F1 hoặc recall constraint.
6. Lưu model, scaler, threshold, raw score direction và feature metadata.
7. Transform/predict test mà không gọi `.fit()` lại.

**Phương án hyperparameter:**

- `n_estimators`: 100 cho vòng nhanh, 300 cho final nếu runtime ổn.
- `max_samples`: `auto` ở v1.
- `contamination`: không coi là threshold cuối; dùng `auto` hoặc một prior cố định, rồi quyết định bằng score threshold validation.

Không grid-search rộng trên dataset nhỏ. Tối đa 3–4 config được định nghĩa trước ở validation; chọn một config duy nhất, lưu kết quả mọi config.

### Bước 8 — DeepLog: sequence benchmark đúng nghĩa

#### BGL

Sequence là EventId trong mỗi window hoặc across events trong từng chronological split. Không tạo sequence bắc cầu giữa train và validation/test; sequence tại đầu split cần đủ context nội bộ hoặc bị loại bỏ theo quy tắc rõ ràng.

#### HDFS

Sequence là EventId trong một block trace. Đây là setting tự nhiên hơn và là benchmark DeepLog trọng tâm.

Quy trình:

1. Build vocabulary chỉ từ train normal sequence; thêm token `UNK` cho event không thấy khi inference.
2. Chọn sequence length 5 hoặc 10 bằng validation.
3. Train LSTM chỉ trên normal train sequence.
4. Tính next-event surprise per position (`1 - confidence` hoặc `-log probability`).
5. Aggregate score per sample bằng `max` hoặc percentile 95; chọn một phương án bằng validation.
6. Chọn threshold validation; khóa model/vocab/threshold; chạy test.

**Phương án DeepLog khi TensorFlow không ổn định hoặc quá chậm:**

- **A — LSTM hiện có, ưu tiên final benchmark:** khớp mục tiêu dự án.
- **B — n-gram/Markov next-event baseline:** dùng để smoke test adapter/sequence và đối chiếu, không thay thế DeepLog trong kết luận nếu LSTM chạy được.

Phương án B hữu ích vì nếu LSTM score bất thường, bạn biết lỗi nằm ở data pipeline hay model training.

### Bước 9 — Quyết định VAR bằng gate kỹ thuật

Trước khi code VAR, kiểm tra:

```text
- Có ít nhất 50 sample theo thời gian?
- Timestamp có khoảng cách đều hoặc đã resample hợp lệ?
- Mỗi sample có đủ nhiều log để feature có nghĩa?
- Validation/test có positive support?
```

Nếu một điều kiện không đạt, VAR là `N/A` cho benchmark đó. Không cố resample BGL thành hàng nghìn zero-window để “có time series”; điều đó chỉ tạo synthetic structure.

Nếu BGL đạt gate sau thử nghiệm daily/hourly aggregation, VAR dùng log-only series và được tune/đánh giá đúng train-validation-test như IF.

### Bước 10 — Normalize score và fusion

Đừng gọi mọi giá trị 0–1 là probability. V1 dùng cụm từ **normalized anomaly score**.

#### Normalization v1

- Rule: score đã là fraction rules triggered.
- IF: map raw score thành percentile anomaly score dựa trên distribution train/validation.
- DeepLog: aggregate surprise rồi percentile-scale bằng train normal/validation.
- VAR: normalized residual score nếu có.

#### Fusion v1

1. Tạo table validation chứa score/prediction mọi detector khả dụng.
2. Chọn một baseline weights bằng nhau.
3. Thử tối đa vài cấu hình weights/min-votes đã viết trước trong YAML.
4. Chọn config bằng validation F1 hoặc recall policy.
5. Đóng băng config; test chỉ dùng config này.

**Phương án fusion:**

- **A — weighted mean normalized score + threshold, khuyến nghị:** đơn giản và giữ được tín hiệu liên tục.
- **B — min-votes:** dễ giải thích; cần ít nhất 2 detector để có ý nghĩa.
- **C — kết hợp A/B:** có thể, nhưng chỉ dùng nếu config được khóa trên validation và báo cáo rõ logic.

Tên output bắt buộc: `log_only_fusion`, không dùng `full_system_fusion`.

### Bước 11 — Tính metric, uncertainty và error analysis

Sau test final, sinh:

- `metrics.json`, confusion matrix, classification report;
- bảng TP/FP/TN/FN;
- distribution raw/normalized score theo ground truth;
- danh sách 10 FP score cao và 10 FN score cao nhất.

Vì BGL chỉ có khoảng 100 non-overlap windows, F1 có thể biến động mạnh. Báo cáo support và cân nhắc thêm 95% bootstrap confidence interval cho F1/precision/recall nếu thời gian cho phép.

**Phương án confidence interval:**

- **A — bootstrap test samples 1.000 lần:** khuyến nghị nếu implement được; ghi CI 95%.
- **B — không thêm CI:** chấp nhận được với deadline ngắn, nhưng phải nêu support/sample size và không overclaim.

Error analysis cần trả lời: false positive là log pattern lạ nhưng nhãn normal, hay do feature threshold? false negative bị bỏ sót vì anomaly event nằm trong window nhiều normal logs, hay vì vocab/template chưa thấy?

### Bước 12 — Đóng gói evidence cho báo cáo và bảo vệ

Mỗi figure/table báo cáo phải truy về một artifact cụ thể:

| Nội dung báo cáo | Artifact nguồn |
|---|---|
| Dataset size/label distribution | `manifest.json`, `split.csv` |
| P/R/F1 bảng chính | `metrics.json` |
| Confusion matrix | `figures/*.png` + `confusion_matrices.csv` |
| Threshold/weights | `run_config.yaml` |
| Ví dụ true/false prediction | `predictions.csv` + reasons |
| Runtime | `run_log.txt` hoặc benchmark JSON |

Không copy số thủ công vào Word rồi bỏ source. Khi rerun kết quả thay đổi, script report phải cập nhật cùng một nguồn.

---

## 14. Lịch triển khai gợi ý

| Ngày | Việc | Deliverable |
|---:|---|---|
| 1 | Protocol, folder, config, metric utility | `evaluation_protocol.md`, config v1 |
| 2 | BGL adapter, window, split, tests leakage | BGL processed dataset + tests pass |
| 3 | Rule + IF BGL | predictions validation/test + metric table |
| 4 | DeepLog BGL + log-only fusion | BGL final report v1 |
| 5 | HDFS adapter + smoke benchmark | HDFS subset report |
| 6 | HDFS full IF/DeepLog/fusion benchmark | HDFS final report v1 |
| 7 | Biểu đồ, Chương 5/6, synthetic E2E demo | evidence package cho báo cáo |

---

## 15. Câu trả lời ngắn khi bảo vệ

**Vì sao chỉ benchmark log?**

> BGL và HDFS có log cùng ground truth công khai, nhưng không có metrics hạ tầng đi kèm nhãn tương ứng. Để tránh tự tạo CPU/RAM theo nhãn và gây circular validation, nhóm đánh giá định lượng riêng các detector log-based. Metrics vẫn được kiểm chứng ở mức tích hợp realtime, không được dùng để tuyên bố F1.

**Vì sao BGL dùng event-count window thay time window production?**

> BGL 2k phân bố rất thưa qua thời gian dài; time window nhỏ tạo phần lớn sample rỗng. Event-count window là adaptation benchmark để tạo sample có đủ log context. Worker production vẫn vận hành bằng time window và được kiểm thử tích hợp riêng.

**Vì sao VAR có thể N/A?**

> VAR đòi hỏi chuỗi thời gian đều và đủ dài. HDFS benchmark là block trace được gán nhãn theo session, không phải chuỗi window thời gian. Ép VAR vào loại dữ liệu này sẽ cho số liệu không có ý nghĩa khoa học.

**Làm sao biết không có leakage?**

> Adapter loại bỏ hoàn toàn label/category/type/identifier khỏi feature matrix; split theo thứ tự trước khi train; model chỉ fit trên normal training data; threshold/weights chỉ chọn trên validation; test set chỉ dùng một lần cuối để báo cáo.

## Kết luận

Kế hoạch này chuyển trọng tâm từ “cố tạo đủ score cho mọi thành phần” sang “đưa ra các số liệu đúng ngữ cảnh, độc lập với ground truth và tái lập được”. Đó là cách mạnh nhất để giải quyết nguy cơ circular validation và bảo vệ độ tin cậy của LogSentry AI trước hội đồng.
