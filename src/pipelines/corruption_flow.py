from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run CP5 corruption and CP6 repair/comparison from the frozen raw snapshot."""
    settings = load_settings()
    paths = settings.paths
    required_paths = {
        "clean baseline": paths.clean_json,
        "baseline metrics": paths.baseline_metrics,
        "raw records": paths.raw_records_json,
        "corrupted metrics": paths.corrupted_metrics,
        "evaluation set": paths.eval_testset,
    }
    missing = [name for name, path in required_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing prerequisite artifacts: {', '.join(missing)}")

    baseline_df = pd.DataFrame(read_json(paths.clean_json))
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.corrupted_metrics,
        answers_output_path=paths.corrupted_answers,
    )
    quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.quality_dir / "freshness_corrupted.json",
    )
    # Repair from raw, never from the corrupted dataframe. Cleaning restores
    # required fields and removes duplicate paper IDs deterministically.
    raw_records = load_raw_records(paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, datetime.now(UTC))
    if repaired_df.empty:
        raise RuntimeError("Repair cleaning produced no usable records.")
    write_csv(repaired_df, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired_df.to_dict(orient="records"))

    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.repaired_metrics,
        answers_output_path=paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.quality_dir / "freshness_repaired.json",
    )
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics=read_json(paths.baseline_metrics),
        corrupted_metrics=read_json(paths.corrupted_metrics),
        repaired_metrics=repaired_evaluation.summary,
        corrupted_quality=quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=freshness,
        repaired_freshness=repaired_freshness,
    )

    print(f"CP6 complete: baseline={len(baseline_df)} corrupted={len(corrupted_df)} repaired={len(repaired_df)}")
    print(f"Corrupted collection: {corrupted_index.collection_name} | docs={len(corrupted_index.documents)}")
    print(f"Repaired collection: {repaired_index.collection_name} | docs={len(repaired_index.documents)}")
    print(f"Corrupted token F1: {corrupted_evaluation.summary['mean_token_f1']:.4f}")
    print(f"Repaired token F1: {repaired_evaluation.summary['mean_token_f1']:.4f}")
    print(f"Repaired quality: {repaired_quality['success']} | Freshness: {repaired_freshness['is_fresh']}")
