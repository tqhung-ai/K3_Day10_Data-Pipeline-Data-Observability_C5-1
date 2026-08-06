from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


MIN_SUMMARY_CHARS = 20


def _non_empty(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def _check(name: str, passed: bool, observed: Any, expected: Any) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run reproducible data-quality gates and persist a JSON report."""
    total_rows = int(len(df))
    checks: list[dict[str, Any]] = []

    checks.append(_check("row_count", total_rows > 0, total_rows, "> 0"))

    if "paper_id" in df:
        paper_ids = df["paper_id"]
        non_null_ids = _non_empty(paper_ids)
        duplicate_ids = int(paper_ids[non_null_ids].astype(str).duplicated().sum())
        checks.append(_check("paper_id_not_null", bool(non_null_ids.all()), int((~non_null_ids).sum()), 0))
        checks.append(_check("paper_id_unique", duplicate_ids == 0, duplicate_ids, 0))
    else:
        checks.extend(
            [
                _check("paper_id_not_null", False, "column missing", 0),
                _check("paper_id_unique", False, "column missing", 0),
            ]
        )

    if "title" in df:
        missing_titles = int((~_non_empty(df["title"])).sum())
        checks.append(_check("title_not_null", missing_titles == 0, missing_titles, 0))
    else:
        checks.append(_check("title_not_null", False, "column missing", 0))

    if "summary" in df:
        summary_lengths = df["summary"].fillna("").astype(str).str.strip().str.len()
        short_summaries = int((summary_lengths < MIN_SUMMARY_CHARS).sum())
        checks.append(
            _check(
                "summary_min_length",
                short_summaries == 0,
                short_summaries,
                f"0 rows shorter than {MIN_SUMMARY_CHARS} characters",
            )
        )
    else:
        checks.append(_check("summary_min_length", False, "column missing", 0))

    if "text_for_embedding" in df:
        missing_embedding_text = int((~_non_empty(df["text_for_embedding"])).sum())
        checks.append(_check("text_for_embedding_not_empty", missing_embedding_text == 0, missing_embedding_text, 0))
    else:
        checks.append(_check("text_for_embedding_not_empty", False, "column missing", 0))

    if "age_days" in df:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
        invalid_age = int((ages.isna() | (ages < 0)).sum())
        checks.append(_check("age_days_valid", invalid_age == 0, invalid_age, 0))
        stale_rows = int((ages > settings.freshness_threshold_days).sum())
    else:
        checks.append(_check("age_days_valid", False, "column missing", 0))
        stale_rows = total_rows

    checks.append(
        _check(
            "freshness_threshold",
            total_rows > 0 and stale_rows == 0,
            stale_rows,
            f"0 rows older than {settings.freshness_threshold_days} days",
        )
    )

    payload = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": total_rows,
        "success": all(check["passed"] for check in checks),
        "checks": checks,
    }
    write_json(settings.paths.quality_dir / f"{report_name}.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build and persist a freshness summary from published dates and age_days."""
    total_rows = int(len(df))
    dates = pd.to_datetime(df.get("published", pd.Series(dtype=str)), errors="coerce", utc=True)
    valid_dates = dates.dropna()
    if "age_days" in df:
        ages = pd.to_numeric(df["age_days"], errors="coerce")
    else:
        ages = pd.Series(dtype=float)

    stale_rows = int((ages > settings.freshness_threshold_days).sum())
    invalid_published = int(dates.isna().sum())
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold_days": settings.freshness_threshold_days,
        "latest_published": valid_dates.max().date().isoformat() if not valid_dates.empty else None,
        "oldest_published": valid_dates.min().date().isoformat() if not valid_dates.empty else None,
        "stale_rows": stale_rows,
        "invalid_published_rows": invalid_published,
        "total_rows": total_rows,
        "is_fresh": total_rows > 0 and invalid_published == 0 and stale_rows == 0,
    }
    write_json(report_path, payload)
    return payload
