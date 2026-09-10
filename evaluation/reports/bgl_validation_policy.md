# BGL v1 validation policy review

Review dùng duy nhất validation split (20 windows: 12 normal, 8 anomaly) từ
artifact `bgl_v1_error_analysis_841b049`.

| Detector         | Validation score distribution                               | Quyết định BGL v1                                               |
| ---------------- | ----------------------------------------------------------- | --------------------------------------------------------------- |
| Rule log-only    | 12 normal và 8 anomaly đều score `0.2`                      | N/A cho fusion: score không phân biệt được class                |
| DeepLog          | 11 normal và 8 anomaly score `1.0`; 1 normal score `0.9919` | N/A cho fusion: UNK saturation, score không phân biệt được class|
| Isolation Forest | score có phân bố chồng lấp nhưng không constant             | Giữ baseline; threshold calibration validation hợp lệ           |

Không thay đổi Rule threshold, DeepLog UNK policy, sequence length hoặc LSTM
hyperparameter dựa trên test. Với BGL v1, `log_only_fusion` cần ít nhất hai
detector có score discriminative; hiện chỉ IF đạt điều kiện nên fusion được
ghi **N/A**, không thay bằng single-detector score.
