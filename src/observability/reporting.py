from __future__ import annotations

from typing import Any

from core.utils import write_text


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "PASS" if value else "FAIL"
    if value is None:
        return "-"
    return str(value)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a Markdown baseline report whose values come from real artifacts."""
    checks = quality.get("checks", [])
    check_lines = [
        f"| `{check.get('name', '-')}` | {_value(check.get('passed'))} | {check.get('observed', '-')} | {check.get('expected', '-')} |"
        for check in checks
    ]
    ragas = metrics.get("ragas", {})
    ragas_status = ragas.get("skipped") if isinstance(ragas, dict) else ragas
    markdown = f"""# Phase 1 Baseline Report

## Source and dataset

| Field | Value |
|---|---|
| Source | {source_summary.get('source_api', '-')} |
| Query | {source_summary.get('query', '-')} |
| Filter | {source_summary.get('filter', '-')} |
| Raw records | {source_summary.get('raw_records', 0)} |
| Clean records | {source_summary.get('clean_records', 0)} |
| Embedding model | `{source_summary.get('embedding_model', '-')}` |
| Collection | `{source_summary.get('collection_name', '-')}` |

## Evaluation metrics

| Metric | Value |
|---|---:|
| Samples | {metrics.get('samples', 0)} |
| Retrieval hit rate | {metrics.get('retrieval_hit_rate', 0):.4f} |
| Mean token F1 | {metrics.get('mean_token_f1', 0):.4f} |
| Judge accuracy | {metrics.get('judge_accuracy', 0):.4f} |
| Mean judge score | {metrics.get('mean_judge_score', 0):.4f} |

Ragas: {_value(ragas_status) if ragas_status else 'available'}

## Data quality

Overall quality: **{_value(quality.get('success'))}**

| Check | Status | Observed | Expected |
|---|---|---:|---|
{chr(10).join(check_lines)}

## Freshness

| Field | Value |
|---|---|
| Latest published | {freshness.get('latest_published', '-')} |
| Oldest published | {freshness.get('oldest_published', '-')} |
| Total rows | {freshness.get('total_rows', 0)} |
| Stale rows | {freshness.get('stale_rows', 0)} |
| Threshold (days) | {freshness.get('threshold_days', '-')} |
| Freshness status | **{_value(freshness.get('is_fresh'))}** |

## Cleaning statistics

```json
{source_summary.get('cleaning_stats', {})}
```

This report is generated from the baseline JSON/CSV artifacts and should be regenerated whenever the baseline snapshot changes.
"""
    write_text(report_path, markdown)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a comparison report for the later corruption flow."""
    rows = []
    for name, metrics in (("Baseline", baseline_metrics), ("Corrupted", corrupted_metrics), ("Repaired", repaired_metrics)):
        rows.append(
            f"| {name} | {metrics.get('retrieval_hit_rate', 0):.4f} | {metrics.get('mean_token_f1', 0):.4f} | {metrics.get('judge_accuracy', 0):.4f} | {metrics.get('mean_judge_score', 0):.4f} |"
        )
    markdown = f"""# Corruption Comparison Report

| State | Retrieval hit rate | Mean token F1 | Judge accuracy | Mean judge score |
|---|---:|---:|---:|---:|
{chr(10).join(rows)}

## Data quality and freshness

- Corrupted quality: **{_value(corrupted_quality.get('success'))}**
- Repaired quality: **{_value(repaired_quality.get('success'))}**
- Corrupted freshness: **{_value(corrupted_freshness.get('is_fresh'))}**
- Repaired freshness: **{_value(repaired_freshness.get('is_fresh'))}**
"""
    write_text(report_path, markdown)
