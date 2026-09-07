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
- [x] Python/dependency runtime đã được kiểm tra; 24 unit test evaluation pass.
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
- [x] Full-scale HDFS join gate pass: 575.061 samples, 558.223 normal, 16.838
  anomaly, 29 occurrence features; không có BlockId mismatch.
- [x] Chronological smoke support gate pass: 20.000 train-normal, validation
  5.000 có 257 anomaly, test 10.000 có 507 anomaly; không cần fallback split.
- [x] Smoke split immutable đã tạo tại `hdfs_v1_smoke_20260907/split.csv`.
- [x] HDFS smoke IF đã chạy tại `hdfs_v1_if_smoke_20260907/`: threshold validation
  `0.93805`, test P=0.1852, R=0.5878, F1=0.2817.
- [x] HDFS DeepLog smoke batched đã hoàn tất trên subset versioned; giới hạn
  2.000 normal traces/1 epoch được ghi trong artifact để không nhầm với final.
- [!] DeepLog subset 2.000 trace / 1 epoch cũng bị dừng: implementation hiện
  gọi TensorFlow predict theo từng context, nên validation/test HDFS tạo quá
  nhiều inference call. Cần batch inference trong `LogOnlyDeepLog.score()`
  trước khi thử lại; không ghi metric từ job bị dừng.
- [x] `LogOnlyDeepLog.score()` đã đổi sang batched inference (4.096 context/lô);
  smoke unit pass. Cần rerun HDFS smoke để xác nhận runtime/metric.
- [x] HDFS DeepLog batched smoke hoàn tất tại `hdfs_v1_deeplog_batched_cd3317b/`:
  train subset 2.000 normal trace/1 epoch, threshold validation `0.9995723`,
  test P=0.9618, R=0.6450, F1=0.7721.
- [!] Đây là DeepLog smoke subset có version rõ ràng, không phải HDFS final;
  final cần train split/protocol đã khóa và artifact đầy đủ.
- [x] HDFS equal-weight log-only fusion smoke hoàn tất tại `hdfs_v1_fusion_smoke/`:
  threshold validation `0.942025`, test P=0.1371, R=0.4990, F1=0.2150.
- [!] Fusion smoke kém hơn DeepLog (F1=0.7721) do IF false positive cao; không
  chỉnh weight theo test. Nếu tiếp tục fusion, weight/min-votes chỉ được chọn
  trên validation và cần ghi config version riêng.
- [x] BGL/HDFS runner hiện mặc định ở `development_validation_only`: không
  score test, không export nhãn test; test chỉ mở qua cờ rõ ràng `--final-test`.
- [x] Có unit test xác nhận Rule BGL validation-only không sinh test rows.
- [x] Guard đã chạy kiểm chứng end-to-end: BGL artifact
  `bgl_dev_guard_20260907/` có 0 test prediction/0 nhãn test; HDFS artifact
  `hdfs_dev_guard_20260907/` chỉ ghi validation metric (DeepLog F1=0.7488 với
  2.000 normal trace, 1 epoch). Đây là checkpoint tuning, không phải final.
- [x] HDFS Rule log-only đã có transformer fit EventId vocabulary từ
  train-normal và feature `trace_length`, entropy, top-event ratio,
  unseen-event ratio; unit test từ chối `Label`/`Type`/`BlockId`/ground truth.
- [x] HDFS Rule validation-only checkpoint `hdfs_rule_dev_20260907/`: P=0.9957,
  R=0.9027, F1=0.9469, threshold=0.2. Rule đủ điều kiện là **candidate** fusion;
  chưa thêm vào fusion hoặc chấm test trước pha tuning versioned.
- [x] HDFS final-scale 70/10/20 source-order split đã được materialize tại
  `hdfs_v1_final_split_20260907/`: train 402.542 (13.115 anomaly), validation
  57.506 (2.044 anomaly), test 115.013. Artifact có config/input/split hash,
  nhưng không export nhãn hoặc score test.
- [x] HDFS Rule final-scale development artifact
  `hdfs_v1_final_rule_checksum_20260907/` đã verify upstream split/config hash và
  chỉ xuất 57.506 validation predictions: P=0.9973, R=0.3601, F1=0.5291,
  threshold=0.2; test không được đọc từ split, không có prediction/nhãn test.
- [x] HDFS Isolation Forest final-scale development artifact
  `hdfs_v1_final_if_dev_20260907/`: train 389.427 normal trace, chỉ score
  57.506 validation trace; P=0.9885, R=0.4628, F1=0.6305,
  threshold=0.7079118807889541. Không có prediction/nhãn test.
- [x] DeepLog được đổi sang streaming train context và direct batched inference;
  unit test xác nhận fit/UNK score. HDFS final-scale artifact
  `hdfs_v1_final_deeplog_dev_20260907/` train deterministic 10.000 normal
  trace/1 epoch, chỉ score validation: P=0.9975, R=0.7671, F1=0.8673,
  threshold=0.9998582827392966; không có prediction/nhãn test.
- [x] Báo cáo validation-only HDFS đã tổng hợp tại
  `reports/hdfs_validation_summary.md`; nêu split seal, config, P/R/F1,
  artifact/commit và cấm diễn giải thành kết quả test cuối.
- [x] DeepLog train-size tuning v1 hoàn tất trên frozen validation: 10.000
  F1=0.86726, 25.000 F1=0.85808, 50.000 F1=0.86733. Theo metric đã công bố,
  50.000 tạm tốt nhất nhưng hơn 10.000 chỉ 0.00007; chưa score test. Bảng và
  artifact nằm trong `reports/hdfs_validation_summary.md`.
- [x] Rule percentile tuning v1 (95/97/99) cho cùng F1=0.5291 trên validation;
  không phải đòn bẩy cải thiện ở checkpoint hiện tại và không score test.
- [x] IF tuning v1: 100/auto F1=0.63046, 200/auto F1=0.63682, 200/512
  F1=0.63997; 200/512 là candidate IF hiện tại, chỉ theo validation.

## D. Vấn đề / quyết định cần theo dõi

- [x] Checksum gate HDFS phát hiện hash occurrence matrix cũ sai một ký tự
  (`59ab8a...`); đã đối chiếu lại file nguồn và sửa thành `59ab8b...` trong
  README/config trước khi tạo bất kỳ final-scale artifact nào.

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

1. Hoàn thiện HDFS Isolation Forest và DeepLog final-scale artifact ở chế độ
   development (train + validation), chưa gọi `--final-test`.
2. Mở pha tuning versioned: thay đổi một nhóm thông số mỗi lần, đo trên
   validation, lưu config/seed/metric; tuyệt đối không score test.
3. Khi chọn được config tốt nhất trên validation, đóng băng config/model hash
   và mới chạy `--final-test` đúng một lần để tạo báo cáo cuối.
