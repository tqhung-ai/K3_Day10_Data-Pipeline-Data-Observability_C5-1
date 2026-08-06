# Checkpoint 4 — Corruption preparation and handoff

CP4 is the 15-minute break and preparation gate between baseline and corruption. No baseline artifact is changed in this checkpoint.

## Frozen baseline

| Item | Value |
|---|---|
| Raw records | 24 |
| Clean records | 24 |
| Unique paper IDs | 24 |
| Evaluation samples | 12 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 0.7518 |
| Judge accuracy | 0.6667 |
| Mean judge score | 3.75 |
| Latest published | 2026-08-01 |
| Oldest published | 2026-02-12 |
| Raw response SHA-256 | `1DC4EF94694D97CFB26BF07E0D97A1DC661F3C62D3127D561DF1629BE74DD387` |
| Raw records SHA-256 | `DFA730DA4DCB14A6ACCB35B2DA1EBC1806B2010B0A3E08EB3EE0D64A870E01F1` |

The evaluation set, evaluator, embedding model, `top_k=4`, and baseline collection `papers-baseline` are frozen.

## Controlled corruption scenario for CP5

Apply deterministic corruption to a copy of clean data only:

1. Drop the newest record by `published` date.
2. Blank the summary of one evaluation paper.
3. Truncate the title of one evaluation paper.
4. Move one publication date older than the 180-day freshness threshold.
5. Add one duplicate row with the same `paper_id`.

Write all changes to corrupted-specific paths and log record ID, corruption type, before/after value or count, and parameter. Never modify baseline files.

## Expected signals and repair

| Corruption | Expected quality/freshness signal | Expected RAG impact | Repair |
|---|---|---|---|
| Drop newest | `row_count` decreases | Queries for dropped paper miss | Reload raw and re-run cleaning |
| Blank summary | `summary_min_length` fails; embedding content degrades | Summary answers/token F1 may drop | Rebuild from raw summary |
| Truncated title | No null check necessarily fails; lineage/title evidence changes | Exact title lookup may miss | Rebuild from raw title |
| Stale date | `stale_rows` increases; freshness fails | Date answer becomes wrong | Rebuild from raw published date |
| Duplicate row | `paper_id_unique` fails | Retrieval may return duplicate evidence | Re-run cleaning deduplication from raw |

## Role handoff

- **Role 1:** freeze scope, paths and comparison rules; verify baseline is not overwritten.
- **Role 2:** preserve the two raw snapshots and their hashes as repair source.
- **Role 3:** apply/log corruption and repair by re-running cleaning from raw.
- **Role 4:** use `papers-corrupted` and `papers-repaired` collections; keep `papers-baseline` readable.
- **Role 5:** reuse the same 12-sample test set and metrics/evaluator settings.
- **Role 6:** run quality/freshness separately for corrupted and repaired data and link signals to the corruption log.

## CP4 pass criteria

- [x] Baseline metrics and artifacts are recorded.
- [x] Corruption types, target signals and expected RAG impact are defined.
- [x] Raw snapshot and hashes are available for repair.
- [x] Scope preserves baseline and freezes test/evaluator configuration.
- [x] Each role has a post-break handoff.

CP5 may now implement the controlled corruption flow.
