# Role 1 — Integrator & release handoff (Checkpoint 0)

## Ownership đã chốt

| Role | Phạm vi | Artifact bàn giao |
|---|---|---|
| Role 1 | Tích hợp, release, QA và handoff | Checklist, lệnh xác minh, luồng end-to-end |
| Role 2 | Crossref ingestion | `data/raw/crossref_response.json`, `crossref_records.json` |
| Role 3 | Cleaning và data modeling | `data/clean/papers_clean.csv`, `papers_clean.json` |
| Role 4 | RAG và agent | Embedding manifest, Chroma collection, smoke-query evidence |
| Role 5 | Evaluation | `data/eval/test_set.json`, answers và metrics |
| Role 6 | Observability | Quality, freshness và report artifacts |

## Handoff contract

```text
Crossref API
  → data/raw/crossref_response.json
  → data/raw/crossref_records.json
  → data/clean/papers_clean.csv + papers_clean.json
  → data/embeddings/ + data/chroma/
  → data/eval/test_set.json
  → data/results/ + data/quality/
  → data/reports/
```

- `paper_id` là DOI chuẩn hóa và phải giữ nguyên qua raw → clean → index → evaluation.
- Baseline, corrupted và repaired phải dùng path/collection riêng.
- Corruption chỉ chạy sau khi baseline có đủ artifact.
- Repair phải chạy lại từ raw, không sửa tay answers hoặc metrics.
- Mỗi report phải trỏ tới artifact và số liệu thật.

## Definition of Done của CP0

- [x] Có owner và output rõ cho cả 6 role.
- [x] Raw response và raw records tồn tại.
- [x] `paper_id` ổn định và unique trong snapshot hiện tại.
- [x] Clean CSV/JSON tồn tại và có schema dùng được cho downstream.
- [x] Evaluation test set tồn tại với ground-truth document IDs thật.
- [x] Role 4 và Role 6 đã có contract/handoff để tiếp tục checkpoint sau.
- [x] Không merge checkpoint sau vào CP0 scope; baseline/corruption vẫn là việc tiếp theo.

## Lệnh xác minh

```powershell
Get-ChildItem data/raw
Get-ChildItem data/clean
Get-ChildItem data/eval
```

CP0 được coi là hoàn tất khi các artifact trên tồn tại và các owner giải thích được input/output của mình.
