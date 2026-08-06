# Vai trò 2 — Bàn giao checkpoint 2

## Trạng thái

Các dependency cleaning, test set và baseline index đã được dựng từ raw snapshot CP0–CP1 mà
không fetch lại Crossref.

| Hạng mục | Kết quả |
| --- | --- |
| Raw → clean | `24 → 24`, không drop, không duplicate |
| Clean schema | `paper_id` unique; không có `text_for_embedding` rỗng |
| Test set | 6 câu: summary, authors, date |
| Baseline index | Collection `papers-baseline`, 24 documents |
| Semantic search | Có 4 nguồn; source đúng đứng top 1 trong smoke query |
| Exact lookup | Đúng theo cả `paper_id` và title |
| Retrieval QA | 6/6 câu có ground-truth DOI trong retrieved sources |
| LLM agent | Chờ cấu hình credential/provider |

Không tạo câu hỏi category vì cả 24 raw record đều thiếu `subject`. Đây là missing source data,
không được thay bằng ground truth `Uncategorized`.

## Artifact

- `data/clean/papers_clean.csv`
- `data/clean/papers_clean.json`
- `data/eval/test_set.json`
- `data/embeddings/papers_embeddings.json`
- `data/chroma/` với collection `papers-baseline`
- `data/results/agent_demo_answers.json`
- `data/results/checkpoint2_evidence.json`

Embedding manifest lưu `persist_path` tương đối (`data/chroma`) để có thể load sau khi clone repo
sang máy khác.

## Lineage sample

```text
paper_id: 10.2118/234689-pa
raw paper_id == clean paper_id == document paper_id == index metadata paper_id
exact ID lookup: pass
exact title lookup: pass
semantic search: top 1
```

Chi tiết title, source URL, retrieved IDs, score và SHA-256 raw snapshot nằm trong
`data/results/checkpoint2_evidence.json`.

## Chạy lại không refresh nguồn

```powershell
$env:HF_HUB_OFFLINE='1'
uv run python script/run_checkpoint2.py
```

Lần đầu tải MiniLM cần internet; các lần sau có thể dùng cache offline.

Để chạy agent thật sau khi cấu hình `.env`:

```powershell
$env:RUN_LLM_AGENT='1'
uv run python script/run_checkpoint2.py
```

Chỉ coi LLM agent smoke test hoàn tất khi `llm_agent_smoke.status` trong evidence là `passed`.
