# Individual Report — Role 6: Observability & Reporting

## Scope

| Thành viên | MSSV |
|---|---|
| Nguyễn Thế Anh | 2A202601791 |

Role 6 owns quality gates, freshness monitoring and comparison evidence.

## Work and evidence

- `run_data_quality_checks()` validates row count, ID completeness/uniqueness,
  title, summary length, embedding text and age validity.
- `build_freshness_report()` uses the shared 180-day threshold.
- Reports exist for baseline, corrupted and repaired states in `data/quality/`.
- Comparison is published at `data/reports/corruption_report.md`.

## Results

| State | Quality | Freshness | Key signal |
|---|---|---|---|
| Baseline | PASS | PASS | 24 valid unique IDs |
| Corrupted | FAIL | FAIL | duplicate ID, short summary, one stale row |
| Repaired | PASS | PASS | 24 valid unique IDs, no stale row |

The checks are computed from each dataframe and persisted as JSON; statuses are
not hard-coded in the report.
