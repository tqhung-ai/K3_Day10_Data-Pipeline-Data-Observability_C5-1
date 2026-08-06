from __future__ import annotations

from datetime import UTC, datetime

from core.config import load_settings
from core.utils import read_json, write_json, write_csv
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the clean-data baseline flow and persist auditable artifacts."""
    settings = load_settings()
    paths = settings.paths

    if paths.raw_records_json.exists() and not settings.refresh_source:
        records = load_raw_records(paths.raw_records_json)
    else:
        records = fetch_source_records(settings)

    clean_df = build_clean_dataframe(records, datetime.now(UTC))
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no usable records; baseline cannot continue.")
    write_csv(clean_df, paths.clean_csv)
    clean_json = clean_df.to_dict(orient="records")
    write_json(paths.clean_json, clean_json)

    index = LocalEmbeddingIndex.build(clean_df, settings, paths.embeddings_json)

    if paths.eval_testset.exists() and not settings.refresh_test_set:
        test_set = read_json(paths.eval_testset)
        if not test_set:
            raise RuntimeError("Existing evaluation set is empty; set REFRESH_TEST_SET=true to rebuild it.")
    else:
        test_set = build_test_set(clean_df, paths.eval_testset)
    if not test_set:
        raise RuntimeError("Evaluation set is empty; baseline cannot continue.")

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "cleaning_stats": clean_df.attrs.get("cleaning_stats", {}),
        "embedding_model": settings.embedding_model,
        "collection_name": index.collection_name,
    }
    generate_phase1_report(
        paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    print(f"Baseline complete: raw={len(records)} clean={len(clean_df)} eval={len(test_set)}")
    print(f"Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"Quality success: {quality['success']} | Freshness: {freshness['is_fresh']}")
