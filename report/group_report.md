# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Trường | Giá trị |
|---|---|
| Khóa/lớp | K3 |
| Tên nhóm | Data Pipeline & Data Observability — C5-1 |
| Repository | https://github.com/tqhung-ai/K3_Day10_Data-Pipeline-Data-Observability_C5-1 |
| Ngày hoàn thành | 2026-08-06 |

| Role | Thành viên | MSSV | Phạm vi | Deliverable chính |
|---|---|---|---|---|
| Role 1 | Trần Quốc Hùng | 2A202601683 | Integration/release QA | Handoff, kiểm tra artifact và release |
| Role 2 | Nguyễn Đức Sơn | 2A202601485 | Crossref ingestion | `src/ingestion/crossref.py`, raw snapshots |
| Role 3 | Phạm Thế Dũng | 2A202601985 | Cleaning/corruption/repair | `cleaning.py`, `corruption.py`, repair flow |
| Role 4 | Phạm Văn Lưu | 2A202601857 | RAG/index/agent | Chroma collections, retrieval và agent |
| Role 5 | Nguyễn Huy Nghĩa | 2A202601943 | Evaluation | Test set, answers và metrics |
| Role 6 | Nguyễn Thế Anh | 2A202601791 | Observability/reporting | Quality, freshness và comparison report |

## 2. Tóm tắt kết quả

Pipeline đã chạy từ Crossref raw snapshot qua cleaning, MiniLM embeddings,
ChromaDB, evaluation, quality/freshness, controlled corruption và repair. Baseline
có 24 records sạch và evaluation set cố định 12 câu hỏi. CP5 tạo sáu dạng lỗi có
log đầy đủ: drop bản ghi mới nhất, blank/noise summary, truncate title, stale
date và duplicate row. Corrupted data làm quality và freshness fail; mean token-F1
giảm từ `0.7518` xuống `0.7324`. CP6 tạo lại dữ liệu từ raw thay vì sửa corrupted
thủ công. Repaired data có 24 unique IDs, quality/freshness pass và toàn bộ metric
evaluation khôi phục đúng baseline. Judge metrics không thay đổi trong sample này;
nhóm chỉ kết luận những thay đổi có bằng chứng trong artifact.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API/snapshot
  -> data/raw/crossref_response.json + crossref_records.json
  -> cleaning và deduplication
  -> clean CSV/JSON + text_for_embedding
  -> MiniLM + ChromaDB (papers-baseline)
  -> evaluation/quality/freshness baseline
  -> deterministic corruption (papers-corrupted)
  -> evaluation/quality/freshness corrupted
  -> reload raw + cleaning repair (papers-repaired)
  -> evaluation/quality/freshness repaired
  -> data/reports/corruption_report.md
```

| Khối | Input | Output | Owner |
|---|---|---|---|
| Ingestion | Crossref response | `data/raw/` | Role 2 |
| Cleaning | `PaperRecord` list | `data/clean/papers_clean.*` | Role 3 |
| Index/agent | clean dataframe | embeddings và `papers-baseline` | Role 4 |
| Evaluation | index + `data/eval/test_set.json` | answers/metrics | Role 5 |
| Observability | clean dataframe | quality/freshness JSON | Role 6 |
| Corruption/repair | clean copy/raw snapshot | corrupted/repaired artifacts | Role 3 |
| Integration | tất cả stage | phase1/corruption flow và reports | Role 1 + Role 3 |

## 4. Cấu hình và cách tái hiện

| Thiết lập | Giá trị |
|---|---|
| LLM provider/model | Gemini / `gemini-2.5-flash` theo cấu hình mặc định |
| Embedding | `sentence-transformers/all-MiniLM-L6-v2` |
| Records | 24 |
| Evaluation samples | 12 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày |
| Collections | `papers-baseline`, `papers-corrupted`, `papers-repaired` |

```powershell
python script/run_phase1.py
python script/run_corruption_flow.py
python -m unittest discover -s tests -v
```

Flow dùng raw snapshot khi snapshot đã tồn tại và không refresh; các trạng thái
dùng chung `data/eval/test_set.json`.

## 5. Artifact và baseline

| Artifact | Trạng thái |
|---|---|
| Raw response/records | Có, 24 records |
| Clean CSV/JSON | Có, 24 records |
| Embedding manifest/index | Có |
| Evaluation set | Có, 12 samples |
| Baseline metrics/answers | Có |
| Quality/freshness | Có và baseline pass |
| Baseline report | Có tại `data/reports/phase1_report.md` |

| Metric | Baseline |
|---|---:|
| `retrieval_hit_rate` | 1.0000 |
| `mean_token_f1` | 0.7518 |
| `judge_accuracy` | 0.6667 |
| `mean_judge_score` | 3.7500 |

## 6. Corruption, repair và comparison

| Corruption | Signal quan sát được | Cách repair |
|---|---|---|
| Drop newest | row lineage thay đổi | reload raw và clean lại |
| Blank summary | summary gate fail | lấy summary từ raw |
| Summary noise | nội dung embedding bị nhiễu | clean lại từ raw |
| Truncated title | title evidence bị mất | lấy title từ raw |
| Stale date | freshness fail | lấy published từ raw |
| Duplicate row | `paper_id_unique` fail | deduplicate trong cleaning |

Log chi tiết nằm tại `data/results/corruption_log.json`. Repair được thực hiện
bằng `load_raw_records()` rồi `build_clean_dataframe()`, không sửa answers hoặc
metrics bằng tay.

| Signal/metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Rows | 24 | 24 | 24 |
| Unique paper IDs | 24 | 23 | 24 |
| Retrieval hit rate | 1.0000 | 1.0000 | 1.0000 |
| Mean token-F1 | 0.7518 | 0.7324 | 0.7518 |
| Judge accuracy | 0.6667 | 0.6667 | 0.6667 |
| Mean judge score | 3.7500 | 3.7500 | 3.7500 |
| Quality | PASS | FAIL | PASS |
| Freshness | PASS | FAIL | PASS |

Kết luận nhân quả thứ nhất: duplicate/blank summary/stale date làm corrupted
quality và freshness fail, đồng thời token-F1 giảm. Retrieval hit rate vẫn là
1.0 nên không được kết luận rằng mọi metric agent đều bị ảnh hưởng.

Kết luận thứ hai: repair từ raw khôi phục unique IDs, summary, ngày xuất bản,
quality/freshness và token-F1 về baseline.

## 7. Kiểm thử và giới hạn

- `6/6` unit tests trong `tests/` pass.
- `compileall` cho `src/` pass.
- Artifact audit xác nhận đủ raw/clean/eval/embedding/results/quality/report.
- Ragas được skip theo cấu hình mặc định (`RUN_RAGAS=1` mới chạy).
- Judge metrics phụ thuộc provider và sample nhỏ; không dùng chúng để khẳng định
  tác động khi số liệu không thay đổi.
- Tên/MSSV thành viên cần được bổ sung trước khi nộp chính thức.

## 8. Checklist nộp bài

- [x] Raw, clean, embedding, evaluation, quality và report artifacts tồn tại.
- [x] Baseline/corrupted/repaired dùng chung evaluation set.
- [x] Corruption log có record ID, before/after và parameter.
- [x] Repair chạy từ raw snapshot và dùng collection riêng.
- [x] Metrics và quality/freshness khớp artifact thực tế.
- [x] Source không còn TODO student/NotImplementedError.
- [x] Không có `.env`, API key hoặc secret trong source/report.
- [x] Bổ sung tên và MSSV của 6 thành viên.
