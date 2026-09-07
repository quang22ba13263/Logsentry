# BGL v1 log-only benchmark summary

## Phạm vi đã khóa

- Dataset: BGL 2k structured log; event-count window 20, non-overlap.
- Split chronological: 60 train / 20 validation / 20 test windows.
- Fit model/scaler/vocabulary: chỉ normal train.
- Threshold: chỉ chọn trên validation.
- VAR: N/A vì timestamp thưa/không đều; xem `bgl_var_gate.md`.

## Kết quả diagnostic đã tái lập

Artifact integrity: `bgl_v1_error_analysis_841b049/`, với dataset/config/split
hash và commit source trong manifest. Đây là development diagnostic vì test đã
được xem trong quá trình xây dựng, không phải con số final để công bố.

| Detector | Precision | Recall | F1 | Quyết định |
| --- | ---: | ---: | ---: | --- |
| Rule log-only | 0.4000 | 1.0000 | 0.5714 | N/A benchmark: validation score constant |
| Isolation Forest log-only | 0.6667 | 0.7500 | 0.7059 | Baseline hợp lệ, cần final run độc lập |
| DeepLog LSTM | 0.4000 | 1.0000 | 0.5714 | N/A benchmark: UNK score saturation |
| VAR | N/A | N/A | N/A | Data-quality gate không đạt |
| log-only fusion | N/A | N/A | N/A | Chỉ IF còn score discriminative |

Không thay đổi threshold/hyperparameter bằng test để tăng score. Các giới hạn
Rule/DeepLog và error analysis được lưu tại `bgl_validation_policy.md` và
`PROGRESS.md`.
