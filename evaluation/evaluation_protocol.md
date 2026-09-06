# Log-only evaluation protocol v1

Tài liệu chính sách đầy đủ nằm tại
[`KE_HOACH_DANH_GIA_LOG_ONLY_CHINH_THUC.md`](../KE_HOACH_DANH_GIA_LOG_ONLY_CHINH_THUC.md).
Tệp này là bản thực thi ngắn gọn, được runner và review dùng làm checklist.

## Bất biến bắt buộc

- `Dataset/` là input chỉ đọc; không ghi cache, output hay model vào đó.
- Feature/model input chỉ lấy từ allow-list quan sát được trước sự cố. Không
  dùng `Label`, `ground_truth`, anomaly category, HDFS `Type` hoặc `BlockId`.
- Split được tạo theo thứ tự trước train, lưu lại và không đổi trong v1.
- Transformer, vocabulary, scaler và anomaly model chỉ `fit` trên train-normal.
- Threshold, rule percentile và fusion weights chỉ chọn trên validation. Test
  chỉ dùng một lần để tạo kết quả chính thức.
- Điểm số fusion phải được gọi là `log_only_fusion`; detector thiếu input hợp lệ
  phải trả `N/A` cùng lý do, không được tạo metrics giả.

## BGL v1

- Input: `BGL_2k.log_structured.csv`, 2.000 events.
- Sample: 20 event liên tiếp, non-overlap; anomaly window khi có ít nhất một
  event `Label != '-'`.
- Split theo thứ tự sample: 60% train, 20% validation, 20% test.
- Detector bắt buộc: Rule log-only; Isolation Forest và DeepLog theo input hợp
  lệ. VAR mặc định N/A vì time series BGL thưa, trừ khi data-quality gate pass.

## HDFS v1

- Input: event traces và event occurrence matrix được ghi checksum trong README.
- Sample: một block trace; `BlockId` chỉ được giữ làm metadata/join key.
- Giai đoạn đầu dùng smoke split theo config; final split được khóa riêng sau
  khi adapter, leakage test và smoke benchmark pass.
- VAR N/A mặc định: nhãn HDFS gắn theo block trace, không phải chuỗi thời gian
  đều.

## Artifact tối thiểu của mỗi run

`manifest.json`, `split.csv`, feature files theo split, `predictions.csv`,
`metrics.json`, `confusion_matrices.csv`, `run_config.yaml` và metadata
model/scaler. Manifest phải có checksum input, Git commit, timestamp, random
seed, Python và package versions.
