from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from ingestion.crossref import PaperRecord
from ingestion.repair import repair_from_raw_records, validate_repaired_dataframe


def _record(paper_id: str, title: str, summary: str, published: str) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        summary=summary,
        authors=["Nguyen Van A"],
        categories=["Artificial Intelligence"],
        primary_category="Artificial Intelligence",
        published=published,
        updated=published,
        abs_url=f"https://doi.org/{paper_id}",
        pdf_url="",
        comment="",
    )


def test_repair_rebuilds_from_raw_and_writes_audit(tmp_path):
    records = [
        _record("10.1000/a", "Paper A", "Summary A", "2025-01-01"),
        _record("10.1000/b", "Paper B", "Summary B", "2025-02-01"),
    ]
    baseline = pd.DataFrame({"paper_id": ["10.1000/a", "10.1000/b"]})
    corrupted = pd.DataFrame(
        {
            "paper_id": ["10.1000/a", "10.1000/a"],
            "summary": ["", "[CORRUPTED_NOISE]"],
        }
    )

    repaired, audit = repair_from_raw_records(
        records,
        run_date=datetime(2026, 8, 6, tzinfo=timezone.utc),
        repaired_csv_path=tmp_path / "papers_repaired.csv",
        repaired_json_path=tmp_path / "papers_repaired.json",
        audit_log_path=tmp_path / "repair_audit.json",
        baseline_df=baseline,
        corrupted_df=corrupted,
    )

    assert (tmp_path / "papers_repaired.csv").exists()
    assert (tmp_path / "papers_repaired.json").exists()
    assert (tmp_path / "repair_audit.json").exists()
    assert validate_repaired_dataframe(repaired)["passed"] is True
    assert set(repaired["paper_id"]) == {"10.1000/a", "10.1000/b"}
    assert audit["repair_source"] == "raw_records_snapshot"
    assert audit["comparison"]["recovery"]["fully_matches_baseline_ids"] is True


def test_repair_rejects_empty_raw_snapshot(tmp_path):
    with pytest.raises(ValueError, match="Raw records are empty"):
        repair_from_raw_records(
            [],
            run_date=datetime(2026, 8, 6, tzinfo=timezone.utc),
            repaired_csv_path=tmp_path / "papers_repaired.csv",
            repaired_json_path=tmp_path / "papers_repaired.json",
            audit_log_path=tmp_path / "repair_audit.json",
        )
