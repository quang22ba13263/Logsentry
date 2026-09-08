# BGL v1 — Kế hoạch tuning validation-only

## Trạng thái và ràng buộc

- Giữ nguyên event-count window 20, stride 20 và chronological split 60/20/20
  đã khóa. Không đổi window/split sau khi đã xem performance detector.
- BGL validation chỉ có 20 window, trong đó 8 anomaly; vì vậy grid phải nhỏ,
  được công bố trước và không thử tuỳ tiện đến khi F1 đẹp.
- Các artifact BGL test trước đây là diagnostic đã quan sát. Từ thời điểm này,
  mọi vòng tuning chỉ gọi runner development mode (không `--final-test`).
- Sau khi khóa config, lần test sau chỉ được báo cáo là **post-diagnostic
  confirmation**, không phải test chưa từng quan sát hoàn toàn.

## Baseline validation để so sánh

| Detector | Checkpoint hiện có | Validation F1 | Vấn đề chính |
| --- | --- | --- |
| Rule | percentile 99 | 0,5714 | score gần hằng 0,2; thường trigger unseen template |
| Isolation Forest | 100 trees | 0,7368 | detector duy nhất có score phân biệt rõ ở BGL v1 |
| DeepLog | sequence 10, max surprise | 0,5926 | UNK saturation, nhiều score gần 1,0 |
| Fusion | N/A | N/A | Chưa có ít nhất hai score discriminative |
| VAR | N/A | N/A | Chuỗi thời gian BGL quá thưa theo data-quality gate |

Các baseline là metric validation-only, không dùng để quyết định từ test.

## Vòng tuning được phép

### 1. Rule — chỉ calibration đã định trước

- `normal_percentile`: 95, 97, 99.
- Chọn threshold F1 trên validation theo cùng policy hiện tại.
- Không thay feature/window; nếu score vẫn hằng hoặc chỉ do `unseen_template`,
  ghi N/A cho fusion thay vì ép Rule vào fusion.

### 2. Isolation Forest — stability grid nhỏ

- `n_estimators`: 100, 200.
- Giữ feature transformer, RobustScaler, random seed 42 và train-normal cố
  định; threshold vẫn chọn trên validation.
- Chọn candidate bằng validation F1; nếu bằng nhau, ưu tiên ít cây hơn.

## Kết quả tuning đã thực hiện

### Rule percentile v1 — hoàn tất

| Percentile | Precision | Recall | F1 | Artifact |
| ---: | ---: | ---: | ---: | --- |
| 95 | 0,4000 | 1,0000 | 0,5714 | `bgl_rule_tune_p95_20260908/` |
| 97 | 0,4000 | 1,0000 | 0,5714 | `bgl_rule_tune_p97_20260908/` |
| 99 | 0,4000 | 1,0000 | 0,5714 | `bgl_dev_guard_20260907/` |

Mọi percentile chọn threshold validation 0,0 và dự báo cả 20 validation
window là anomaly. Vì vậy percentile không phải hướng cải thiện Rule BGL v1;
Rule không đủ score discriminative để làm candidate fusion hiện tại.

### Isolation Forest stability v1 — hoàn tất

| Trees | Precision | Recall | F1 | Artifact |
| ---: | ---: | ---: | ---: | --- |
| 100 | 0,6368 | 0,8750 | 0,7368 | `bgl_dev_guard_20260907/` |
| 200 | 0,6154 | 1,0000 | 0,7619 | `bgl_if_tune_200_20260908/` |

Theo validation F1, 200 trees là candidate IF hiện tại. Chênh lệch chỉ có 20
validation window, nên cần tránh mở grid lớn hơn ngoài kế hoạch đã khóa.

### 3. DeepLog — giảm UNK saturation

- `sequence_length`: 5, 10.
- Giữ EventId input, train-normal, seed 42 và max-surprise aggregation.
- Theo dõi tỷ lệ score bằng 1,0 và số UNK target trong validation. Không đổi
  UNK policy dựa trên test; chỉ cân nhắc policy mới nếu được version/test riêng.

### 4. Fusion gate

- Chỉ mở grid weight nếu ít nhất hai detector có nhiều hơn một mức score và
  có F1 validation dương sau các vòng trên.
- Grid weight cố định `[0; 0,25; 0,5; 0,75; 1]`, cần ít nhất hai weight dương;
  threshold chọn trên validation.
- Nếu gate không đạt: báo cáo `log-only fusion: N/A` là kết quả đúng.

## Tiêu chí dừng và đóng băng

1. Chạy mỗi cấu hình đúng một lần với run ID riêng, lưu config, manifest,
   prediction validation và P/R/F1.
2. Không mở thêm cấu hình ngoài grid này nếu không có lý do phương pháp mới
   được ghi thành protocol amendment.
3. Chọn một config/detector/fusion theo validation F1; khi hoà, ưu tiên cấu
   hình đơn giản hơn.
4. Ghi config hash, commit hash và threshold; chỉ sau đó mới cân nhắc một lần
   post-diagnostic confirmation trên BGL test.
