# Phase 1 - Baseline Pipeline Report

## 1. Source Summary

- **Source API**: Crossref REST API
- **Query**: agentic retrieval augmented generation large language model
- **Filter**: from-pub-date:2026-02-07,has-abstract:true
- **Max Results**: 24
- **Total Records Fetched**: 24
- **Total Records After Cleaning**: 24

## 2. Evaluation Metrics

- **Samples**: 36
- **Retrieval Hit Rate**: 1.0000
- **Mean Token F1**: 0.5495
- **Judge Accuracy**: 0.6111
- **Mean Judge Score**: 2.8889
- **Ragas**: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## 3. Data Quality

- **Report Name**: baseline_quality
- **Total Rows**: 24
- **Overall Passed**: True

### Individual Checks

| Check | Passed | Value | Threshold |
|-------|--------|-------|-----------|
| row_count | True | 24 | > 0 |
| paper_id_not_null | True | 0 | 0 |
| paper_id_unique | True | 0 | 0 |
| title_not_null | True | 0 | 0 |
| summary_not_empty | True | 0 | 0 |
| summary_min_length | True | 0 | 0 (min 50 chars) |
| freshness | True | 0 | <= 180 days |

## 4. Freshness Report

- **Latest Published**: 2026-08-01
- **Oldest Published**: 2026-02-12
- **Stale Rows**: 0
- **Total Rows**: 24
- **Freshness Threshold (days)**: 180
- **Is Fresh**: True

## 5. Summary

Baseline pipeline completed successfully. The RAG agent was evaluated on a clean dataset.
Data quality and freshness checks confirm the integrity of the baseline data.
