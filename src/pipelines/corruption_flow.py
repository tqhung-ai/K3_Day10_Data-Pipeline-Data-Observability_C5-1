from __future__ import annotations

import json

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung corruption -> evaluate -> repair -> compare flow.

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
    require_llm_credentials(settings)

    run_date = now_utc()

    # 1. Load baseline metrics and clean dataset
    print("Loading baseline metrics and clean dataset...")
    baseline_metrics = json.loads(settings.paths.baseline_metrics.read_text(encoding="utf-8"))
    clean_df = json.loads(settings.paths.clean_json.read_text(encoding="utf-8"))
    import pandas as pd
    clean_df = pd.DataFrame(clean_df)
    print(f"Loaded {len(clean_df)} clean records and baseline metrics.")

    # 2. Create corrupted dataframe
    print("Creating corrupted dataset...")
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    print(f"Corrupted dataset: {len(corrupted_df)} records.")

    # 3. Save corrupted artifacts
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    print(f"Saved corrupted data to {settings.paths.corrupted_clean_csv}")

    # 4. Rebuild index and evaluate on corrupted data
    print("Building Chroma index for corrupted data...")
    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    print("Evaluating corrupted pipeline...")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(f"Corrupted metrics: {json.dumps(corrupted_bundle.summary, indent=2)}")

    # 5. Run quality checks and freshness on corrupted data
    print("Running quality checks on corrupted data...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted_quality")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness.json")
    print(f"Corrupted quality passed: {corrupted_quality['overall_passed']}")

    # 6. Repair from raw records
    print("Repairing data from raw source...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date)
    print(f"Repaired dataset: {len(repaired_df)} records.")

    # Save repaired artifacts
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    print(f"Saved repaired data to {settings.paths.repaired_clean_csv}")

    # 7. Evaluate repaired dataset
    print("Building Chroma index for repaired data...")
    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    print("Evaluating repaired pipeline...")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(f"Repaired metrics: {json.dumps(repaired_bundle.summary, indent=2)}")

    # Run quality checks and freshness on repaired data
    print("Running quality checks on repaired data...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired_quality")
    repaired_freshness = build_freshness_report(repaired_df, settings, settings.paths.quality_dir / "repaired_freshness.json")
    print(f"Repaired quality passed: {repaired_quality['overall_passed']}")

    # 8. Generate comparison report
    print("Generating corruption comparison report...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"Comparison report saved to {settings.paths.comparison_report}")

    print("\n=== Corruption flow completed successfully! ===")


if __name__ == "__main__":
    main()
