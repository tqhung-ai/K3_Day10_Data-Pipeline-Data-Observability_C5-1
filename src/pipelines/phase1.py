from __future__ import annotations

import json
from datetime import datetime

from core.config import load_settings, require_llm_credentials
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xay dung baseline pipeline end-to-end.

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
    require_llm_credentials(settings)

    run_date = now_utc()

    # 2. Load or fetch raw records
    if settings.paths.raw_records_json.exists():
        print("Loading raw records from snapshot...")
        records = load_raw_records(settings.paths.raw_records_json)
    else:
        print("Fetching raw records from Crossref API...")
        records = fetch_source_records(settings)

    print(f"Loaded {len(records)} raw records.")

    # 3. Clean data
    print("Cleaning data...")
    df = build_clean_dataframe(records, run_date)
    print(f"Cleaned data: {len(df)} records.")

    # 4. Save clean CSV/JSON
    write_csv(df, settings.paths.clean_csv)
    clean_records = df.to_dict(orient="records")
    write_json(settings.paths.clean_json, clean_records)
    print(f"Saved clean data to {settings.paths.clean_csv} and {settings.paths.clean_json}")

    # 5. Build Chroma index
    print("Building Chroma index...")
    index = LocalEmbeddingIndex.build(
        df=df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    print(f"Built index with collection: {index.collection_name}")

    # 6. Create or load evaluation set
    print("Building evaluation test set...")
    test_set = build_test_set(df, settings.paths.eval_testset)
    print(f"Created test set with {len(test_set)} questions.")

    # 7. Evaluate
    print("Evaluating pipeline...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(f"Evaluation complete. Metrics: {json.dumps(bundle.summary, indent=2)}")

    # 8. Run quality checks and freshness report
    print("Running data quality checks...")
    quality_report = run_data_quality_checks(df, settings, "baseline_quality")
    print(f"Quality checks: {quality_report['overall_passed']}")

    print("Building freshness report...")
    freshness_report = build_freshness_report(df, settings, settings.paths.freshness_report)
    print(f"Freshness: is_fresh={freshness_report['is_fresh']}")

    # 9. Generate markdown report
    print("Generating phase 1 report...")
    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "total_records": len(records),
        "total_clean_records": len(df),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality_report,
        freshness=freshness_report,
    )
    print(f"Report saved to {settings.paths.baseline_report}")

    # 10. Demo agent on sample questions
    print("\n--- Demo Agent ---")
    from retrieval.agent import build_agent, run_agent_question

    agent = build_agent(settings, index)
    sample_questions = [
        "What papers are about agentic retrieval augmented generation?",
        "Who are the authors of the most recent paper?",
    ]
    for question in sample_questions:
        answer = run_agent_question(agent, question)
        print(f"\nQ: {question}")
        print(f"A: {answer}")

    print("\n=== Phase 1 baseline pipeline completed successfully! ===")


if __name__ == "__main__":
    main()
