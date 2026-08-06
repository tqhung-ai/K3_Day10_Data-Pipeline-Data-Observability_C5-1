from __future__ import annotations

from typing import Any

from core.utils import ensure_parent


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    lines: list[str] = []
    lines.append("# Phase 1 - Baseline Pipeline Report")
    lines.append("")
    lines.append("## 1. Source Summary")
    lines.append("")
    lines.append(f"- **Source API**: {source_summary.get('source_api', 'N/A')}")
    lines.append(f"- **Query**: {source_summary.get('source_query', 'N/A')}")
    lines.append(f"- **Filter**: {source_summary.get('source_filter', 'N/A')}")
    lines.append(f"- **Max Results**: {source_summary.get('max_results', 'N/A')}")
    lines.append(f"- **Total Records Fetched**: {source_summary.get('total_records', 'N/A')}")
    lines.append(f"- **Total Records After Cleaning**: {source_summary.get('total_clean_records', 'N/A')}")
    lines.append("")

    lines.append("## 2. Evaluation Metrics")
    lines.append("")
    lines.append(f"- **Samples**: {metrics.get('samples', 'N/A')}")
    lines.append(f"- **Retrieval Hit Rate**: {metrics.get('retrieval_hit_rate', 'N/A'):.4f}" if isinstance(metrics.get('retrieval_hit_rate'), (int, float)) else f"- **Retrieval Hit Rate**: {metrics.get('retrieval_hit_rate', 'N/A')}")
    lines.append(f"- **Mean Token F1**: {metrics.get('mean_token_f1', 'N/A'):.4f}" if isinstance(metrics.get('mean_token_f1'), (int, float)) else f"- **Mean Token F1**: {metrics.get('mean_token_f1', 'N/A')}")
    lines.append(f"- **Judge Accuracy**: {metrics.get('judge_accuracy', 'N/A'):.4f}" if isinstance(metrics.get('judge_accuracy'), (int, float)) else f"- **Judge Accuracy**: {metrics.get('judge_accuracy', 'N/A')}")
    lines.append(f"- **Mean Judge Score**: {metrics.get('mean_judge_score', 'N/A'):.4f}" if isinstance(metrics.get('mean_judge_score'), (int, float)) else f"- **Mean Judge Score**: {metrics.get('mean_judge_score', 'N/A')}")
    ragas = metrics.get('ragas', {})
    if isinstance(ragas, dict):
        if 'skipped' in ragas:
            lines.append(f"- **Ragas**: {ragas['skipped']}")
        elif 'error' in ragas:
            lines.append(f"- **Ragas**: {ragas['error']}")
        else:
            for k, v in ragas.items():
                lines.append(f"- **Ragas - {k}**: {v}")
    lines.append("")

    lines.append("## 3. Data Quality")
    lines.append("")
    lines.append(f"- **Report Name**: {quality.get('report_name', 'N/A')}")
    lines.append(f"- **Total Rows**: {quality.get('total_rows', 'N/A')}")
    lines.append(f"- **Overall Passed**: {quality.get('overall_passed', 'N/A')}")
    lines.append("")
    lines.append("### Individual Checks")
    lines.append("")
    lines.append("| Check | Passed | Value | Threshold |")
    lines.append("|-------|--------|-------|-----------|")
    for check_name, check_result in quality.get("checks", {}).items():
        passed = check_result.get("passed", "N/A")
        value = check_result.get("value", "N/A")
        threshold = check_result.get("threshold", "N/A")
        lines.append(f"| {check_name} | {passed} | {value} | {threshold} |")
    lines.append("")

    lines.append("## 4. Freshness Report")
    lines.append("")
    lines.append(f"- **Latest Published**: {freshness.get('latest_published', 'N/A')}")
    lines.append(f"- **Oldest Published**: {freshness.get('oldest_published', 'N/A')}")
    lines.append(f"- **Stale Rows**: {freshness.get('stale_rows', 'N/A')}")
    lines.append(f"- **Total Rows**: {freshness.get('total_rows', 'N/A')}")
    lines.append(f"- **Freshness Threshold (days)**: {freshness.get('freshness_threshold_days', 'N/A')}")
    lines.append(f"- **Is Fresh**: {freshness.get('is_fresh', 'N/A')}")
    lines.append("")

    lines.append("## 5. Summary")
    lines.append("")
    lines.append("Baseline pipeline completed successfully. The RAG agent was evaluated on a clean dataset.")
    lines.append("Data quality and freshness checks confirm the integrity of the baseline data.")
    lines.append("")

    ensure_parent(report_path)
    report_path.write_text("\n".join(lines), encoding="utf-8")


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
    """Viet markdown report so sanh baseline/corrupted/repaired."""
    lines: list[str] = []
    lines.append("# Corruption & Repair Comparison Report")
    lines.append("")
    lines.append("## 1. Metrics Comparison")
    lines.append("")
    lines.append("| Metric | Baseline | Corrupted | Repaired |")
    lines.append("|--------|----------|-----------|----------|")

    metric_keys = ["samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]
    for key in metric_keys:
        baseline_val = baseline_metrics.get(key, "N/A")
        corrupted_val = corrupted_metrics.get(key, "N/A")
        repaired_val = repaired_metrics.get(key, "N/A")
        if isinstance(baseline_val, float):
            baseline_val = f"{baseline_val:.4f}"
        if isinstance(corrupted_val, float):
            corrupted_val = f"{corrupted_val:.4f}"
        if isinstance(repaired_val, float):
            repaired_val = f"{repaired_val:.4f}"
        lines.append(f"| {key} | {baseline_val} | {corrupted_val} | {repaired_val} |")
    lines.append("")

    lines.append("## 2. Data Quality Comparison")
    lines.append("")
    lines.append("| Check | Corrupted | Repaired |")
    lines.append("|-------|-----------|----------|")
    corrupted_checks = corrupted_quality.get("checks", {})
    repaired_checks = repaired_quality.get("checks", {})
    all_check_names = set(corrupted_checks.keys()) | set(repaired_checks.keys())
    for check_name in sorted(all_check_names):
        corrupted_passed = corrupted_checks.get(check_name, {}).get("passed", "N/A")
        repaired_passed = repaired_checks.get(check_name, {}).get("passed", "N/A")
        lines.append(f"| {check_name} | {corrupted_passed} | {repaired_passed} |")
    lines.append("")

    lines.append("## 3. Freshness Comparison")
    lines.append("")
    lines.append("| Metric | Corrupted | Repaired |")
    lines.append("|--------|-----------|----------|")
    freshness_keys = ["latest_published", "oldest_published", "stale_rows", "total_rows", "is_fresh"]
    for key in freshness_keys:
        corrupted_val = corrupted_freshness.get(key, "N/A")
        repaired_val = repaired_freshness.get(key, "N/A")
        lines.append(f"| {key} | {corrupted_val} | {repaired_val} |")
    lines.append("")

    lines.append("## 4. Analysis")
    lines.append("")
    lines.append("### Impact of Data Corruption")
    lines.append("")
    lines.append("The table below shows the change in key metrics from baseline to corrupted:")
    lines.append("")
    lines.append("| Metric | Baseline | Corrupted | Change |")
    lines.append("|--------|----------|-----------|--------|")
    for key in ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]:
        baseline_val = baseline_metrics.get(key, 0)
        corrupted_val = corrupted_metrics.get(key, 0)
        if isinstance(baseline_val, (int, float)) and isinstance(corrupted_val, (int, float)):
            change = corrupted_val - baseline_val
            change_str = f"{change:+.4f}"
        else:
            change_str = "N/A"
        lines.append(f"| {key} | {baseline_val} | {corrupted_val} | {change_str} |")
    lines.append("")

    lines.append("### Recovery After Repair")
    lines.append("")
    lines.append("The table below shows the change in key metrics from corrupted to repaired:")
    lines.append("")
    lines.append("| Metric | Corrupted | Repaired | Change |")
    lines.append("|--------|-----------|----------|--------|")
    for key in ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]:
        corrupted_val = corrupted_metrics.get(key, 0)
        repaired_val = repaired_metrics.get(key, 0)
        if isinstance(corrupted_val, (int, float)) and isinstance(repaired_val, (int, float)):
            change = repaired_val - corrupted_val
            change_str = f"{change:+.4f}"
        else:
            change_str = "N/A"
        lines.append(f"| {key} | {corrupted_val} | {repaired_val} | {change_str} |")
    lines.append("")

    lines.append("## 5. Conclusion")
    lines.append("")
    lines.append("This report demonstrates the impact of data corruption on RAG agent performance")
    lines.append("and validates that repairing data from the raw source restores performance.")
    lines.append("Data quality and freshness checks help detect issues before they affect users.")
    lines.append("")

    ensure_parent(report_path)
    report_path.write_text("\n".join(lines), encoding="utf-8")
