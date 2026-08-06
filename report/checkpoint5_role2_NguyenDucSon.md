# Checkpoint 5 – Role 2 – Nguyễn Đức Sơn

## Mục tiêu

Triển khai corruption có kiểm soát trên clean dataset để nhóm có thể đo ảnh hưởng tới quality, freshness, retrieval và evaluation mà không làm thay đổi baseline hoặc raw source.

## Phần đã hoàn thiện

File `src/ingestion/corruption.py` đã triển khai hàm:

```python
corrupt_clean_dataframe(df, output_log_path)
```

Hàm tạo bản sao độc lập của clean dataframe và áp dụng sáu dạng lỗi:

1. Xóa một số record mới nhất theo `published`.
2. Làm rỗng `summary` của một số record.
3. Chèn noise có marker rõ ràng vào `summary`.
4. Cắt ngắn `title`.
5. Làm `published` cũ đi 10 năm.
6. Thêm duplicate rows.

Sau khi thay đổi title, summary hoặc published, hàm xây dựng lại `text_for_embedding` để corrupted index phản ánh đúng dữ liệu bị lỗi.

## Corruption log contract

Log JSON chứa:

- `schema_version`
- `created_at_utc`
- `source_row_count`
- `corrupted_row_count`
- `source_unique_paper_ids`
- `corrupted_unique_paper_ids`
- `event_count`
- `events`

Mỗi event chứa:

- `corruption_type`
- `paper_id`
- `parameter`
- `before`
- `after`

Nhờ vậy có thể truy ngược record bị tác động và đối chiếu signal với corruption cụ thể.

## Bảo vệ baseline và raw source

- Không sửa dataframe đầu vào.
- Không đọc hoặc ghi vào `data/raw/`.
- Không fetch source mới.
- Không ghi đè baseline clean dataset.
- Chỉ ghi corruption log vào path được pipeline truyền vào.
- Output corrupted được trả về cho pipeline lưu vào path riêng.

## Kiểm thử

Đã bổ sung `tests/test_corruption.py` để kiểm tra:

- Input dataframe không bị mutate.
- Đủ sáu loại corruption.
- Corruption log có record ID, parameter và before/after.
- Duplicate, missing summary và noise xuất hiện thực tế.
- `text_for_embedding` được rebuild.
- Hàm từ chối dataframe rỗng hoặc sai schema.

## Lệnh chạy

```powershell
python -m pytest tests/test_corruption.py -q
python script/run_corruption_flow.py
```

## Artifact kỳ vọng sau khi pipeline tích hợp

```text
data/clean/papers_corrupted.csv
data/clean/papers_corrupted.json
data/quality/corruption_log.json
data/results/corrupted_answers.json
data/results/corrupted_metrics.json
data/quality/corrupted-quality.json
data/reports/corruption_report.md
```

Role 2 bàn giao corrupted dataframe và corruption log cho Role 1/3/4 tiếp tục rebuild index, evaluate và tạo quality/report artifacts.
