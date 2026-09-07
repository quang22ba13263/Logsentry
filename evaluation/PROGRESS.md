# Tiến độ log-only evaluation

Trạng thái kiểm tra: 2026-09-07. Checklist này theo
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
- [x] Runner bắt buộc `--run-id`, tạo artifact `bgl_v1_20260907/` và từ chối
  lần chạy thứ hai cùng ID; `split.csv` không còn bị overwrite.
- [x] Integrity đã xác minh lại với `bgl_v1_e6a08f3/`: hash dataset/config/split
  và `git_commit` trong manifest khớp đúng commit khóa runner `e6a08f3`.
- [x] IF đã tích hợp vào `run_bgl.py`: `RobustScaler`/model fit train-normal,
  threshold `0.8958333333333334` chọn từ validation, prediction/metric được
  export cùng Rule.
- [x] Export `confusion_matrices.csv` cho Rule và IF trong artifact BGL.
- [x] DeepLog đã tích hợp `run_bgl.py`: LSTM train normal-window sequence,
  score next-event surprise và threshold chọn trên validation; artifact
  `bgl_v1_deeplog_20260907/` có prediction/metric/confusion matrix.
- [x] VAR BGL data-quality gate: **N/A**; xem `reports/bgl_var_gate.md`.
- [x] `error_analysis.csv` đã export cho mỗi detector (top 10 FP/FN theo score)
  trong artifact `bgl_v1_error_analysis_841b049/`.
- [x] Validation policy review đã hoàn tất; xem `reports/bgl_validation_policy.md`.
- [x] Log-only fusion BGL v1: **N/A** vì chỉ IF có score discriminative;
  không thay fusion bằng score của một detector.
- [x] Báo cáo BGL v1 đã đóng gói tại `reports/bgl_v1_summary.md`, phân biệt
  diagnostic artifact với final run độc lập cần thực hiện sau development.

## C. HDFS v1

- [x] Đã kiểm tra input schema: `Event_traces.csv` có `BlockId`, `Label`,
  `Type`, `Features`; occurrence matrix có `E1..E29`; label file riêng map
  `Normal`/`Anomaly`.
- [x] `hdfs_adapter.py` parse EventId sequence, join ba input theo `BlockId`,
  và chỉ expose `E1..E29` làm feature; label/type/ID là metadata.
- [x] Unit tests HDFS cho sequence parser, join và leakage audit pass.
- [ ] Full-scale join/count distribution và mismatch gate trên input HDFS thật.
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
- [!] Artifact `bgl_v1_20260907/` hiện là immutable diagnostic run có đầy đủ
  split/prediction/metric/confusion matrix/manifest. Không gọi là final vì
  DeepLog, fusion, error analysis và policy Rule vẫn chưa hoàn tất.
- [!] `bgl_v1_20260907/` giữ manifest của commit trước (`e9ce224`) vì được tạo
  trước commit runner. Dùng `bgl_v1_e6a08f3/` làm baseline integrity đã xác
  minh; cả hai vẫn chỉ là diagnostic do test đã được xem trong giai đoạn phát
  triển.
- [!] TensorFlow chạy CPU trên native Windows (không GPU) và phát cảnh báo
  Matplotlib font-cache không ghi được tại user profile. Smoke test pass; đặt
  `MPLCONFIGDIR` writable trước khi sinh figure benchmark.
- [!] DeepLog diagnostic chọn threshold `1.0`, dự đoán tất cả 20 test sample
  anomaly (TP=8, FP=12, TN=0, FN=0; F1=0.5714). Khả năng cao do EventId chưa
  thấy trong normal-train được score cực đại; cần error analysis và xem xét
  aggregation/UNK policy bằng validation, tuyệt đối không tune theo test.
- [!] Manifest `bgl_v1_deeplog_20260907/` ghi commit `530b770` (DeepLog class)
  vì run được tạo trước commit runner integration `426c0e0`; giữ nó làm
  diagnostic và tạo run ID mới sau khi source được khóa trước bất kỳ kết quả
  chính thức nào.
- [!] Error analysis: 10 Rule FP đầu đều trigger `unseen_template_ratio`; DeepLog
  FP có score `1.0` do EventId UNK; IF có 3 FP (windows 85/91/97) và 2 FN
  (windows 86/87). Các finding này phải được dùng để sửa policy qua validation,
  không được chọn lại bằng test.
- [!] Validation policy: Rule score constant `0.2`; DeepLog 19/20 score gần
  hoặc bằng `1.0` do UNK saturation. Hai detector bị loại khỏi BGL v1 fusion;
  không chỉnh hyperparameter theo test để cố cải thiện F1.
- [!] Workspace có thay đổi ngoài benchmark không nằm trong commit benchmark:
  `File_structure.md`, nhóm `scripts/`, cùng một số file root. Ngoài ra tại
  thời điểm audit, `evaluation/reports/.gitkeep` bị xóa và
  `evaluation/features/reports/` chưa track; cần người sở hữu thay đổi xác nhận
  mục đích trước khi stage hoặc khôi phục.

## Bước kế tiếp bắt buộc

1. Viết và test HDFS adapter trước khi chạy smoke benchmark.
2. Chạy HDFS smoke IF + DeepLog, rồi HDFS final benchmark.
3. Chỉ sau khi toàn bộ benchmark hoàn tất mới mở một pha tuning riêng, được
   ghi version/config và không dùng test set để chọn thông số.
