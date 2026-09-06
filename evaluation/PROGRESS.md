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
- [ ] Tạo `manifest.json` cho một run thực tế, gồm commit, package version và
  dataset hash đã xác minh runtime.

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
- [ ] Ghi và khóa `split.csv` versioned cho run BGL.
- [ ] Tích hợp Rule + IF vào runner CLI `run_bgl.py`; export predictions,
  metrics, confusion matrix và manifest.
- [ ] Tune IF threshold chỉ trên validation, sau đó chạy test đúng một lần.
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

- [!] `PyYAML>=6.0` đã thêm vào `requirements.txt` để runner đọc YAML, nhưng
  chưa cài trong interpreter đã kiểm tra. Chưa chạy CLI runner cho tới khi cài
  dependency này.
- [!] Repository hiện không có `.venv`; Python đã xác minh là Python hệ thống
  3.13.15. Cần dùng đúng interpreter của venv mong muốn trước final run và ghi
  vào manifest.
- [!] Không được báo cáo F1 hiện tại như kết quả chính thức: chưa có artifact
  immutable (`split.csv`, manifest, predictions) và IF chưa calibration qua
  validation.
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
