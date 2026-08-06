from __future__ import annotations

from dataclasses import asdict

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the baseline pipeline end-to-end.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    settings = load_settings()
    if settings.paths.raw_records_json.exists():
        records = load_raw_records(settings.paths.raw_records_json)
        source_mode = "loaded existing raw snapshot"
    else:
        records = fetch_source_records(settings)
        source_mode = "fetched and persisted new raw snapshot"

    clean = build_clean_dataframe(records, run_date=now_utc())
    write_csv(clean, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(clean, settings, settings.paths.embeddings_json)
    if settings.paths.eval_testset.exists():
        test_set = read_json(settings.paths.eval_testset)
    else:
        test_set = build_test_set(clean, settings.paths.eval_testset)
    evaluation = evaluate_pipeline(settings, index, settings.paths.eval_testset, settings.paths.baseline_metrics, settings.paths.baseline_answers)
    quality = run_data_quality_checks(clean, settings, "baseline_quality")
    freshness = build_freshness_report(clean, settings, settings.paths.freshness_report)
    generate_phase1_report(
        settings.paths.baseline_report,
        {"mode": source_mode, "raw_records": len(records), "clean_records": len(clean), "test_samples": len(test_set)},
        evaluation.summary,
        quality,
        freshness,
    )
    print(f"Phase 1 complete: {len(clean)} clean records, {len(test_set)} test samples, quality={quality['status']}, freshness={freshness['status']}")
