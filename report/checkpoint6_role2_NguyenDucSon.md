# Checkpoint 6 – Role 2 – Nguyễn Đức Sơn

## Mục tiêu

Phục hồi clean dataset từ đúng raw-record snapshot đã dùng ở baseline, không sửa tay corrupted data và không sao chép baseline thành repaired artifact.

## Phần đã hoàn thiện

Bổ sung `src/ingestion/repair.py` với ba nhóm chức năng:

1. `repair_from_raw_records(...)`
   - Nhận `list[PaperRecord]` từ raw snapshot đáng tin cậy.
   - Chạy lại `build_clean_dataframe` với cùng cleaning contract.
   - Lưu repaired CSV/JSON vào path riêng.
   - Tạo `repair_audit.json` để chứng minh lineage và recovery.

2. `validate_repaired_dataframe(...)`
   - Kiểm tra đủ clean schema.
   - Kiểm tra `paper_id` unique.
   - Không còn title/summary/text embedding rỗng.
   - Không có `age_days` âm.

3. `compare_recovery_states(...)`
   - So sánh row count, unique ID, duplicate, blank summary và noise giữa baseline/corrupted/repaired.
   - Liệt kê baseline ID còn thiếu sau repair.
   - Liệt kê ID bất thường xuất hiện sau repair.
   - Chỉ đánh dấu phục hồi đầy đủ khi ID set repaired khớp baseline.

## Evidence và lineage

Audit log chứa:

- `repair_source = raw_records_snapshot`
- SHA-256 của toàn bộ raw records
- raw record count
- cleaning statistics
- validation signals
- baseline/corrupted/repaired comparison
- đường dẫn repaired artifacts

Cách làm này chứng minh repaired dataset được tái tạo từ nguồn raw và cleaning logic, không phải chỉnh tay output.

## Artifact kỳ vọng

```text
data/clean/papers_repaired.csv
data/clean/papers_repaired.json
data/quality/repair_audit.json
```

Các role RAG/Evaluation/Observability tiếp tục dùng repaired dataset để tạo:

```text
data/results/repaired_metrics.json
data/results/repaired_answers.json
data/reports/corruption_report.md
```

## Lệnh kiểm thử

```powershell
python -m pytest tests/test_repair.py -q
```

## Tiêu chí hoàn thành Role 2

- Repair bắt đầu từ raw records, không bắt đầu từ corrupted dataframe.
- Repaired artifacts dùng path riêng, không ghi đè baseline/corrupted.
- Schema repaired hợp lệ và `paper_id` unique.
- Có audit log chứng minh raw lineage và ID recovery.
- Có dữ liệu so sánh clean/corrupted/repaired để demo trung thực.
