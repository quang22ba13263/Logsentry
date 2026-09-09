# BGL v1 — Validation uncertainty and seed stability

Status: validation-only. This analysis reads no test rows or test labels.

The fixed chronological validation split has 20 windows (8 anomaly, 12 normal). The candidate is Isolation Forest with 200 trees; split/window parameters were not changed.

| Run | Seed | Precision | Recall | F1 | Stratified bootstrap 95% F1 CI |
| --- | ---: | ---: | ---: | ---: | --- |
| `bgl_if_stability_seed13_20260909_cd05065` | 13 | 0.6667 | 1.0000 | 0.8000 | [0.6957, 0.9412] |
| `bgl_if_stability_seed42_20260909_cd05065_retry` | 42 | 0.6154 | 1.0000 | 0.7619 | [0.6667, 0.8889] |
| `bgl_if_stability_seed2026_20260909_cd05065_retry` | 2026 | 0.6154 | 1.0000 | 0.7619 | [0.6667, 0.8889] |

Across seeds: mean validation F1 = **0.7746**, population std = **0.0180**.

Bootstrap method: 10,000 stratified non-parametric resamples, bootstrap seed 20260909. The CI describes sampling instability of this small validation set; it is not a final-test confidence interval.

## Reporting constraint

BGL's 20-window validation set is too small to compare its apparent F1 directly with HDFS's 57,506-trace validation result. Report the interval and seed spread together with the point estimate, and do not tune further from this analysis.
