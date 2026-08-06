from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.corruption import corrupt_clean_dataframe
from observability.quality import build_freshness_report, run_data_quality_checks
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run the controlled corruption and impact-measurement stage for CP5."""
    settings = load_settings()
    paths = settings.paths
    if not paths.clean_json.exists() or not paths.baseline_metrics.exists():
        raise FileNotFoundError("Run the baseline pipeline before the corruption flow.")
    if not paths.eval_testset.exists():
        raise FileNotFoundError("Baseline evaluation set is required before corruption.")

    baseline_df = pd.DataFrame(read_json(paths.clean_json))
    corrupted_df = corrupt_clean_dataframe(baseline_df, paths.corruption_log)
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        paths.corrupted_embeddings_json,
    )
    evaluation = evaluate_pipeline(
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
    print(f"Corruption complete: baseline={len(baseline_df)} corrupted={len(corrupted_df)}")
    print(f"Collection: {corrupted_index.collection_name} | docs={len(corrupted_index.documents)}")
    print(f"Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.4f}")
    print(f"Quality success: {quality['success']} | Freshness: {freshness['is_fresh']}")
