# Checkpoint 4 – Role 2 – Nguyễn Đức Sơn

## 1. Vai trò và mục tiêu

- **Vai trò:** Role 2 – Data foundation & recovery.
- **Phạm vi:** `src/ingestion/`, `data/raw/`, `data/clean/`.
- **Mục tiêu Checkpoint 4:** đóng băng baseline, bảo toàn raw source dùng cho repair và chuẩn bị corruption scenario cho Checkpoint 5.

Checkpoint 4 là mốc nghỉ 15 phút và rà soát baseline. Chưa chạy corruption ở mốc này.

## 2. Baseline freeze checklist

Trước khi bắt đầu Checkpoint 5, xác nhận các artifact sau tồn tại và đọc được:

- [ ] Raw API response trong `data/raw/`.
- [ ] Raw records đã parse trong `data/raw/`.
- [ ] Clean CSV/JSON trong `data/clean/`.
- [ ] `paper_id` trong clean data là duy nhất.
- [ ] `text_for_embedding` không rỗng.
- [ ] `age_days` đã được tính.
- [ ] Evaluation test set đã khóa trong `data/eval/`.
- [ ] Embedding manifest và baseline collection tồn tại.
- [ ] Baseline answers tồn tại.
- [ ] `data/results/baseline_metrics.json` tồn tại.
- [ ] Data quality và freshness artifacts tồn tại trong `data/quality/`.
- [ ] `data/reports/phase1_report.md` tồn tại và khớp artifact thật.

## 3. Quy tắc bảo toàn baseline

Trong Checkpoint 5 và Checkpoint 6 phải tuân thủ:

1. Không sửa hoặc ghi đè raw snapshot dùng cho baseline.
2. Không ghi đè clean baseline dataset.
3. Không ghi đè baseline embedding collection.
4. Không thay đổi test set, ground truth, evaluator hoặc retrieval top-k.
5. Corrupted và repaired states phải dùng path/collection riêng.
6. Repair phải chạy lại từ raw source đáng tin cậy, không sửa tay answers hoặc metrics.
7. Mọi corruption phải có log gồm record ID, loại lỗi, tham số và before/after.

## 4. Raw source dùng làm điểm khôi phục

Raw artifacts trong `data/raw/` là nguồn sự thật để phục hồi dữ liệu ở Checkpoint 6.

Lineage dự kiến:

```text
Crossref raw response
    -> raw records
    -> cleaned baseline data
    -> corrupted clean data
    -> repaired clean data được tạo lại từ raw records
```

Khi repair:

- Nạp đúng raw snapshot đã dùng cho baseline.
- Chạy lại cleaning bằng cùng rule baseline.
- Không fetch source mới giữa quá trình so sánh.
- Đối chiếu `paper_id` của các record bị corrupt/drop để chứng minh đã phục hồi.

## 5. Corruption scenario chuẩn bị cho Checkpoint 5

Các corruption có chủ đích sẽ áp dụng trên bản sao của clean data:

| Scenario | Cách tạo lỗi | Signal kỳ vọng | Cách repair |
|---|---|---|---|
| Drop latest records | Xóa một số record mới nhất | Row count giảm, freshness xấu hơn, retrieval có thể mất tài liệu đúng | Re-run cleaning từ raw snapshot |
| Missing summary | Làm rỗng summary của một số record | Missing summary tăng, text embedding kém thông tin | Khôi phục summary từ raw records |
| Summary noise | Chèn noise vào summary | Retrieval/token F1 có thể giảm | Re-clean từ raw source |
| Old publication date | Dịch ngày xuất bản về quá khứ | `age_days` tăng, freshness report xấu | Parse lại ngày từ raw source |
| Duplicate records | Nhân bản một số record | Duplicate count tăng, unique paper_id check fail | Dedupe lại bằng stable ID |

## 6. Corruption log contract

Mỗi corruption event cần có tối thiểu:

```json
{
  "corruption_type": "missing_summary",
  "paper_id": "stable-paper-id",
  "parameters": {},
  "before": {},
  "after": {}
}
```

Log tổng phải lưu tại:

```text
data/results/corruption_log.json
```

## 7. Expected impact

Sau corruption, dự kiến quan sát được ít nhất một trong các thay đổi:

- `row_count` giảm hoặc tăng bất thường.
- `missing_summary_count` tăng.
- `duplicate_count` tăng.
- Freshness signal xấu hơn.
- `retrieval_hit_rate` giảm.
- `mean_token_f1` giảm.
- Một số câu trả lời không còn truy xuất đúng `ground_truth_doc_ids`.

Không kết luận corruption làm RAG kém nếu artifact thực tế không chứng minh được thay đổi.

## 8. Repair acceptance criteria

Repair được coi là hợp lệ khi:

- Repaired dataset được sinh lại từ raw snapshot.
- Repaired path khác baseline và corrupted path.
- Schema clean hợp lệ.
- `paper_id` unique.
- Missing/duplicate/freshness signals phục hồi gần baseline.
- Các record bị drop/corrupt xuất hiện lại đúng theo lineage.
- `repaired_metrics.json` được đánh giá bằng test set cũ.

## 9. Blocker cần kiểm tra trước Checkpoint 5

Chạy các lệnh sau tại project root:

```powershell
Test-Path data/results/baseline_metrics.json
Test-Path data/reports/phase1_report.md
Get-ChildItem data/raw -Recurse -File
Get-ChildItem data/clean -Recurse -File
Get-ChildItem data/eval -Recurse -File
Get-ChildItem data/quality -Recurse -File
Get-Content data/results/baseline_metrics.json
```

Nếu baseline artifact còn thiếu, chưa được chạy corruption flow.

## 10. Kết luận Checkpoint 4

Baseline được giữ làm mốc đối chiếu. Raw source được xác định là điểm khôi phục chính thức. Corruption scenario, signal kỳ vọng và repair strategy đã được chuẩn bị cho Checkpoint 5 mà không thay đổi baseline artifacts.
