# HDFS v1 — Validation-only summary

Trạng thái: development checkpoint, 2026-09-07. Báo cáo này tóm tắt kết quả
trên validation để phục vụ tuning; **không phải** kết quả benchmark cuối.

## Protocol và niêm phong test

- Dataset HDFS v1 được chia theo source record order: 70% train, 10%
  validation, 20% test.
- Frozen split: `hdfs_v1_final_split_20260907/`, hash split
  `b99bd57ebab04302a286a28a3693e296c83e9de3cd93789ac0fb81fe7cc944ae`.
- Train có 402.542 trace (389.427 normal); validation có 57.506 trace, gồm
  2.044 anomaly.
- Test có 115.013 trace, nhưng nhãn test không được export và không detector
  nào score test trong các run dưới đây.
- Threshold của từng detector được chọn từ validation; không dùng metric test
  để chọn feature, hyperparameter, threshold hay fusion weight.

## Kết quả validation

| Detector | Train normal | Cấu hình checkpoint | Precision | Recall | F1 |
| --- | ---: | --- | ---: | ---: | ---: |
| Rule log-only | 389.427 | percentile 99, threshold 0,2 | 0,9973 | 0,3601 | 0,5291 |
| Isolation Forest | 389.427 | 100 trees, RobustScaler, threshold 0,7079119 | 0,9885 | 0,4628 | 0,6305 |
| DeepLog | 10.000 | LSTM streaming, sequence 10, 1 epoch, threshold 0,9998583 | 0,9975 | 0,7671 | 0,8673 |

Các metric trên cùng một validation split; `train normal` của DeepLog bị giới
hạn có chủ ý ở 10.000 trace theo source order để kiểm soát RAM/runtime. Giới
hạn này là một tham số development cần được tune trên validation, không phải
quyết định dựa trên test.

## Artifact và traceability

| Detector | Artifact validation-only | Commit runner |
| --- | --- | --- |
| Rule | `hdfs_v1_final_rule_checksum_20260907/` | `1c1835a` |
| Isolation Forest | `hdfs_v1_final_if_dev_20260907/` | `736f2bb` |
| DeepLog | `hdfs_v1_final_deeplog_dev_20260907/` | `6028508` |

Mỗi artifact có `manifest.json` với `test_scored=false` và
`test_labels_exported=false`; `predictions.csv` chỉ có `split=validation`.

## Diễn giải và bước tiếp theo

DeepLog là detector tốt nhất ở checkpoint hiện tại theo F1 validation.

### DeepLog train-size tuning v1

Giữ cố định split, seed, sequence length 10, LSTM 16/32, 1 epoch và validation;
chỉ đổi `train_normal_limit`. Selection metric được công bố trước là validation
F1.

| Normal train | Precision | Recall | F1 | Artifact |
| ---: | ---: | ---: | ---: | --- |
| 10.000 | 0,9975 | 0,7671 | 0,86726 | `hdfs_v1_final_deeplog_dev_20260907/` |
| 25.000 | 0,9727 | 0,7676 | 0,85808 | `hdfs_v1_final_deeplog_tune_25000_20260907/` |
| 50.000 | 0,9968 | 0,7676 | 0,86733 | `hdfs_v1_final_deeplog_tune_50000_20260907/` |

Theo F1, 50.000 là checkpoint tốt nhất nhưng chênh lệch với 10.000 là rất nhỏ
(0,00007); đây là lý do để cân nhắc runtime trước khi khóa lựa chọn. Không vòng
nào score test.

Các vòng tuning kế tiếp thay đổi một nhóm tham số mỗi lần, đo lại validation và
ghi config/seed/artifact. Fusion chỉ được thử sau khi chọn candidate
detector/weight hoàn toàn trên validation.

Khi tuning được chốt, cần đóng băng config/model hash và mới chạy test đúng một
lần để tạo báo cáo cuối. Không được dùng kết quả trong file này như metric test
hay tuyên bố độ chính xác cuối cùng.
