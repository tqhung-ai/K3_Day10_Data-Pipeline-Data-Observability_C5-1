from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run data quality checks and persist their result.

    Pseudo-code:
    1. Check row count.
    2. Check `paper_id` not null va unique.
    3. Check `title` not null.
    4. Check do dai `summary`.
    5. Check freshness bang `age_days`.
    6. Ghi ket qua vao `data/quality/`.
    """
    required = ["paper_id", "title", "summary", "text_for_embedding", "published", "age_days"]
    missing = [field for field in required if field not in df.columns]
    checks: dict[str, Any] = {
        "report_name": report_name,
        "row_count": int(len(df)),
        "missing_columns": missing,
        "missing_paper_id": int(df["paper_id"].isna().sum()) if "paper_id" in df else None,
        "empty_paper_id": int(df["paper_id"].fillna("").astype(str).str.strip().eq("").sum()) if "paper_id" in df else None,
        "duplicate_paper_id": int(df["paper_id"].duplicated().sum()) if "paper_id" in df else None,
        "missing_title": int(df["title"].fillna("").astype(str).str.strip().eq("").sum()) if "title" in df else None,
        "missing_summary": int(df["summary"].fillna("").astype(str).str.strip().eq("").sum()) if "summary" in df else None,
        "missing_text_for_embedding": int(df["text_for_embedding"].fillna("").astype(str).str.strip().eq("").sum()) if "text_for_embedding" in df else None,
        "invalid_published": int(pd.to_datetime(df["published"], errors="coerce", utc=True).isna().sum()) if "published" in df else None,
        "invalid_age_days": int((pd.to_numeric(df["age_days"], errors="coerce").isna() | (pd.to_numeric(df["age_days"], errors="coerce") < 0)).sum()) if "age_days" in df else None,
    }
    failures = bool(missing) or any(value not in (0, False) for key, value in checks.items() if key not in {"report_name", "row_count", "missing_columns"} and value is not None)
    checks["passed"] = bool(len(df) > 0 and not failures)
    checks["status"] = "PASS" if checks["passed"] else "FAIL"
    write_json(settings.paths.quality_dir / f"{report_name}.json", checks)
    return checks


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Build and persist a freshness report.

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
    dates = pd.to_datetime(df["published"], errors="coerce", utc=True) if "published" in df else pd.Series(dtype="datetime64[ns, UTC]")
    ages = pd.to_numeric(df["age_days"], errors="coerce") if "age_days" in df else pd.Series(dtype=float)
    stale = ages > settings.freshness_threshold_days
    payload = {
        "newest_published": dates.max().date().isoformat() if not dates.dropna().empty else None,
        "oldest_published": dates.min().date().isoformat() if not dates.dropna().empty else None,
        "mean_age_days": float(ages.mean()) if not ages.dropna().empty else None,
        "median_age_days": float(ages.median()) if not ages.dropna().empty else None,
        "max_age_days": int(ages.max()) if not ages.dropna().empty else None,
        "stale_count": int(stale.sum()),
        "total_rows": int(len(df)),
        "stale_ratio": float(stale.mean()) if len(df) else 0.0,
        "threshold_days": settings.freshness_threshold_days,
        "passed": bool(len(df) > 0 and not stale.any()),
        "status": "PASS" if len(df) > 0 and not stale.any() else "FAIL",
    }
    write_json(report_path, payload)
    return payload
