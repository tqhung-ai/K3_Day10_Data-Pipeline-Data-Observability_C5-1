from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings, normalized_provider
from core.utils import now_utc, write_csv, write_json
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def _llm_is_configured(settings: Settings) -> bool:
    provider = normalized_provider(settings)
    return {
        "gemini": bool(settings.google_api_key),
        "openai": bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "ollama": True,
        "custom": bool(settings.custom_llm_base_url),
    }.get(provider, False)


def _load_or_build_baseline_index(
    clean_df: pd.DataFrame,
    settings: Settings,
) -> tuple[LocalEmbeddingIndex, bool]:
    expected_documents = LocalEmbeddingIndex._build_documents(clean_df)
    force_rebuild = os.getenv("REBUILD_BASELINE_INDEX", "").lower() in {"1", "true", "yes"}
    if settings.paths.embeddings_json.exists() and not force_rebuild:
        try:
            existing = LocalEmbeddingIndex.load(settings, settings.paths.embeddings_json)
            if (
                existing.documents == expected_documents
                and existing.collection.count() == len(expected_documents)
            ):
                return existing, False
        except Exception:
            pass

    return (
        LocalEmbeddingIndex.build(
            clean_df,
            settings,
            embeddings_output_path=settings.paths.embeddings_json,
        ),
        True,
    )


def _run_optional_llm_agent(
    settings: Settings,
    index: LocalEmbeddingIndex,
    question: str,
) -> dict[str, Any]:
    if not _llm_is_configured(settings):
        return {
            "status": "blocked",
            "reason": (
                "No credentials or local endpoint configured for "
                f"{normalized_provider(settings)}."
            ),
        }
    if os.getenv("RUN_LLM_AGENT", "").lower() not in {"1", "true", "yes"}:
        return {
            "status": "skipped",
            "reason": "Set RUN_LLM_AGENT=1 to run the configured provider smoke test.",
        }

    try:
        agent = build_agent(settings, index)
        return {
            "status": "passed",
            "question": question,
            "answer": run_agent_question(agent, question),
        }
    except Exception as exc:
        return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}


def main() -> None:
    """Build and verify all artifacts required at checkpoint 2 without refetching Crossref."""
    settings = load_settings()
    if not settings.paths.raw_api_response.exists() or not settings.paths.raw_records_json.exists():
        raise FileNotFoundError(
            "CP2 requires the locked CP0 raw response and raw records snapshot."
        )

    records = load_raw_records(settings.paths.raw_records_json)
    clean_df = build_clean_dataframe(records, run_date=now_utc())
    if clean_df.empty:
        raise ValueError("Cleaning produced no records; do not build an empty baseline index.")

    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, _dataframe_records(clean_df))

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = json.loads(settings.paths.eval_testset.read_text(encoding="utf-8"))
    if not isinstance(test_set, list) or not test_set:
        raise ValueError("The locked evaluation test set must be a non-empty JSON list.")
    clean_ids = set(clean_df["paper_id"])
    missing_ground_ids = {
        paper_id
        for item in test_set
        for paper_id in item.get("ground_truth_doc_ids", [])
        if paper_id not in clean_ids
    }
    if missing_ground_ids:
        raise ValueError(
            f"Test-set ground-truth IDs are missing from clean data: {sorted(missing_ground_ids)}"
        )

    index, index_rebuilt = _load_or_build_baseline_index(clean_df, settings)

    sample = test_set[0]
    sample_paper_id = sample["ground_truth_doc_ids"][0]
    raw_sample = next(record for record in records if record.paper_id == sample_paper_id)
    clean_sample = clean_df.loc[clean_df["paper_id"].eq(sample_paper_id)].iloc[0]
    exact_document = index.lookup(sample_paper_id)
    if exact_document is None:
        raise AssertionError(f"paper_id missing from exact index lookup: {sample_paper_id}")
    exact_title_document = index.lookup(str(clean_sample["title"]))
    if exact_title_document is None:
        raise AssertionError(f"title missing from exact index lookup: {clean_sample['title']}")

    semantic_results = index.search(sample["question"], top_k=settings.top_k)
    if not semantic_results:
        raise AssertionError("Semantic search returned no source documents.")
    if sample_paper_id not in {result.paper_id for result in semantic_results}:
        raise AssertionError("Semantic search did not retrieve the expected source document.")

    qa_demo_answers = []
    for item in test_set:
        result = answer_question(item["question"], settings=settings, index=index)
        qa_demo_answers.append(
            {
                "id": item["id"],
                "question_type": item["question_type"],
                "question": item["question"],
                "answer": result.answer,
                "ground_truth_doc_ids": item["ground_truth_doc_ids"],
                "retrieved_doc_ids": result.retrieved_doc_ids,
                "retrieved_titles": result.retrieved_titles,
                "source_hit": any(
                    paper_id in item["ground_truth_doc_ids"]
                    for paper_id in result.retrieved_doc_ids
                ),
            }
        )
    write_json(settings.paths.demo_answers, qa_demo_answers)

    qa_result = answer_question(sample["question"], settings=settings, index=index)
    if sample_paper_id not in qa_result.retrieved_doc_ids:
        raise AssertionError("QA smoke test did not retrieve its ground-truth source document.")

    indexed_metadata = exact_document["metadata"]
    if not (
        raw_sample.paper_id
        == clean_sample["paper_id"]
        == exact_document["paper_id"]
        == indexed_metadata["paper_id"]
    ):
        raise AssertionError("paper_id changed between raw, clean, document, and index metadata.")

    evidence_path = settings.paths.project_dir / "data" / "results" / "checkpoint2_evidence.json"
    evidence = {
        "generated_at": now_utc().isoformat(),
        "source_refresh_performed": False,
        "raw_snapshot": {
            "response_path": str(settings.paths.raw_api_response),
            "records_path": str(settings.paths.raw_records_json),
            "response_sha256": _file_sha256(settings.paths.raw_api_response),
            "records_sha256": _file_sha256(settings.paths.raw_records_json),
            "record_count": len(records),
        },
        "clean": {
            "csv_path": str(settings.paths.clean_csv),
            "json_path": str(settings.paths.clean_json),
            "record_count": len(clean_df),
            "paper_id_unique": bool(clean_df["paper_id"].is_unique),
            "empty_text_for_embedding": int(clean_df["text_for_embedding"].eq("").sum()),
            "stats": clean_df.attrs.get("cleaning_stats", {}),
        },
        "test_set": {
            "path": str(settings.paths.eval_testset),
            "count": len(test_set),
            "question_types": sorted({item["question_type"] for item in test_set}),
        },
        "index": {
            "manifest_path": str(settings.paths.embeddings_json),
            "collection_name": index.collection_name,
            "document_count": len(index.documents),
            "embedding_model": settings.embedding_model,
            "rebuilt_this_run": index_rebuilt,
        },
        "lineage_sample": {
            "paper_id": sample_paper_id,
            "raw": {
                "paper_id": raw_sample.paper_id,
                "title": raw_sample.title,
                "published": raw_sample.published,
            },
            "clean": {
                "paper_id": clean_sample["paper_id"],
                "title": clean_sample["title"],
                "published": clean_sample["published"],
                "summary_chars": int(clean_sample["summary_chars"]),
            },
            "index_metadata": indexed_metadata,
            "exact_id_lookup_match": exact_document["paper_id"] == sample_paper_id,
            "exact_title_lookup_match": exact_title_document["paper_id"] == sample_paper_id,
        },
        "semantic_search": {
            "query": sample["question"],
            "results": [
                {"paper_id": result.paper_id, "title": result.title, "score": result.score}
                for result in semantic_results
            ],
        },
        "qa_smoke": {
            "demo_answers_path": str(settings.paths.demo_answers),
            "demo_answer_count": len(qa_demo_answers),
            "source_hit_count": sum(item["source_hit"] for item in qa_demo_answers),
            "question": qa_result.question,
            "answer": qa_result.answer,
            "retrieved_doc_ids": qa_result.retrieved_doc_ids,
            "retrieved_titles": qa_result.retrieved_titles,
            "ground_truth_doc_id_present": sample_paper_id in qa_result.retrieved_doc_ids,
        },
        "llm_agent_smoke": _run_optional_llm_agent(settings, index, sample["question"]),
    }
    write_json(evidence_path, evidence)
    print(json.dumps(evidence, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
