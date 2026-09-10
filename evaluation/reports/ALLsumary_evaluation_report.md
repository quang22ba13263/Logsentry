# Báo cáo tổng hợp đánh giá LogSentry — BGL và HDFS

**Cập nhật:** 2026-09-10
**Branch:** `codex/log-only-evaluation`
**Trạng thái:** development/validation hoàn tất; BGL/HDFS final runner và
candidate frozen đã sẵn sàng nhưng **chưa chạy test cuối niêm phong**.

## Tóm tắt

Đánh giá dùng log công khai có ground truth, không tạo metric hệ thống giả.
BGL và HDFS được train/đánh giá độc lập, không có model nào train chung hai
dataset. HDFS đạt validation tốt nhất với fusion Rule + DeepLog F1=0,9985.
BGL candidate là Isolation Forest 200 trees, seed 42, F1=0,7619; qua ba seed
đạt mean F1=0,7746 ± 0,0180. Đây đều là metric validation, không phải final
accuracy.

## Dataset và xử lý

| Dataset | Input chỉ đọc | Đơn vị đánh giá | Xử lý |
| --- | --- | --- | --- |
| BGL | `Dataset/BGL/BGL_2k.log_structured.csv` | Window 20 event, stride 20 | 100 non-overlap window; nhãn window là OR anomaly event |
| HDFS | `Dataset/HDFS_v1/preprocessed/Event_traces.csv` | Block trace | Parse chuỗi EventId `Features` |
| HDFS | `Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv` | Block trace | Chỉ `E1..E29` là IF feature |
| HDFS | `Dataset/HDFS_v1/preprocessed/anomaly_label.csv` | Block trace | Ground truth/split offline |

Không đưa `Label`, `Type`, `BlockId` hoặc `ground_truth` vào model input.
Adapter: `evaluation/adapters/bgl_adapter.py`,
`evaluation/adapters/hdfs_adapter.py`. Hash dataset nằm trong
`evaluation/README.md`, `evaluation/config/bgl_v1.yaml` và
`evaluation/config/hdfs_v1_final.yaml`. `Dataset/` là read-only và Git ignore.

## Split, train và test seal

- BGL: chronological 60/20/20 window; 60 train, 20 validation, 20 test.
- HDFS: source-record-order 70/10/20; 402.542 train, 57.506 validation,
  115.013 test. Train có 389.427 normal trace, validation có 2.044 anomaly.
- HDFS frozen split: `data/processed/evaluation/hdfs_v1_final_split_20260907/`;
  SHA-256 split `b99bd57ebab04302a286a28a3693e296c83e9de3cd93789ac0fb81fe7cc944ae`.
- HDFS development split không export test label; guard tại
  `evaluation/runners/frozen_split.py` chỉ cấp assignment train/validation.

Model one-class chỉ fit normal sample của train. Threshold luôn chọn validation.
BGL test đã từng bị xem trong diagnostic cũ; nếu chạy lại chỉ là
**post-diagnostic confirmation**. HDFS test chưa được score hoặc export nhãn.

## Detector và train/calibration

| Detector | Code | Train/calibration |
| --- | --- | --- |
| Rule BGL | `evaluation/detectors/log_only_rule.py` | Fit percentile/vocabulary normal train; threshold validation |
| Rule HDFS | `evaluation/detectors/hdfs_log_only_rule.py` | Fit trace length, entropy, top-event, unseen-event normal train |
| Isolation Forest | `evaluation/detectors/log_only_isolation_forest.py` | RobustScaler + IF fit normal train; normalized score/threshold validation |
| DeepLog | `evaluation/detectors/log_only_deeplog.py` | LSTM next-EventId, vocabulary/weight riêng mỗi dataset, normal train only |
| Fusion HDFS | `evaluation/runners/run_hdfs_fusion.py` | Grid weight normalized score, validation only |

DeepLog HDFS streaming `tf.data` để không materialize hàng triệu context trong
RAM. Checkpoint tốt nhất dùng 50.000 normal trace, sequence 10, embedding 16,
LSTM 32, 1 epoch, batch 256, seed 42.

## Kết quả validation hiện tại

| Dataset | Detector | Checkpoint | Precision | Recall | F1 |
| --- | --- | --- | ---: | ---: | ---: |
| HDFS | Rule | percentile 99 | 0,9973 | 0,3601 | 0,5291 |
| HDFS | Isolation Forest | 200 trees, max_samples 512 | 0,9888 | 0,4731 | 0,6400 |
| HDFS | DeepLog | 50.000 normal trace | 0,9968 | 0,7676 | 0,8673 |
| HDFS | Fusion | Rule 0,75 + DeepLog 0,25; IF 0 | 0,9971 | 1,0000 | 0,9985 |
| HDFS | VAR | N/A | N/A | N/A | N/A |
| BGL | Rule | percentile 95/97/99 | 0,4000 | 1,0000 | 0,5714 |
| BGL | Isolation Forest | 200 trees | 0,6154 | 1,0000 | 0,7619 |
| BGL | DeepLog | sequence 10 | 0,4211 | 1,0000 | 0,5926 |
| BGL | Fusion | N/A | N/A | N/A | N/A |
| BGL | VAR | N/A | N/A | N/A | N/A |

HDFS tuning: DeepLog 10k/25k/50k F1=0,86726/0,85808/0,86733; IF
100/auto, 200/auto, 200/512 F1=0,63046/0,63682/0,63997. Fusion grid yêu cầu ít
nhất hai detector active; IF=0 là kết quả validation tối ưu, không bị bỏ tay.

BGL Rule luôn threshold 0 và không discriminative. DeepLog sequence 5/10 có
20/20 và 19/20 score=1,0 do UNK saturation, nên không đủ điều kiện fusion.

## VAR và điều kiện fusion

VAR HDFS N/A vì HDFS gán nhãn theo block trace/session, không có time-series
window liên tục/đều. Resample sẽ thay semantics ground truth. VAR BGL N/A vì
2.000 event phân tán trên 166 active day/215 day, median 3 event mỗi active day;
xem `evaluation/reports/bgl_var_gate.md`.

Fusion BGL N/A vì Rule và DeepLog score gần hằng; ép fusion sẽ không khoa học.
HDFS fusion chỉ dùng Rule/DeepLog vì adding IF làm validation F1 thấp hơn.

## Artifact và path

| Nội dung | Path |
| --- | --- |
| Protocol | `KE_HOACH_DANH_GIA_LOG_ONLY_CHINH_THUC.md` |
| Runtime/hash guide | `evaluation/README.md` |
| Checklist | `evaluation/PROGRESS.md` |
| Báo cáo HDFS | `evaluation/reports/hdfs_validation_summary.md` |
| Tuning BGL | `evaluation/reports/bgl_tuning_plan.md` |
| BGL uncertainty/seed stability | `evaluation/reports/bgl_validation_uncertainty.md` |
| BGL final candidate | `evaluation/config/bgl_final_candidate_v1.yaml` |
| HDFS final candidate | `evaluation/config/hdfs_final_candidate_v1.yaml` |
| BGL final runner | `evaluation/runners/run_bgl_final_test.py` |
| HDFS final runner | `evaluation/runners/run_hdfs_final_test.py` |
| HDFS Rule | `data/processed/evaluation/hdfs_v1_final_rule_checksum_20260907/` |
| HDFS IF | `data/processed/evaluation/hdfs_v1_final_if_tune_200_512_20260907/` |
| HDFS DeepLog | `data/processed/evaluation/hdfs_v1_final_deeplog_tune_50000_20260907/` |
| HDFS Fusion | `data/processed/evaluation/hdfs_v1_final_fusion_tune_fast_20260907/` |
| BGL IF | `data/processed/evaluation/bgl_if_tune_200_20260908/` |
| BGL DeepLog | `data/processed/evaluation/bgl_deeplog_tune_seq10_20260908/` |
| BGL frozen IF bundle | `data/models/evaluation/bgl_if_stability_seed42_20260909_cd05065_retry/isolation_forest/` |
| HDFS frozen IF bundle | `data/models/evaluation/hdfs_v1_final_if_bundle_200_512_20260909/isolation_forest/` |
| HDFS frozen DeepLog bundle | `data/models/evaluation/hdfs_v1_final_deeplog_epoch1_50000_20260909/deeplog/` |

Artifacts runtime bị ignore tại `data/processed/evaluation/<run_id>/`. Candidate
Isolation Forest đã lưu model/scaler/reference-score (và BGL transformer) bằng
`joblib`; DeepLog đã lưu `.keras`, vocabulary và config. Mỗi bundle có
`bundle_manifest.json` SHA-256. Khi giao repository cho supervisor, cần giao
kèm các bundle runtime này hoặc tái tạo chúng bằng validation protocol.

## Cách tái lập validation

```powershell
python -m unittest discover -s evaluation/tests -t . -v
python evaluation/runners/run_hdfs.py --config evaluation/config/hdfs_v1_final.yaml --run-id hdfs_supervisor_split
python evaluation/runners/run_hdfs_rule.py --config evaluation/config/hdfs_v1_final.yaml --split-artifact data/processed/evaluation/hdfs_supervisor_split --run-id hdfs_supervisor_rule
python evaluation/runners/run_hdfs_isolation_forest.py --config evaluation/config/hdfs_v1_final.yaml --split-artifact data/processed/evaluation/hdfs_supervisor_split --run-id hdfs_supervisor_if --n-estimators 200 --max-samples 512
python evaluation/runners/run_hdfs_deeplog.py --config evaluation/config/hdfs_v1_final.yaml --split-artifact data/processed/evaluation/hdfs_supervisor_split --run-id hdfs_supervisor_deeplog --train-normal-limit 50000
python evaluation/runners/run_bgl.py --config evaluation/config/bgl_v1.yaml --run-id bgl_supervisor_dev --if-n-estimators 200 --deeplog-sequence-length 10
```

Các lệnh trên là development-only: không score test hold-out.

## Test niêm phong cuối

Chỉ thực hiện sau khi supervisor phê duyệt config/commit/hash cuối: dừng tuning,
commit config, ghi seed/hash, dùng run ID mới và không overwrite artifact.

### Điều kiện chung

- Candidate config và source commit phải đã được review/push.
- Working tree phải sạch; hai runner từ chối chạy nếu còn thay đổi chưa commit.
- Bundle được khai báo trong candidate config phải tồn tại và hash-verify pass.
- Mỗi benchmark dùng run ID mới, đúng một lần; không mở lại test để tune.

### BGL — post-diagnostic confirmation

```powershell
python evaluation/runners/run_bgl_final_test.py --config evaluation/config/bgl_final_candidate_v1.yaml --run-id bgl_post_diagnostic_confirmation_YYYYMMDD --release-sealed-test --approval-token BGL_POST_DIAGNOSTIC_CONFIRMATION_CONFIRMED
```

Ghi nhãn kết quả BGL là *post-diagnostic confirmation*.

### HDFS — sealed final test

Không dùng `run_hdfs_smoke.py --final-test` vì smoke split không phải
final-scale protocol. Runner explicit nạp IF/DeepLog bundle đã hash-verify,
kiểm tra frozen split/config, fit lại Rule deterministic từ train-normal và
score test đúng một lần:

```powershell
python evaluation/runners/run_hdfs_final_test.py --config evaluation/config/hdfs_final_candidate_v1.yaml --split-artifact data/processed/evaluation/hdfs_v1_final_split_20260907 --run-id hdfs_final_YYYYMMDD --release-sealed-test --approval-token HDFS_TEST_RELEASE_CONFIRMED
```

## Đánh giá trung thực

HDFS fusion 0,9985 rất hứa hẹn nhưng được chọn qua nhiều vòng validation nên có
nguy cơ optimistic bias. Chưa được gọi là final hoặc production accuracy trước
hold-out test. BGL yếu hơn, chứng minh không nên gộp metric hai dataset.
