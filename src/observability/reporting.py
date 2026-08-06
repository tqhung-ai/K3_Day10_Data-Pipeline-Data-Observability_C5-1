from __future__ import annotations

from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline phase Markdown report.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    text = "\n".join([
        "# Phase 1 Baseline Report", "", "## Source", f"- {source_summary}", "",
        "## Metrics", *[f"- **{key}**: {value}" for key, value in metrics.items()], "",
        "## Data quality", *[f"- **{key}**: {value}" for key, value in quality.items()], "",
        "## Freshness", *[f"- **{key}**: {value}" for key, value in freshness.items()], "",
    ])
    write_text(report_path, text)


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
    """Write the baseline/corrupted/repaired comparison report."""
    metric_keys = sorted(set(baseline_metrics) | set(corrupted_metrics) | set(repaired_metrics))
    rows = ["| Metric | Baseline | Corrupted | Repaired | Corrupted-Baseline | Repaired-Corrupted | Repaired-Baseline |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key in metric_keys:
        if not isinstance(baseline_metrics.get(key), (int, float)):
            continue
        base = float(baseline_metrics.get(key, 0)); bad = float(corrupted_metrics.get(key, 0)); fixed = float(repaired_metrics.get(key, 0))
        rows.append(f"| {key} | {base:.4f} | {bad:.4f} | {fixed:.4f} | {bad-base:.4f} | {fixed-bad:.4f} | {fixed-base:.4f} |")
    text = "\n".join([
        "# Corruption and Repair Comparison", "", "## Metrics", *rows, "",
        "## Quality and freshness", "", f"- Corrupted quality: **{corrupted_quality.get('status')}**", f"- Repaired quality: **{repaired_quality.get('status')}**", f"- Corrupted freshness: **{corrupted_freshness.get('status')}**", f"- Repaired freshness: **{repaired_freshness.get('status')}**", "",
        "## Observability details", f"- Corrupted duplicate paper IDs: {corrupted_quality.get('duplicate_paper_id')}", f"- Corrupted stale rows: {corrupted_freshness.get('stale_count')}", f"- Repaired duplicate paper IDs: {repaired_quality.get('duplicate_paper_id')}", f"- Repaired stale rows: {repaired_freshness.get('stale_count')}", "",
    ])
    write_text(report_path, text)
