from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord

_REQUIRED_CLEAN_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if pd.isna(value) if not isinstance(value, (list, tuple, dict, set)) else False:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value


def _stable_records_hash(records: Iterable[PaperRecord]) -> str:
    payload = [asdict(record) for record in records]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_safe).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_repaired_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Validate the repaired clean-data contract and return auditable signals."""
    missing_columns = sorted(_REQUIRED_CLEAN_COLUMNS.difference(df.columns))
    duplicated_ids = int(df["paper_id"].duplicated().sum()) if "paper_id" in df.columns else None
    missing_title = int(df["title"].fillna("").str.strip().eq("").sum()) if "title" in df.columns else None
    missing_summary = int(df["summary"].fillna("").str.strip().eq("").sum()) if "summary" in df.columns else None
    missing_embedding_text = (
        int(df["text_for_embedding"].fillna("").str.strip().eq("").sum())
        if "text_for_embedding" in df.columns
        else None
    )
    invalid_age_days = (
        int((pd.to_numeric(df["age_days"], errors="coerce") < 0).fillna(True).sum())
        if "age_days" in df.columns
        else None
    )

    passed = (
        not missing_columns
        and not df.empty
        and duplicated_ids == 0
        and missing_title == 0
        and missing_summary == 0
        and missing_embedding_text == 0
        and invalid_age_days == 0
    )

    return {
        "passed": bool(passed),
        "row_count": int(len(df)),
        "unique_paper_ids": int(df["paper_id"].nunique()) if "paper_id" in df.columns else 0,
        "missing_columns": missing_columns,
        "duplicate_paper_ids": duplicated_ids,
        "missing_title": missing_title,
        "missing_summary": missing_summary,
        "missing_text_for_embedding": missing_embedding_text,
        "invalid_age_days": invalid_age_days,
    }


def compare_recovery_states(
    baseline_df: pd.DataFrame | None,
    corrupted_df: pd.DataFrame | None,
    repaired_df: pd.DataFrame,
) -> dict[str, Any]:
    """Build compact evidence for baseline/corrupted/repaired comparison."""

    def state(df: pd.DataFrame | None) -> dict[str, Any] | None:
        if df is None:
            return None
        paper_ids = set(df["paper_id"].astype(str)) if "paper_id" in df.columns else set()
        duplicate_ids = int(df["paper_id"].duplicated().sum()) if "paper_id" in df.columns else None
        blank_summary = (
            int(df["summary"].fillna("").astype(str).str.strip().eq("").sum())
            if "summary" in df.columns
            else None
        )
        noise_rows = (
            int(df["summary"].fillna("").astype(str).str.contains("CORRUPTED_NOISE", regex=False).sum())
            if "summary" in df.columns
            else None
        )
        return {
            "row_count": int(len(df)),
            "unique_paper_ids": len(paper_ids),
            "duplicate_paper_ids": duplicate_ids,
            "blank_summary_rows": blank_summary,
            "noise_rows": noise_rows,
            "paper_ids": paper_ids,
        }

    baseline = state(baseline_df)
    corrupted = state(corrupted_df)
    repaired = state(repaired_df)
    assert repaired is not None

    comparison: dict[str, Any] = {
        "baseline": baseline,
        "corrupted": corrupted,
        "repaired": repaired,
    }

    if baseline is not None:
        restored_ids = repaired["paper_ids"].intersection(baseline["paper_ids"])
        missing_after_repair = baseline["paper_ids"].difference(repaired["paper_ids"])
        unexpected_after_repair = repaired["paper_ids"].difference(baseline["paper_ids"])
        comparison["recovery"] = {
            "baseline_ids_restored": len(restored_ids),
            "baseline_ids_missing_after_repair": sorted(missing_after_repair),
            "unexpected_ids_after_repair": sorted(unexpected_after_repair),
            "row_count_delta_vs_baseline": repaired["row_count"] - baseline["row_count"],
            "fully_matches_baseline_ids": not missing_after_repair and not unexpected_after_repair,
        }

    for value in (baseline, corrupted, repaired):
        if value is not None:
            value.pop("paper_ids", None)

    return comparison


def repair_from_raw_records(
    records: list[PaperRecord],
    *,
    run_date: datetime,
    repaired_csv_path: str | Path,
    repaired_json_path: str | Path,
    audit_log_path: str | Path,
    baseline_df: pd.DataFrame | None = None,
    corrupted_df: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Rebuild repaired data from the immutable raw-record snapshot.

    The function deliberately does not accept a corrupted dataframe as the repair
    source. It reuses the same cleaning function used by baseline, writes repaired
    artifacts to separate paths and emits lineage/recovery evidence.
    """
    if not records:
        raise ValueError("Raw records are empty; repair must start from a trusted raw snapshot.")

    repaired_csv_path = Path(repaired_csv_path)
    repaired_json_path = Path(repaired_json_path)
    audit_log_path = Path(audit_log_path)

    output_paths = {repaired_csv_path.resolve(), repaired_json_path.resolve(), audit_log_path.resolve()}
    if len(output_paths) != 3:
        raise ValueError("Repaired CSV, repaired JSON and audit log must use separate paths.")

    repaired_df = build_clean_dataframe(records, run_date=run_date)
    validation = validate_repaired_dataframe(repaired_df)
    if not validation["passed"]:
        raise ValueError(f"Repaired dataframe failed clean-data validation: {validation}")

    repaired_csv_path.parent.mkdir(parents=True, exist_ok=True)
    repaired_json_path.parent.mkdir(parents=True, exist_ok=True)
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    repaired_df.to_csv(repaired_csv_path, index=False)
    repaired_df.to_json(repaired_json_path, orient="records", force_ascii=False, indent=2)

    comparison = compare_recovery_states(baseline_df, corrupted_df, repaired_df)
    audit = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repair_source": "raw_records_snapshot",
        "repair_method": "re-run ingestion.cleaning.build_clean_dataframe",
        "raw_record_count": len(records),
        "raw_records_sha256": _stable_records_hash(records),
        "run_date": run_date.isoformat(),
        "cleaning_stats": _json_safe(repaired_df.attrs.get("cleaning_stats", {})),
        "validation": validation,
        "comparison": comparison,
        "artifacts": {
            "repaired_csv": str(repaired_csv_path),
            "repaired_json": str(repaired_json_path),
            "recovery_audit": str(audit_log_path),
        },
    }
    audit_log_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return repaired_df, audit
