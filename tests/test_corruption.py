from __future__ import annotations

import json

import pandas as pd
import pytest

from ingestion.corruption import corrupt_clean_dataframe


def _sample_dataframe(size: int = 30) -> pd.DataFrame:
    rows = []
    for index in range(size):
        rows.append(
            {
                "paper_id": f"10.1000/paper-{index:03d}",
                "title": f"A sufficiently descriptive research paper title number {index}",
                "summary": f"Original summary content for research paper number {index}.",
                "authors_joined": "Author A; Author B",
                "categories_joined": "cs.AI; cs.LG",
                "published": (pd.Timestamp("2026-08-01", tz="UTC") - pd.Timedelta(days=index)).date().isoformat(),
                "summary_chars": 55,
                "age_days": index,
                "text_for_embedding": "baseline text",
            }
        )
    return pd.DataFrame(rows)


def test_corruption_is_deterministic_auditable_and_does_not_mutate_input(tmp_path):
    baseline = _sample_dataframe()
    original = baseline.copy(deep=True)
    log_path = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(baseline, log_path)

    pd.testing.assert_frame_equal(baseline, original)
    assert log_path.exists()
    payload = json.loads(log_path.read_text(encoding="utf-8"))

    event_types = {event["corruption_type"] for event in payload["events"]}
    assert event_types == {
        "drop_latest_record",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "age_published_date",
        "duplicate_record",
    }
    assert payload["source_row_count"] == len(baseline)
    assert payload["corrupted_row_count"] == len(corrupted)
    assert payload["event_count"] == len(payload["events"])
    assert all(event["paper_id"] for event in payload["events"])
    assert all("before" in event and "after" in event for event in payload["events"])

    assert corrupted["paper_id"].duplicated().any()
    assert (corrupted["summary"] == "").any()
    assert corrupted["summary"].str.contains("CORRUPTED_NOISE", regex=False).any()
    assert corrupted["text_for_embedding"].str.contains("CORRUPTED_NOISE", regex=False).any()


def test_corruption_rejects_missing_contract_columns(tmp_path):
    dataframe = pd.DataFrame([{"paper_id": "x", "title": "title"}])
    with pytest.raises(ValueError, match="Missing required clean columns"):
        corrupt_clean_dataframe(dataframe, tmp_path / "log.json")


def test_corruption_rejects_empty_dataframe(tmp_path):
    dataframe = pd.DataFrame(columns=["paper_id", "title", "summary", "published"])
    with pytest.raises(ValueError, match="empty"):
        corrupt_clean_dataframe(dataframe, tmp_path / "log.json")
