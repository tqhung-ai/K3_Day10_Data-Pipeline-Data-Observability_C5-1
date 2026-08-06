# Checkpoint 5 — Controlled corruption evidence

## Scope

CP5 applies deterministic corruption to a deep copy of the clean baseline. The
baseline dataset, baseline embeddings, baseline collection, evaluation set and
baseline metrics remain unchanged. Repair and the repaired comparison are
deferred to the next checkpoint.

## Corruption log

The flow writes `data/results/corruption_log.json` and records the affected
`paper_id`, operation type, before/after value or count, and the operation
parameter. The scenario performs:

1. Drop the newest publication.
2. Blank one evaluation paper summary.
3. Inject deterministic noise into another evaluation paper summary.
4. Truncate one evaluation paper title.
5. Set one publication date to `2024-01-01`, older than the 180-day threshold.
6. Add one exact duplicate row.

Output is written only to corrupted-specific paths, including
`papers_clean_corrupted.*`, `papers_embeddings_corrupted.json`,
`corruption_log.json`, `corrupted_metrics.json`, `corrupted_answers.json`,
`quality/corrupted.json`, and `quality/freshness_corrupted.json`.

## Observed results

| Signal | Baseline | Corrupted | Interpretation |
|---|---:|---:|---|
| Rows | 24 | 24 | One dropped row is offset by one duplicate |
| Unique paper IDs | 24 | 23 | Duplicate corruption detected |
| Retrieval hit rate | 1.0000 | 1.0000 | Retrieval still finds the target in this run |
| Mean token F1 | 0.7518 | 0.7324 | Answer overlap degraded |
| Judge accuracy | 0.6667 | 0.6667 | No change in this sample |
| Mean judge score | 3.75 | 3.75 | No change in this sample |
| Freshness | true | false | One stale row detected |
| Data quality | true | false | Duplicate ID and short/blank summary detected |

The controlled corruption therefore produces observable data-quality and
freshness failures and a measurable token-F1 reduction. Retrieval hit rate and
judge metrics did not change; they are reported as observed rather than being
claimed as impacted.

## Verification command

```powershell
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

The flow requires the baseline artifacts and reuses the frozen 12-sample
evaluation set.
