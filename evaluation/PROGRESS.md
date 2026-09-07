# Tiến độ log-only evaluation

Trạng thái kiểm tra: 2026-09-06. Checklist này theo
[`KE_HOACH_DANH_GIA_LOG_ONLY_CHINH_THUC.md`](../KE_HOACH_DANH_GIA_LOG_ONLY_CHINH_THUC.md)
và chỉ ghi nhận checkpoint đã có code/test hoặc artifact kiểm chứng.

## A. Nền tảng và protocol

- [x] Branch riêng `codex/log-only-evaluation`.
- [x] `Dataset/`, `data/processed/evaluation/`, `data/models/evaluation/` bị
  ignore; không ghi output vào dataset nguồn.
- [x] SHA-256 BGL structured CSV, HDFS traces và HDFS occurrence matrix đã ghi
  tại `README.md` và config.
- [x] Protocol, BGL/HDFS YAML config và random seed `42` đã tạo.
- [x] Python/dependency runtime đã được kiểm tra; 13 unit test evaluation pass.
- [x] Runner BGL đã tạo `manifest.json`, checksum input/config, `split.csv`,
  `predictions.csv`, `metrics.json` và `run_config.yaml` tại output bị ignore.

## B. BGL v1

- [x] `bgl_adapter.py` map đúng contract, sort timestamp và kiểm tra 2.000
  events / 143 event anomaly mà không sửa dataset.
- [x] Event-count window size 20, stride 20, non-overlap; 100 samples.
- [x] Chronological split 60/20/20: train 60 (12 anomaly), validation 20 (8),
  test 20 (8). Validation/test đủ positive support.
- [x] Leakage guard: model input loại `Label`, `ground_truth`, `Type`, `BlockId`.
- [x] Log-only Rule baseline: threshold fit train-normal, calibration F1 chỉ
  trên validation, prediction có reason.
- [x] Log-only Isolation Forest baseline: feature/scaler/model fit train-normal;
  score chuẩn hóa bằng distribution train-normal.
- [x] Rule baseline đã chạy qua CLI `run_bgl.py`; export split, prediction,
  metric và manifest thành công.
- [ ] Khóa artifact bằng run ID mới cho mỗi lần chạy; runner hiện ghi đè
  `bgl_v1/`, nên `split.csv` chưa là immutable versioned artifact.
- [x] IF đã tích hợp vào `run_bgl.py`: `RobustScaler`/model fit train-normal,
  threshold `0.8958333333333334` chọn từ validation, prediction/metric được
  export cùng Rule.
- [ ] Export confusion matrix CSV/figure cho Rule và IF.
- [ ] DeepLog BGL, VAR data-quality gate/N/A statement, log-only fusion và báo
  cáo BGL final.

## C. HDFS v1

- [x] Đã kiểm tra input schema: `Event_traces.csv` có `BlockId`, `Label`,
  `Type`, `Features`; occurrence matrix có `E1..E29`; label file riêng map
  `Normal`/`Anomaly`.
- [ ] **HDFS adapter chưa tồn tại.** Cần tạo `evaluation/adapters/hdfs_adapter.py`
  để parse sequence, join chính xác theo `BlockId`, chỉ dùng `E1..E29` làm
  feature và đưa `Label`/`Type`/`BlockId` ra metadata.
- [ ] Unit tests HDFS: parser sequence, join mismatch fail-closed, count/sample
  distribution, và leakage audit.
- [ ] HDFS smoke split, IF + DeepLog; Rule chỉ thêm khi feature policy đã rõ.
- [ ] HDFS final split/benchmark, log-only fusion và evidence artifact.

## D. Vấn đề / quyết định cần theo dõi

- [x] `PyYAML 6.0.3` đã cài và runner đọc YAML thành công.
- [!] Repository hiện không có `.venv`; Python đã xác minh là Python hệ thống
  3.13.15. Cần dùng đúng interpreter của venv mong muốn trước final run và ghi
  vào manifest.
- [!] Không được báo cáo F1 hiện tại như kết quả chính thức: chưa có artifact
  immutable versioned và IF chưa calibration qua validation. Rule preliminary
  chọn threshold `0.0` trên validation, dẫn đến mọi test sample bị dự đoán là
  anomaly (TP=8, FP=12, TN=0, FN=0; F1=0.5714); cần error analysis/policy
  review, không được tune theo test.
- [!] IF preliminary chạy qua runner: TP=6, FP=3, TN=9, FN=2; P=0.6667,
  R=0.7500, F1=0.7059. Threshold được chọn đúng từ validation, nhưng test đã
  chạy lặp khi kiểm tra runner và output `bgl_v1/` bị ghi đè; cần run ID bất
  biến trước khi công bố kết quả chính thức.
- [!] Workspace có thay đổi ngoài benchmark không nằm trong commit benchmark:
  `File_structure.md`, nhóm `scripts/`, cùng một số file root. Ngoài ra tại
  thời điểm audit, `evaluation/reports/.gitkeep` bị xóa và
  `evaluation/features/reports/` chưa track; cần người sở hữu thay đổi xác nhận
  mục đích trước khi stage hoặc khôi phục.

## Bước kế tiếp bắt buộc

1. Cài `PyYAML` vào interpreter dùng chạy benchmark.
2. Viết và test HDFS adapter trước khi chạy smoke benchmark.
3. Hoàn thiện BGL runner/artifact và calibration IF; chỉ sau đó mới chạy BGL
   test chính thức, DeepLog và fusion.
