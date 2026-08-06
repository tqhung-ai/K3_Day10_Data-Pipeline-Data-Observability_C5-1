from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.utils import write_json


def _short(value: Any, limit: int = 160) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    run_timestamp = pd.Timestamp(datetime.now(UTC)).normalize()
    df["age_days"] = (run_timestamp - published.dt.normalize()).dt.days.clip(lower=0)
    df["text_for_embedding"] = df.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Published: {row['published']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create deterministic, logged corruption from a clean dataframe copy."""
    if df.empty:
        raise ValueError("Cannot corrupt an empty dataframe.")
    required = {"paper_id", "title", "summary", "published", "authors_joined", "categories_joined"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing columns: {sorted(missing)}")

    corrupted = df.copy(deep=True)
    operations: list[dict[str, Any]] = []

    # 1. Drop the newest record, preserving the baseline dataframe untouched.
    newest_index = corrupted.assign(_published=pd.to_datetime(corrupted["published"], errors="coerce"))["_published"].idxmax()
    newest_id = str(corrupted.loc[newest_index, "paper_id"])
    corrupted = corrupted.drop(index=newest_index).reset_index(drop=True)
    operations.append({"type": "drop_latest", "paper_id": newest_id, "before_count": len(df), "after_count": len(corrupted), "parameter": "max(published)"})

    if len(corrupted) < 5:
        raise ValueError("Corruption scenario requires at least five records after dropping latest.")

    # 2. Blank summary.
    index = corrupted.index[0]
    paper_id = str(corrupted.loc[index, "paper_id"])
    before = corrupted.loc[index, "summary"]
    corrupted.loc[index, "summary"] = ""
    operations.append({"type": "blank_summary", "paper_id": paper_id, "before": _short(before), "after": "", "parameter": "summary=''"})

    # 3. Inject deterministic noise into another summary.
    index = corrupted.index[1]
    paper_id = str(corrupted.loc[index, "paper_id"])
    before = corrupted.loc[index, "summary"]
    corrupted.loc[index, "summary"] = f"[CORRUPTED_NOISE_2026] {before} unrelated noise token xyzzy."
    operations.append({"type": "summary_noise", "paper_id": paper_id, "before": _short(before), "after": _short(corrupted.loc[index, "summary"]), "parameter": "prefix + unrelated noise token"})

    # 4. Truncate a title while retaining a traceable paper ID.
    index = corrupted.index[2]
    paper_id = str(corrupted.loc[index, "paper_id"])
    before = corrupted.loc[index, "title"]
    title = str(before)
    corrupted.loc[index, "title"] = title[: max(12, len(title) // 3)]
    operations.append({"type": "truncate_title", "paper_id": paper_id, "before": _short(before), "after": _short(corrupted.loc[index, "title"]), "parameter": "keep first max(12, len(title)//3) characters"})

    # 5. Make one publication date stale beyond the configured threshold.
    index = corrupted.index[3]
    paper_id = str(corrupted.loc[index, "paper_id"])
    before = corrupted.loc[index, "published"]
    corrupted.loc[index, "published"] = "2024-01-01"
    operations.append({"type": "stale_published", "paper_id": paper_id, "before": str(before), "after": "2024-01-01", "parameter": "freshness_threshold_days=180"})

    # 6. Add one duplicate row with the same stable identity.
    duplicate_index = corrupted.index[4]
    duplicate_id = str(corrupted.loc[duplicate_index, "paper_id"])
    corrupted = pd.concat([corrupted, corrupted.loc[[duplicate_index]]], ignore_index=True)
    operations.append({"type": "duplicate_row", "paper_id": duplicate_id, "before_count": len(corrupted) - 1, "after_count": len(corrupted), "parameter": "duplicate exact row"})

    _rebuild_embedding_text(corrupted)
    corrupted = corrupted.reset_index(drop=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scenario": "deterministic_cp5_v1",
        "input_rows": int(len(df)),
        "output_rows": int(len(corrupted)),
        "operations": operations,
        "baseline_untouched": True,
    }
    write_json(output_log_path, payload)
    return corrupted
