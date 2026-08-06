# Corruption & Repair Comparison Report

## 1. Metrics Comparison

| Metric | Baseline | Corrupted | Repaired |
|--------|----------|-----------|----------|
| samples | 36 | 36 | 36 |
| retrieval_hit_rate | 1.0000 | 0.6667 | 1.0000 |
| mean_token_f1 | 0.5495 | 0.2742 | 0.5495 |
| judge_accuracy | 0.6111 | 0.2778 | 0.6111 |
| mean_judge_score | 2.8889 | 1.8889 | 2.8889 |

## 2. Data Quality Comparison

| Check | Corrupted | Repaired |
|-------|-----------|----------|
| freshness | True | True |
| paper_id_not_null | True | True |
| paper_id_unique | False | True |
| row_count | True | True |
| summary_min_length | False | True |
| summary_not_empty | False | True |
| title_not_null | True | True |

## 3. Freshness Comparison

| Metric | Corrupted | Repaired |
|--------|-----------|----------|
| latest_published | 2026-07-01 | 2026-08-01 |
| oldest_published | 2000-01-01 | 2026-02-12 |
| stale_rows | 0 | 0 |
| total_rows | 22 | 24 |
| is_fresh | True | True |

## 4. Analysis

### Impact of Data Corruption

The table below shows the change in key metrics from baseline to corrupted:

| Metric | Baseline | Corrupted | Change |
|--------|----------|-----------|--------|
| retrieval_hit_rate | 1.0 | 0.6666666666666666 | -0.3333 |
| mean_token_f1 | 0.5495494650434656 | 0.27422756844016266 | -0.2753 |
| judge_accuracy | 0.6111111111111112 | 0.2777777777777778 | -0.3333 |
| mean_judge_score | 2.888888888888889 | 1.8888888888888888 | -1.0000 |

### Recovery After Repair

The table below shows the change in key metrics from corrupted to repaired:

| Metric | Corrupted | Repaired | Change |
|--------|-----------|----------|--------|
| retrieval_hit_rate | 0.6666666666666666 | 1.0 | +0.3333 |
| mean_token_f1 | 0.27422756844016266 | 0.5495494650434656 | +0.2753 |
| judge_accuracy | 0.2777777777777778 | 0.6111111111111112 | +0.3333 |
| mean_judge_score | 1.8888888888888888 | 2.888888888888889 | +1.0000 |

## 5. Conclusion

This report demonstrates the impact of data corruption on RAG agent performance
and validates that repairing data from the raw source restores performance.
Data quality and freshness checks help detect issues before they affect users.
