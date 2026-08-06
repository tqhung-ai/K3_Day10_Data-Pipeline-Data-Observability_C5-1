from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from evaluation.metrics import evaluate_pipeline
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex
import pandas as pd


def main() -> None:
    """Run corruption, evaluation, repair and comparison end-to-end.

    Pseudo-code:
    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    settings = load_settings()
    if not settings.paths.baseline_metrics.exists() or not settings.paths.eval_testset.exists():
        raise FileNotFoundError("Baseline artifacts are required before running corruption flow.")
    clean = pd.read_csv(settings.paths.clean_csv)
    corrupted = corrupt_clean_dataframe(clean, settings.paths.corruption_log)
    test_set = read_json(settings.paths.eval_testset)
    corruption_log = read_json(settings.paths.corruption_log)
    for entry in corruption_log:
        affected = [item["id"] for item in test_set if entry["paper_id"] in item.get("ground_truth_doc_ids", [])]
        entry["overlap_with_test_set"] = bool(affected)
        entry["affected_question_ids"] = affected
    write_json(settings.paths.corruption_log, corruption_log)
    write_csv(corrupted, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(corrupted, settings, settings.paths.corrupted_embeddings_json)
    corrupted_eval = evaluate_pipeline(settings, corrupted_index, settings.paths.eval_testset, settings.paths.corrupted_metrics, settings.paths.corrupted_answers)
    corrupted_quality = run_data_quality_checks(corrupted, settings, "corrupted_quality")
    corrupted_freshness = build_freshness_report(corrupted, settings, settings.paths.quality_dir / "freshness_corrupted.json")

    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired = build_clean_dataframe(raw_records, run_date=now_utc())
    write_csv(repaired, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(repaired, settings, settings.paths.repaired_embeddings_json)
    repaired_eval = evaluate_pipeline(settings, repaired_index, settings.paths.eval_testset, settings.paths.repaired_metrics, settings.paths.repaired_answers)
    repaired_quality = run_data_quality_checks(repaired, settings, "repaired_quality")
    repaired_freshness = build_freshness_report(repaired, settings, settings.paths.quality_dir / "freshness_repaired.json")

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    generate_corruption_report(settings.paths.comparison_report, baseline_metrics, corrupted_eval.summary, repaired_eval.summary, corrupted_quality, repaired_quality, corrupted_freshness, repaired_freshness)
    print(f"Corruption flow complete: corrupted={corrupted_quality['status']}, repaired={repaired_quality['status']}")
