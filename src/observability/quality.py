from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd

from core.config import Settings
from core.utils import ensure_parent, now_utc, read_json


def _compute_age_days(published: str, run_date: datetime) -> int | None:
    """Compute age_days from published date string."""
    if not published:
        return None
    try:
        published_dt = datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=UTC)
        return (run_date - published_dt).days
    except (ValueError, TypeError):
        return None


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Tao bo data quality checks.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    run_date = now_utc()
    checks: dict[str, Any] = {
        "report_name": report_name,
        "timestamp": run_date.isoformat(),
        "total_rows": int(len(df)),
        "checks": {},
    }

    # 1. Row count
    checks["checks"]["row_count"] = {
        "passed": bool(len(df) > 0),
        "value": int(len(df)),
        "threshold": "> 0",
    }

    # 2. paper_id not null and unique
    if "paper_id" in df.columns:
        null_paper_ids = int(df["paper_id"].isna().sum())
        empty_paper_ids = int((df["paper_id"].astype(str).str.strip() == "").sum())
        duplicate_paper_ids = int(df["paper_id"].duplicated().sum())
    else:
        null_paper_ids = len(df)
        empty_paper_ids = 0
        duplicate_paper_ids = 0

    checks["checks"]["paper_id_not_null"] = {
        "passed": bool(null_paper_ids == 0 and empty_paper_ids == 0),
        "value": null_paper_ids + empty_paper_ids,
        "threshold": "0",
    }
    checks["checks"]["paper_id_unique"] = {
        "passed": bool(duplicate_paper_ids == 0),
        "value": duplicate_paper_ids,
        "threshold": "0",
    }

    # 3. title not null
    if "title" in df.columns:
        null_titles = int(df["title"].isna().sum())
        empty_titles = int((df["title"].astype(str).str.strip() == "").sum())
    else:
        null_titles = len(df)
        empty_titles = 0
    checks["checks"]["title_not_null"] = {
        "passed": bool((null_titles + empty_titles) == 0),
        "value": null_titles + empty_titles,
        "threshold": "0",
    }

    # 4. summary length
    if "summary" in df.columns:
        summary_lengths = df["summary"].astype(str).str.len()
        null_summaries = int(df["summary"].isna().sum())
        empty_summaries = null_summaries + int((summary_lengths == 0).sum())
        short_summaries = int((summary_lengths < 50).sum())
    else:
        empty_summaries = len(df)
        short_summaries = len(df)
    checks["checks"]["summary_not_empty"] = {
        "passed": bool(empty_summaries == 0),
        "value": empty_summaries,
        "threshold": "0",
    }
    checks["checks"]["summary_min_length"] = {
        "passed": bool(short_summaries == 0),
        "value": short_summaries,
        "threshold": "0 (min 50 chars)",
    }

    # 5. Duplicate rows (full row duplicates)
    duplicate_rows = int(df.duplicated().sum())
    checks["checks"]["duplicate_rows"] = {
        "passed": bool(duplicate_rows == 0),
        "value": duplicate_rows,
        "threshold": "0",
    }

    # 6. Freshness check using age_days column (computed at ingestion time)
    stale_threshold = settings.freshness_threshold_days
    if "age_days" in df.columns:
        stale_count = int(
            df["age_days"].dropna().astype(int).gt(stale_threshold).sum()
        )
    elif "published" in df.columns:
        age_days_list = []
        for _, row in df.iterrows():
            age = _compute_age_days(row.get("published", ""), run_date)
            age_days_list.append(age)
        stale_count = sum(1 for age in age_days_list if age is not None and age > stale_threshold)
    else:
        stale_count = 0

    checks["checks"]["freshness"] = {
        "passed": bool(stale_count == 0),
        "value": int(stale_count),
        "threshold": f"<= {stale_threshold} days",
    }

    # Overall pass/fail
    all_passed = bool(all(check.get("passed", False) for check in checks["checks"].values()))
    checks["overall_passed"] = all_passed

    # Write to data/quality/
    output_path = settings.paths.quality_dir / f"{report_name}.json"
    ensure_parent(output_path)
    output_path.write_text(json.dumps(checks, indent=2, ensure_ascii=True), encoding="utf-8")

    return checks


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report.

    Pseudo-code:
    1. Tim latest va oldest published date.
    2. Dem so dong stale.
    3. Tao payload:
       - latest_published
       - oldest_published
       - stale_rows
       - total_rows
       - is_fresh
    4. Ghi JSON report.
    """
    run_date = now_utc()
    total_rows = int(len(df))
    stale_threshold = settings.freshness_threshold_days

    # 1. Find latest and oldest published date
    if "published" in df.columns and total_rows > 0:
        published_dates = df["published"].dropna()
        published_dates = published_dates[published_dates.astype(str).str.strip() != ""]
        if len(published_dates) > 0:
            latest_published = str(published_dates.max())
            oldest_published = str(published_dates.min())
        else:
            latest_published = ""
            oldest_published = ""
    else:
        latest_published = ""
        oldest_published = ""

    # 2. Count stale rows using age_days column (computed at ingestion time)
    stale_rows = 0
    if "age_days" in df.columns:
        stale_rows = int(
            df["age_days"].dropna().astype(int).gt(stale_threshold).sum()
        )
    elif "published" in df.columns:
        for _, row in df.iterrows():
            age = _compute_age_days(row.get("published", ""), run_date)
            if age is not None and age > stale_threshold:
                stale_rows += 1

    # 3. Build payload
    is_fresh = bool(stale_rows == 0)

    report: dict[str, Any] = {
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "stale_rows": int(stale_rows),
        "total_rows": total_rows,
        "freshness_threshold_days": stale_threshold,
        "is_fresh": is_fresh,
        "timestamp": run_date.isoformat(),
    }

    # 4. Write JSON report
    ensure_parent(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")

    return report


def audit_embeddings(
    settings: Settings,
    embeddings_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Audit embedding manifest, collection name, and document count.

    Pseudo-code:
    1. Read embeddings manifest JSON.
    2. Extract collection_name and document count from manifest.
    3. Connect to Chroma and get the collection.
    4. Count actual documents in the collection.
    5. Compare manifest count with actual count.
    6. Return audit report.
    """
    embeddings_path = embeddings_path or settings.paths.embeddings_json
    run_date = now_utc()

    audit: dict[str, Any] = {
        "manifest_path": str(embeddings_path),
        "timestamp": run_date.isoformat(),
        "checks": {},
    }

    # 1. Read manifest
    if not embeddings_path.exists():
        audit["checks"]["manifest_exists"] = {
            "passed": False,
            "value": "missing",
            "expected": "exists",
        }
        audit["overall_passed"] = False
        if output_path:
            ensure_parent(output_path)
            output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=True), encoding="utf-8")
        return audit

    try:
        manifest = read_json(embeddings_path)
    except Exception as e:
        audit["checks"]["manifest_readable"] = {
            "passed": False,
            "value": str(e),
            "expected": "valid JSON",
        }
        audit["overall_passed"] = False
        if output_path:
            ensure_parent(output_path)
            output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=True), encoding="utf-8")
        return audit

    audit["checks"]["manifest_readable"] = {
        "passed": True,
        "value": "valid JSON",
        "expected": "valid JSON",
    }

    # 2. Extract collection_name and document count
    collection_name = manifest.get("collection_name", "unknown")
    manifest_doc_count = len(manifest.get("documents", []))

    audit["checks"]["collection_name"] = {
        "passed": bool(collection_name != "unknown" and collection_name),
        "value": collection_name,
        "expected": "non-empty string",
    }

    audit["checks"]["manifest_doc_count"] = {
        "passed": bool(manifest_doc_count > 0),
        "value": manifest_doc_count,
        "expected": "> 0",
    }

    # 3. Connect to Chroma and get collection
    try:
        client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
        collection = client.get_collection(name=collection_name)
        actual_count = collection.count()
    except Exception as e:
        audit["checks"]["chroma_collection_accessible"] = {
            "passed": False,
            "value": str(e),
            "expected": "collection exists",
        }
        audit["overall_passed"] = False
        if output_path:
            ensure_parent(output_path)
            output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=True), encoding="utf-8")
        return audit

    audit["checks"]["chroma_collection_accessible"] = {
        "passed": True,
        "value": f"count={actual_count}",
        "expected": "collection exists",
    }

    # 4. Compare counts
    audit["checks"]["doc_count_match"] = {
        "passed": bool(manifest_doc_count == actual_count),
        "value": f"manifest={manifest_doc_count}, actual={actual_count}",
        "expected": "manifest count == actual count",
    }

    # Overall pass/fail
    all_passed = bool(all(check.get("passed", False) for check in audit["checks"].values()))
    audit["overall_passed"] = all_passed

    # Write audit report if output_path provided
    if output_path:
        ensure_parent(output_path)
        output_path.write_text(json.dumps(audit, indent=2, ensure_ascii=True), encoding="utf-8")

    return audit


def forecast_signals(
    baseline_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corruption_log: list[dict[str, Any]],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Du bao quality/freshness signal se thay doi sau corruption.

    Pseudo-code:
    1. Dem so luong moi loai corruption tu log.
    2. Du bao row_count, paper_id_unique, summary_not_empty, summary_min_length,
       duplicate_rows, freshness stale_rows.
    3. Tra ve forecast report.
    """
    run_date = now_utc()

    # 1. Count corruption actions
    n_drop = sum(1 for action in corruption_log if action.get("action") == "drop_record")
    n_blank = sum(1 for action in corruption_log if action.get("action") == "blank_summary")
    n_noise = sum(1 for action in corruption_log if action.get("action") == "inject_noise")
    n_truncate = sum(1 for action in corruption_log if action.get("action") == "truncate_title")
    n_stale = sum(1 for action in corruption_log if action.get("action") == "stale_date")
    n_dup = sum(1 for action in corruption_log if action.get("action") == "duplicate_row")

    baseline_rows = baseline_quality.get("total_rows", 0)

    # 2. Forecast quality checks
    forecasted_rows = baseline_rows - n_drop + n_dup
    forecasted_paper_id_unique = n_dup
    forecasted_summary_not_empty = n_blank
    forecasted_summary_min_length = n_blank + n_noise  # blank + noise may be short
    forecasted_duplicate_rows = n_dup
    forecasted_stale_rows = n_stale

    forecast: dict[str, Any] = {
        "timestamp": run_date.isoformat(),
        "baseline_total_rows": baseline_rows,
        "corruption_actions": {
            "drop_record": n_drop,
            "blank_summary": n_blank,
            "inject_noise": n_noise,
            "truncate_title": n_truncate,
            "stale_date": n_stale,
            "duplicate_row": n_dup,
        },
        "forecasted_quality": {
            "row_count": {
                "baseline": baseline_rows,
                "forecasted": forecasted_rows,
                "delta": forecasted_rows - baseline_rows,
            },
            "paper_id_unique": {
                "baseline": baseline_quality.get("checks", {}).get("paper_id_unique", {}).get("value", 0),
                "forecasted": forecasted_paper_id_unique,
                "delta": forecasted_paper_id_unique - baseline_quality.get("checks", {}).get("paper_id_unique", {}).get("value", 0),
            },
            "summary_not_empty": {
                "baseline": baseline_quality.get("checks", {}).get("summary_not_empty", {}).get("value", 0),
                "forecasted": forecasted_summary_not_empty,
                "delta": forecasted_summary_not_empty - baseline_quality.get("checks", {}).get("summary_not_empty", {}).get("value", 0),
            },
            "summary_min_length": {
                "baseline": baseline_quality.get("checks", {}).get("summary_min_length", {}).get("value", 0),
                "forecasted": forecasted_summary_min_length,
                "delta": forecasted_summary_min_length - baseline_quality.get("checks", {}).get("summary_min_length", {}).get("value", 0),
            },
            "duplicate_rows": {
                "baseline": baseline_quality.get("checks", {}).get("duplicate_rows", {}).get("value", 0),
                "forecasted": forecasted_duplicate_rows,
                "delta": forecasted_duplicate_rows - baseline_quality.get("checks", {}).get("duplicate_rows", {}).get("value", 0),
            },
            "freshness": {
                "baseline": baseline_freshness.get("stale_rows", 0),
                "forecasted": forecasted_stale_rows,
                "delta": forecasted_stale_rows - baseline_freshness.get("stale_rows", 0),
            },
        },
        "overall_forecast": {
            "row_count_will_decrease": n_drop > 0,
            "duplicates_will_appear": n_dup > 0,
            "summaries_will_be_blank": n_blank > 0,
            "summaries_will_be_short": n_noise > 0,
            "freshness_will_degrade": n_stale > 0,
        },
    }

    # Write forecast report if output_path provided
    if output_path:
        ensure_parent(output_path)
        output_path.write_text(json.dumps(forecast, indent=2, ensure_ascii=True), encoding="utf-8")

    return forecast
