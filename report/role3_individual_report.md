# Individual Report — Role 3: Cleaning, Corruption & Repair

## Scope

Role 3 owns clean data modeling, deterministic corruption and repair integration.
The member name/MSSV must be added before submission.

## Work and evidence

- `src/ingestion/cleaning.py` normalizes fields, rejects unusable records and
  deduplicates by `paper_id`.
- `src/ingestion/corruption.py` creates six logged corruption operations without
  modifying baseline data.
- `src/pipelines/corruption_flow.py` reloads raw records and runs cleaning again
  to create repaired data.
- Evidence: `papers_clean_repaired.json` has 24 rows and 24 unique IDs;
  `data/results/corruption_log.json` records before/after values and parameters.

## Technical understanding

Repair must use raw because corrupted values cannot be trusted. Re-running the
cleaner restores summary/title/date and deduplicates rows, then the repaired data
is re-indexed and evaluated independently.

## Result

Corrupted data has 23 unique IDs and fails quality/freshness. Repaired data has
24 unique IDs, passes both gates and restores token-F1 from `0.7324` to `0.7518`.
