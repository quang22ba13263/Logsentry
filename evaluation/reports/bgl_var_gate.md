# BGL v1 VAR data-quality gate

Kiểm tra ngày 2026-09-07 trên `BGL_2k.log_structured.csv` (2.000 event):

| Điều kiện VAR | Kết quả |
| --- | --- |
| Chuỗi thời gian đều, có mật độ đủ | Không đạt |
| Active day | 166 / 215 ngày lịch |
| Median event / active day | 3 |
| Khoảng event / active day | 1–150 |
| Active day có anomaly | 35 |

**Quyết định:** `VAR = N/A` cho BGL v1. Event phân bố quá thưa và không đều;
resample thành zero-window sẽ tạo cấu trúc synthetic và không còn là đánh giá
độc lập với dataset. VAR không được đưa vào `log_only_fusion` BGL v1.
