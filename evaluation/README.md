# Log-only evaluation

Thư mục này chứa benchmark độc lập cho LogSentry AI trên dữ liệu log công khai
có ground truth. Nó không sửa worker realtime hoặc bất cứ tệp nào trong
`Dataset/`.

## Nguồn dữ liệu

Đặt các input chỉ đọc tại các đường dẫn sau (không commit chúng):

| Dataset | Input | SHA-256 |
| --- | --- | --- |
| BGL 2k | `Dataset/BGL/BGL_2k.log_structured.csv` | `3fe74103c0b02a28514534e2a47257a3f770135ca61afd425bbd3b9d6a31fe26` |
| HDFS v1 | `Dataset/HDFS_v1/preprocessed/Event_traces.csv` | `68cd80eac007b28f5ca10d8acceb104d61067e74e1c4eef2c6c6015b2d769d3c` |
| HDFS v1 | `Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv` | `59ab8a8a6d12f18f41b35e9eb0113655825b9bf9d9787c1a6f72fface7cc01a7` |

Tải BGL và HDFS v1 từ nguồn Loghub/public dataset tương ứng, rồi đặt đúng cấu
trúc trên. Xác nhận checksum trước khi chạy; dataset là input chỉ đọc.

## Cấu trúc

```text
evaluation/
  config/             # YAML versioned cho mỗi benchmark
  adapters/           # Dataset → common evaluation contract
  detectors/          # Detector benchmark, không ảnh hưởng realtime worker
  features/           # Transformer fit chỉ trên train-normal
  runners/            # Lệnh chạy reproducible
  reports/            # Chỉ chứa placeholder/tài liệu; artifact runtime bị ignore
  tests/              # Unit và leakage tests
```

Artifact runtime phải nằm ở `data/processed/evaluation/<run_id>/` và model ở
`data/models/evaluation/<run_id>/`; cả hai đều bị Git ignore.

## Môi trường đã xác minh cho protocol v1

Kiểm tra ngày 2026-09-06 bằng interpreter đang hoạt động:

- Python: `3.13.15` tại `C:\Program Files\Python313\python.exe`.
- Repository hiện không có `.venv` hoặc `pyvenv.cfg`; interpreter trên là Python
  cài hệ thống, không phải virtual environment cục bộ. Nếu dùng venv ở nơi khác,
  hãy chạy lại các lệnh kiểm tra bên dưới từ interpreter của venv đó và ghi vào
  `manifest.json` của từng run.
- `python -m pip check`: pass, không có dependency hỏng.

| Package | Version đã import | Yêu cầu tối thiểu trong `requirements.txt` |
| --- | --- | --- |
| `pandas` | `3.0.5` | `>=1.5.0` |
| `numpy` | `2.5.2` | `>=1.23.0` |
| `scikit-learn` | `1.9.0` | `>=1.2.0` |
| `tensorflow` | `2.21.0` | `>=2.12.0` |

Các package trên đã được import runtime thành công. `Flask 3.1.3`,
`SQLAlchemy 2.0.52` và `statsmodels 0.15.0` cũng import được. Bộ 11 unit test
trong `evaluation/tests` pass với interpreter này.

Trước khi chạy benchmark chính thức, lưu output của các lệnh sau vào
`manifest.json` để gắn kết quả với đúng môi trường thực thi:

```bash
python --version
python -m pip check
python -m pip show pandas numpy scikit-learn tensorflow
python -m unittest discover -s evaluation/tests -t . -v
```

- Random seed chung: `42` (NumPy, scikit-learn, TensorFlow).

## Chạy benchmark

Sau khi các runner được triển khai, dùng các config đã versioned:

```bash
python evaluation/runners/run_bgl.py --config evaluation/config/bgl_v1.yaml
python evaluation/runners/run_hdfs.py --config evaluation/config/hdfs_v1.yaml
```

Xem [evaluation_protocol.md](evaluation_protocol.md) để biết split, ngăn rò rỉ
nhãn và quy tắc đánh giá bắt buộc.
