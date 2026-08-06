# Role 6 — Observability handoff (Checkpoint 0)

## Scope

Role 6 định nghĩa các tín hiệu cần theo dõi để chứng minh data quality và freshness ảnh hưởng tới RAG. CP0 chốt contract và artifact; implementation quality checks/report chạy ở checkpoint sau.

## Quality signals

| Signal | Cách tính | Baseline expectation |
|---|---|---|
| `row_count` | Số record sau mỗi stage | Raw và clean count phải được ghi lại |
| `paper_id_null` | Đếm `paper_id` rỗng/null | `0` sau cleaning |
| `paper_id_duplicate` | `count - nunique` | `0` sau cleaning |
| `title_null` | Đếm title rỗng/null | `0` sau cleaning |
| `summary_null` | Đếm summary rỗng/null | Ghi rõ; baseline hiện không thiếu |
| `summary_chars` | Độ dài summary | Dùng để phát hiện summary rỗng/quá ngắn |
| `source_parse_drop` | Raw items trừ parsed records | Phải truy vết được lý do loại |
| `category_missing` | Record có category fallback/rỗng | Baseline hiện có 24/24 thiếu category thật |

## Freshness signals

- `latest_published`: ngày published mới nhất.
- `oldest_published`: ngày published cũ nhất.
- `stale_rows`: số record có `age_days` vượt threshold.
- `total_rows`: tổng record được kiểm tra.
- `is_fresh`: true khi không có stale record theo threshold cấu hình.
- `source_snapshot_timestamp`: thời điểm fetch/snapshot để phân biệt dữ liệu cũ với dữ liệu mới.

Threshold hiện tại trong `core.config` là `180` ngày. Tất cả trạng thái baseline/corrupted/repaired phải dùng cùng threshold.

## Artifact contract

- Quality payload: `data/quality/<report_name>.json`.
- Freshness payload: `data/quality/freshness_report.json`.
- Great Expectations output: `data/quality/gx/`.
- Baseline report: `data/reports/phase1_report.md`.
- Corruption comparison: `data/reports/corruption_report.md`.

Mỗi report phải ghi input path, report name, row count, pass/fail checks, freshness fields và timestamp; không hard-code trạng thái pass.

## CP0 evidence đã xác định

- Raw và clean snapshot hiện có 24 record.
- `paper_id` clean unique.
- `text_for_embedding`, `age_days`, `summary_chars` đã có trong clean schema.
- Snapshot có 24/24 record thiếu category thật; đây là missingness cần report, không được che bằng kết luận quality pass.

## Handoff cho checkpoint sau

1. Implement `run_data_quality_checks` và ghi từng check/result/count.
2. Implement `build_freshness_report` từ `published`/`age_days`.
3. Generate baseline report từ JSON/CSV thật.
4. Chạy lại cùng checks trên corrupted và repaired dataset để so sánh.
