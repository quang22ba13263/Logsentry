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
| HDFS v1 | `Dataset/HDFS_v1/preprocessed/Event_occurrence_matrix.csv` | `59ab8b8a6d12f18f41b35e9eb0113655825b9bf9d9787c1a6f72fface7cc01a7` |

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
| `joblib` | `1.6.0` | `>=1.3.0` |

Các package trên đã được import runtime thành công. `Flask 3.1.3`,
`SQLAlchemy 2.0.52` và `statsmodels 0.15.0` cũng import được. Bộ 29 unit test
hiện tại trong `evaluation/tests` pass với interpreter này.

Trước khi chạy benchmark chính thức, lưu output của các lệnh sau vào
`manifest.json` để gắn kết quả với đúng môi trường thực thi:

```bash
python --version
python -m pip check
python -m pip show pandas numpy scikit-learn tensorflow
python -m unittest discover -s evaluation/tests -t . -v
```

- Random seed chung: `42` (NumPy, scikit-learn, TensorFlow).

## Model bundle tái lập

Các run mới lưu candidate runtime ở
`data/models/evaluation/<run_id>/`. Isolation Forest bundle gồm model, fitted
`RobustScaler`, reference score distribution và transformer (nếu có); DeepLog
bundle gồm `.keras`, vocabulary và config. Mỗi bundle có
`bundle_manifest.json` chứa SHA-256 của file bên trong. Chỉ load bundle tạo từ
run tin cậy cục bộ; không deserialize artifact không rõ nguồn gốc.

## Chạy benchmark và khóa test hold-out

Mặc định, runner chỉ fit train-normal và đo/tune trên **validation**. Nó không
score test split, và `split.csv` cũng không ghi nhãn test. Dùng mode này cho mọi
vòng phát triển/tuning; mỗi vòng phải có `run_id` riêng:

```bash
python evaluation/runners/run_bgl.py --config evaluation/config/bgl_v1.yaml --run-id bgl_dev_v2
python evaluation/runners/run_hdfs_smoke.py --run-id hdfs_dev_v2 --deeplog-train-limit 2000 --deeplog-epochs 1
```

Chỉ sau khi ghi lại và khóa hẳn config/threshold/model version, mới thêm
`--final-test` để chạy **một lần** test hold-out. Không dùng output test cũ để
chọn hyperparameter, threshold hoặc fusion weight. Artifact tạo trước guard này
chỉ là diagnostic, không phải kết quả cuối.

Xem [evaluation_protocol.md](evaluation_protocol.md) để biết split, ngăn rò rỉ
nhãn và quy tắc đánh giá bắt buộc.

HDFS có hai config riêng: `config/hdfs_final_test_template.yaml` là template
không thể chạy, còn `config/hdfs_final_candidate_v1.yaml` là candidate đã khóa
từ validation. Ngay cả candidate đã khóa vẫn **không** score test nếu thiếu cả
`--release-sealed-test` và token xác nhận; không dùng lệnh này nếu chưa có phê
duyệt rõ ràng.

BGL có `config/bgl_final_candidate_v1.yaml` và runner riêng
`runners/run_bgl_final_test.py`. Đây là **post-diagnostic confirmation**, không
phải hold-out test chưa từng quan sát: chỉ Isolation Forest 200 trees/seed 42
được score vì Rule và DeepLog không vượt fusion gate. Cả BGL lẫn HDFS final
runner chỉ nạp model bundle đã hash-verify, bắt buộc release flag/token và từ
chối chạy khi Git working tree còn thay đổi. Các bundle ở `data/models/` bị
ignore, nên phải có mặt cục bộ hoặc được giao kèm repository, không commit vào
Git.
