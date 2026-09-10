# IMPORTANT — Vì sao Rule và DeepLog đảo chiều giữa HDFS validation/final?

## Trả lời ngắn để trình bày

Đây **không phải** do thay đổi model, train lại, hay chọn threshold theo test.
Rule, DeepLog, model bundle và threshold đều đã freeze từ validation trước khi
final test được mở. Sự thay đổi đến từ **khác biệt phân phối anomaly** giữa
validation và test final theo source-record-order split.

| Detector | Validation anomaly score median | Final anomaly score median | Validation recall | Final recall |
|---|---:|---:|---:|---:|
| Rule | 0.0 | 0.4 | 0.3601 | 0.7510 |
| DeepLog | 1.0 | 0.0 | 0.7676 | 0.3657 |

## Rule cải thiện ở final vì sao?

Rule dùng các đặc trưng hình dạng trace được fit chỉ từ normal train:
`trace_length`, event entropy, top-event ratio và unseen-event ratio. Với
threshold freeze 0.2, anomaly final có Rule score cao hơn rõ rệt (median 0.4,
trong khi validation median 0.0), nghĩa là chúng có nhiều dấu hiệu cấu trúc
khác normal train hơn.

Kết quả là Rule phát hiện 1,261/1,679 anomaly final (recall 0.7510), so với
736/2,044 anomaly validation (recall 0.3601). Precision vẫn cao gần như không
đổi (0.9973 → 0.9961), vì FP chỉ từ 2 lên 5. Điều này phù hợp với nhận định:
phần anomaly ở final có trace shape dễ bị Rule phát hiện hơn. Final runner chỉ
lưu reason `frozen_validation_rule_threshold`, nên không thể khẳng định từng
trigger cụ thể cho mỗi row final mà không chạy lại detector; kết luận trên dựa
vào score distribution đã lưu và thiết kế feature của Rule.

## DeepLog giảm ở final vì sao?

DeepLog freeze với `sequence_length=10`. Nó chỉ tạo next-event context từ event
thứ 11; trace dài từ 10 event trở xuống không có context và implementation trả
score **0**.

| Nhóm anomaly | Số sample | Trace `<=10` event | Có OOV target sau context | DeepLog score 0 |
|---|---:|---:|---:|---:|
| Validation | 2,044 | 464 (22.7%) | 1,284 (62.8%) | 464 |
| Final | 1,679 | 1,033 (61.5%) | 533 (31.7%) | 1,033 |

Do đó, 1,033 trong 1,065 false negative DeepLog final (xấp xỉ 97%) là trace
ngắn bị score 0 ngay từ thiết kế scoring hiện tại. Ngược lại, validation có
nhiều anomaly dài hơn và có OOV EventId sau context hơn. Với implementation
này, OOV ở vị trí target nhận surprise score 1, nên DeepLog validation nhận tín
hiệu mạnh hơn: anomaly score median 1.0 thay vì 0.0 ở final.

Vocabulary DeepLog frozen chỉ gồm 15 EventId normal-train; đây là đúng protocol
normal-only nhưng khiến hiệu năng nhạy với độ dài trace và vị trí EventId chưa
thấy trong sequence.

## Ý nghĩa đối với Fusion

Fusion final vẫn đạt recall 0.9988 và F1 0.8718 vì Rule và DeepLog bổ sung nhau
trên các nhóm anomaly khác nhau. Tuy nhiên F1 final thấp hơn F1 validation
(0.8718 so với 0.9985), do validation được dùng để chọn threshold/weight và
final có distribution khác. Khi báo cáo, dùng metric final làm kết quả chính.

## Điều không được làm

Không đổi epoch, sequence length, threshold hoặc fusion weight dựa vào final
test hiện tại. Đây sẽ là test leakage và làm metric final mất ý nghĩa.

## Hướng cải thiện hợp lệ sau báo cáo

Trên **validation mới hoặc development data mới**, có thể thử:

1. Sequence length nhỏ hơn hoặc scoring riêng cho trace ngắn.
2. Hybrid routing: Rule cho short trace, DeepLog cho trace đủ context.
3. Chính sách OOV/aggregation khác cho DeepLog.

Sau khi chọn bằng validation, phải dùng một hold-out test mới, chưa từng được
quan sát, để đánh giá lại.

## Artifact để đối chiếu

- Rule validation: `data/processed/evaluation/hdfs_v1_final_rule_checksum_20260907/`
- DeepLog validation: `data/processed/evaluation/hdfs_v1_final_deeplog_epoch1_50000_20260909/`
- HDFS final: `data/processed/evaluation/hdfs_v1_final_test_20260910/`
- DeepLog bundle metadata: `data/models/evaluation/hdfs_v1_final_deeplog_epoch1_50000_20260909/deeplog/deeplog_metadata.json`
