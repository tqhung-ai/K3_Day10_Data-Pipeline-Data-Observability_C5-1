# Phase 1 Baseline Report

## Source and dataset

| Field | Value |
|---|---|
| Source | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-02-07,has-abstract:true |
| Raw records | 24 |
| Clean records | 24 |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Collection | `papers-baseline` |

## Evaluation metrics

| Metric | Value |
|---|---:|
| Samples | 12 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 0.7518 |
| Judge accuracy | 0.6667 |
| Mean judge score | 3.7500 |

Ragas: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## Data quality

Overall quality: **PASS**

| Check | Status | Observed | Expected |
|---|---|---:|---|
| `row_count` | PASS | 24 | > 0 |
| `paper_id_not_null` | PASS | 0 | 0 |
| `paper_id_unique` | PASS | 0 | 0 |
| `title_not_null` | PASS | 0 | 0 |
| `summary_min_length` | PASS | 0 | 0 rows shorter than 20 characters |
| `text_for_embedding_not_empty` | PASS | 0 | 0 |
| `age_days_valid` | PASS | 0 | 0 |
| `freshness_threshold` | PASS | 0 | 0 rows older than 180 days |

## Freshness

| Field | Value |
|---|---|
| Latest published | 2026-08-01 |
| Oldest published | 2026-02-12 |
| Total rows | 24 |
| Stale rows | 0 |
| Threshold (days) | 180 |
| Freshness status | **PASS** |

## Cleaning statistics

```json
{'input_rows': 24, 'output_rows': 24, 'duplicates_removed': 0, 'missing_paper_id': 0, 'missing_title': 0, 'missing_summary': 0, 'invalid_published': 0}
```

This report is generated from the baseline JSON/CSV artifacts and should be regenerated whenever the baseline snapshot changes.
