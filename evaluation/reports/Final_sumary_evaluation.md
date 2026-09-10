# Final summary evaluation — BGL và HDFS log-only

**Ngày chạy final:** 2026-09-10  
**Branch/commit khi chạy HDFS final:** `codex/log-only-evaluation` / `7bcebeda661af334e4a7ff24106296a8a57ea932`  
**Phạm vi:** anomaly detection chỉ dùng thông tin log. Không dùng `Label`,
`ground_truth`, HDFS `Type`, `BlockId` hoặc identifier làm input model.

## Kết luận ngắn

- **HDFS sealed final test:** Fusion Rule + DeepLog đạt **F1 0.8718**, recall
  **0.9988**. Kết quả thấp hơn validation (F1 0.9985), cho thấy validation đã
  lạc quan hơn hold-out và kết quả final này mới là số liệu cần báo cáo chính.
- **BGL post-diagnostic confirmation:** Isolation Forest đạt **F1 0.7059**.
  BGL test từng bị quan sát trong giai đoạn chẩn đoán cũ, vì vậy đây là xác nhận
  sau chẩn đoán, không được gọi là sealed hold-out hoàn toàn độc lập.
- Không gộp một metric chung cho BGL và HDFS: hai dataset có đơn vị mẫu, tín
  hiệu log và độ khó khác nhau.

## 1. Setup và tính tái lập

Mã evaluation nằm trong `evaluation/`; dữ liệu nguồn ở `Dataset/` chỉ đọc.
`.gitignore` loại trừ `Dataset/`, `data/processed/evaluation/` và
`data/models/evaluation/`, vì vậy dataset, model bundle và output runtime không
đi vào Git.

- Môi trường chạy: Python 3.13.15 trên Windows 11; `pip check` không phát hiện
  dependency hỏng.
- Thư viện cần thiết được ghi tại `requirements.txt` và `evaluation/README.md`:
  `pandas`, `numpy`, `scikit-learn`, `tensorflow` (cùng `PyYAML`, `joblib`).
- Trước final: 10 YAML config parse thành công; 32/32 unit test pass, gồm guard
  clean-worktree, split sealing, label-leakage và model-bundle round-trip.
- Bundle frozen được nạp và kiểm hash trước khi chấm test. HDFS dùng IF bundle
  `data/models/evaluation/hdfs_v1_final_if_bundle_200_512_20260909/isolation_forest/`
  và DeepLog bundle
  `data/models/evaluation/hdfs_v1_final_deeplog_epoch1_50000_20260909/deeplog/`.
  BGL dùng IF bundle
  `data/models/evaluation/bgl_if_stability_seed42_20260909_cd05065_retry/isolation_forest/`.

## 2. Dữ liệu và chia tập

| Benchmark | Nguồn và adapter | Train | Validation | Test final | Cách chia |
|---|---|---:|---:|---:|---|
| BGL_2k | `Dataset/BGL/BGL_2k.log_structured.csv`; `evaluation/adapters/bgl_adapter.py` | 60 window (48 normal, 12 anomaly) | 20 (12 normal, 8 anomaly) | 20 (12 normal, 8 anomaly) | chronological 60/20/20; mỗi window 20 event, stride 20 |
| HDFS_v1 | `Dataset/HDFS_v1/preprocessed/{Event_traces,Event_occurrence_matrix,anomaly_label}.csv`; `evaluation/adapters/hdfs_adapter.py` | 402,542 trace (389,427 normal, 13,115 anomaly) | 57,506 (55,462 normal, 2,044 anomaly) | 115,013 (113,334 normal, 1,679 anomaly) | source-record-order 70/10/20 |

Hash SHA-256 input và frozen split được kiểm trước final. HDFS frozen split là
`data/processed/evaluation/hdfs_v1_final_split_20260907/`, hash
`b99bd57ebab04302a286a28a3693e296c83e9de3cd93789ac0fb81fe7cc944ae`.
Artifact development giữ `ground_truth` test trống (115,013/115,013 test row
không có nhãn); runner final mới đọc label-bearing source sau release flag.

## 3. Dữ liệu đi vào detector và quá trình train

### BGL

1. `bgl_adapter.py` đọc CSV structured BGL, chuyển mỗi event thành template/log
   representation và gộp 20 event liên tiếp thành một window theo thời gian.
2. `evaluation/features/log_only_features.py` biến mỗi window thành feature chỉ
   từ log. Transformer được fit trên **48 normal train window**; nhãn chỉ dùng
   để chọn normal train và để tính metric bên ngoài model.
3. Isolation Forest được train normal-only, seed 42, 200 trees, `max_samples`
   `auto`; model, scaler/reference score và fitted transformer được lưu bằng
   `joblib`. Threshold 0.8541666666666666 được chọn trên validation rồi freeze.

### HDFS

1. `hdfs_adapter.py` ghép Event traces (chuỗi event) với occurrence matrix theo
   trace. `hdfs_log_only_features.py` tạo vector occurrence cho Rule/IF và giữ
   sequence event cho DeepLog; `Type`, `BlockId`, label không vào feature.
2. Rule fit đặc trưng normal trên **389,427 train-normal trace** với percentile
   99. IF 200-tree/`max_samples=512` cũng được train normal-only trên split này
   và lưu bundle. DeepLog dùng sequence length 10, embedding 16, LSTM 32,
   batch 256 và train **50,000 train-normal trace**, 1 epoch; model `.keras`,
   vocabulary và config được bundle cùng nhau.
3. Khi final, IF và DeepLog được **load**, không retrain. Rule được fit lại một
   cách deterministic từ train-normal. Điều này giữ nguyên candidate đã chọn
   trên validation và tránh dùng test để chọn thông số.

## 4. Validation và tuning trước khi mở test

Tất cả tuning dùng validation, không export/chấm test HDFS.

| Benchmark / detector | Cấu hình được freeze từ validation | Validation TP / FP / TN / FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|
| BGL IF | seed 42, 200 trees, threshold 0.85417 | 8 / 5 / 7 / 0 | 0.6154 | 1.0000 | 0.7619 |
| HDFS Rule | p99, threshold 0.2 | 736 / 2 / 55,460 / 1,308 | 0.9973 | 0.3601 | 0.5291 |
| HDFS IF | 200 trees, 512 samples, threshold 0.76514 | 967 / 11 / 55,451 / 1,077 | 0.9888 | 0.4731 | 0.6400 |
| HDFS DeepLog | 50k normal, epoch 1, threshold 0.999943 | 1,569 / 5 / 55,457 / 475 | 0.9968 | 0.7676 | 0.8673 |
| HDFS Fusion | Rule 0.75 + DeepLog 0.25 + IF 0; threshold 0.249986 | 2,044 / 6 / 55,456 / 0 | 0.9971 | 1.0000 | 0.9985 |

Các artifact validation chi tiết nằm trong
`data/processed/evaluation/hdfs_v1_final_{rule_checksum_20260907,if_bundle_200_512_20260909,deeplog_epoch1_50000_20260909,fusion_tune_fast_20260907}/`
và `data/processed/evaluation/bgl_if_stability_seed42_20260909_cd05065_retry/`.
Tuning BGL được ghi ở `evaluation/reports/bgl_tuning_plan.md`; các vòng HDFS
và quyết định chọn candidate được ghi ở
`evaluation/reports/hdfs_validation_summary.md`.

## 5. Kết quả final

### HDFS sealed final test

Artifact bất biến: `data/processed/evaluation/hdfs_v1_final_test_20260910/`
(`predictions.csv`, `metrics.json`, `manifest.json`). Test gồm 115,013 trace:
1,679 anomaly và 113,334 normal.

| Detector | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Rule log-only | 1,261 | 5 | 113,329 | 418 | 0.9961 | 0.7510 | 0.8564 |
| Isolation Forest log-only | 1,356 | 68,502 | 44,832 | 323 | 0.0194 | 0.8076 | 0.0379 |
| DeepLog log-only | 614 | 487 | 112,847 | 1,065 | 0.5577 | 0.3657 | 0.4417 |
| Fusion (Rule 0.75 + DeepLog 0.25) | 1,677 | 491 | 112,843 | 2 | 0.7735 | 0.9988 | **0.8718** |

**Đánh giá HDFS.** Rule rất chính xác khi báo động (chỉ 5 FP) nhưng bỏ sót 418
anomaly. IF không phù hợp với hold-out này ở threshold freeze: 68,502 FP làm
precision và F1 giảm mạnh; vì weight IF đã là 0 từ validation, fusion không bị
ảnh hưởng trực tiếp bởi IF. DeepLog cũng giảm recall trên test, có thể phản ánh
khác biệt phân phối sequence giữa validation và test hoặc threshold calibration;
đây là diễn giải, không phải bằng chứng nhân quả. Fusion bắt gần như toàn bộ
anomaly (chỉ 2 FN) nhưng đổi lại 491 FP. F1 final 0.8718 thấp đáng kể so với
0.9985 validation: không nên báo cáo số validation như hiệu năng cuối cùng, và
không nên tuning tiếp bằng test này.

### BGL post-diagnostic confirmation

Artifact: `data/processed/evaluation/bgl_v1_post_diagnostic_confirmation_20260910/`.
Test gồm 20 window: 8 anomaly và 12 normal.

| Detector được chấm | TP | FP | TN | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Isolation Forest log-only | 6 | 3 | 9 | 2 | 0.6667 | 0.7500 | **0.7059** |

**Đánh giá BGL.** Kết quả 0.7059 thấp hơn validation 0.7619 nhưng chênh lệch
không lớn; tuy nhiên test chỉ có 20 window nên 1–2 dự đoán thay đổi đã làm metric
dao động đáng kể. Seed stability trước final (13/42/2026) cho F1 validation mean
0.7746 ± 0.0180, nên không nên diễn giải chênh lệch nhỏ là cải thiện/suy giảm
chắc chắn. BGL cần thêm log hoặc window-level sample độc lập trước khi khẳng định
độ chính xác tổng quát.

## 6. Vì sao một số detector là N/A hoặc không vào fusion

| Benchmark | Thành phần | Trạng thái | Lý do |
|---|---|---|---|
| BGL | Rule | Không chấm final | Validation score hầu như không phân biệt được mẫu; không có threshold/candidate khoa học để freeze. |
| BGL | DeepLog | Không chấm final | UNK saturation: 19/20 validation score bằng 1, nên score không đủ độ phân giải để chọn threshold đáng tin cậy. |
| BGL | Fusion | N/A | Fusion cần tối thiểu hai detector có score phân biệt và threshold đã freeze; BGL chỉ có IF đủ điều kiện. |
| BGL, HDFS | VAR | N/A | Protocol VAR yêu cầu chuỗi thời gian đủ dài, đều và có tín hiệu tương quan ổn định. Event-window BGL và HDFS block-trace/occurrence không qua data-quality gate này; ép chạy sẽ tạo metric không cùng cơ sở với detector log-only. |
| HDFS | IF trong Fusion | weight 0 | Validation fusion đã chọn weight 0 cho IF. Final IF có 68,502 FP xác nhận quyết định loại IF khỏi fusion là hợp lý, nhưng đây không phải tuning lại theo test. |

## 7. Ghi chú vận hành và cách kiểm tra lại

Lệnh đã chạy (không chạy lại cùng run-id vì runner từ chối overwrite artifact):

```powershell
python evaluation/runners/run_hdfs_final_test.py --config evaluation/config/hdfs_final_candidate_v1.yaml --split-artifact data/processed/evaluation/hdfs_v1_final_split_20260907 --run-id hdfs_v1_final_test_20260910 --release-sealed-test --approval-token HDFS_TEST_RELEASE_CONFIRMED

python evaluation/runners/run_bgl_final_test.py --config evaluation/config/bgl_final_candidate_v1.yaml --run-id bgl_v1_post_diagnostic_confirmation_20260910 --release-sealed-test --approval-token BGL_POST_DIAGNOSTIC_CONFIRMATION_CONFIRMED
```

HDFS invocation đầu tiên bị dừng trước khi tạo output/prediction/metric do lỗi
mapping tuple Rule trong runner. Lỗi đã được sửa bằng `zip(test, scores,
strict=True)`, bổ sung regression test, chạy lại 32/32 test pass và commit tại
`7bcebed` trước invocation thành công. Sự cố này được ghi để minh bạch; không có
metric nào được xuất từ invocation thất bại.

Để supervisor tái lập preflight hoặc đọc kết quả cần có repository ở commit trên,
`Dataset/`, các model bundle và `data/processed/evaluation/` tương ứng (đều bị
Git ignore, nên phải bàn giao qua Drive/ZIP hoặc cơ chế artifact riêng). Đọc
`metrics.json` và `manifest.json` không cần chạy lại detector. Không dùng kết
quả test final này để chọn threshold, weight hay epoch mới.

## 8. Đường dẫn chính

| Nội dung | Path |
|---|---|
| Protocol / hướng dẫn môi trường | `evaluation/README.md`, `evaluation/evaluation_protocol.md` |
| Tiến độ / checklist | `evaluation/PROGRESS.md` |
| Config BGL frozen | `evaluation/config/bgl_final_candidate_v1.yaml` |
| Config HDFS frozen | `evaluation/config/hdfs_final_candidate_v1.yaml` |
| Final runner | `evaluation/runners/run_bgl_final_test.py`, `evaluation/runners/run_hdfs_final_test.py` |
| BGL final artifact | `data/processed/evaluation/bgl_v1_post_diagnostic_confirmation_20260910/` |
| HDFS final artifact | `data/processed/evaluation/hdfs_v1_final_test_20260910/` |
| Báo cáo tổng hợp trước final | `evaluation/reports/ALLsumary_evaluation_report.md` |
