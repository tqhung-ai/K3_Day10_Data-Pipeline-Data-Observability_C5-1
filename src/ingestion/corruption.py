from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


_REQUIRED_COLUMNS = {"paper_id", "title", "summary", "published"}
_NOISE_TEXT = " [CORRUPTED_NOISE: unrelated metadata token sequence xyz-123]"


def _json_safe(value: Any) -> Any:
    """Convert pandas/numpy/datetime values into JSON-serialisable values."""
    if value is None or value is pd.NA:
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if pd.isna(value):
        return None
    return value


def _build_text_for_embedding(row: pd.Series) -> str:
    authors = row.get("authors_joined", "")
    categories = row.get("categories_joined", "")
    parts = [
        f"Title: {row.get('title', '')}",
        f"Authors: {authors}" if authors else "",
        f"Categories: {categories}" if categories else "",
        f"Published: {row.get('published', '')}",
        f"Summary: {row.get('summary', '')}",
    ]
    return "\n".join(str(part) for part in parts if part)


def _append_event(
    events: list[dict[str, Any]],
    *,
    corruption_type: str,
    paper_id: str,
    parameter: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    events.append(
        {
            "corruption_type": corruption_type,
            "paper_id": paper_id,
            "parameter": _json_safe(parameter),
            "before": _json_safe(before),
            "after": _json_safe(after),
        }
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Create a deterministic corrupted copy of a clean paper dataframe.

    Corruptions are intentional and auditable:
    - drop latest records;
    - blank summaries;
    - inject text noise;
    - truncate titles;
    - age publication dates;
    - append duplicate rows.

    The input dataframe is never mutated. A JSON corruption log is always
    written to ``output_log_path``. The function adapts the number of affected
    rows to small datasets while ensuring each selected row has lineage through
    ``paper_id``.
    """
    missing_columns = sorted(_REQUIRED_COLUMNS.difference(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required clean columns: {missing_columns}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")

    original = df.copy(deep=True).reset_index(drop=True)
    corrupted = original.copy(deep=True)
    events: list[dict[str, Any]] = []

    # 1) Drop the newest records. At least one row remains for downstream work.
    published_ts = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    latest_order = published_ts.sort_values(ascending=False, na_position="last").index.tolist()
    drop_count = min(max(1, len(corrupted) // 20), max(0, len(corrupted) - 1))
    drop_indices = latest_order[:drop_count]
    for index in drop_indices:
        row = corrupted.loc[index]
        _append_event(
            events,
            corruption_type="drop_latest_record",
            paper_id=str(row["paper_id"]),
            parameter={"selection": "latest_published", "rank": drop_indices.index(index) + 1},
            before={"row_count": len(corrupted), "published": row["published"]},
            after={"row_count": len(corrupted) - 1, "record_present": False},
        )
        corrupted = corrupted.drop(index=index)
    corrupted = corrupted.reset_index(drop=True)

    # Choose disjoint target rows when possible so evidence is easy to explain.
    target_indices = list(corrupted.index)
    cursor = 0

    def take_index() -> int:
        nonlocal cursor
        index = target_indices[cursor % len(target_indices)]
        cursor += 1
        return index

    # 2) Blank summaries.
    blank_count = min(max(1, len(corrupted) // 15), len(corrupted))
    for _ in range(blank_count):
        index = take_index()
        before_summary = str(corrupted.at[index, "summary"])
        corrupted.at[index, "summary"] = ""
        if "summary_chars" in corrupted.columns:
            corrupted.at[index, "summary_chars"] = 0
        _append_event(
            events,
            corruption_type="blank_summary",
            paper_id=str(corrupted.at[index, "paper_id"]),
            parameter={"replacement": "empty_string"},
            before={"summary_chars": len(before_summary), "summary": before_summary},
            after={"summary_chars": 0, "summary": ""},
        )

    # 3) Inject deterministic noise into summaries.
    noise_count = min(max(1, len(corrupted) // 15), len(corrupted))
    for _ in range(noise_count):
        index = take_index()
        before_summary = str(corrupted.at[index, "summary"])
        after_summary = before_summary + _NOISE_TEXT
        corrupted.at[index, "summary"] = after_summary
        if "summary_chars" in corrupted.columns:
            corrupted.at[index, "summary_chars"] = len(after_summary)
        _append_event(
            events,
            corruption_type="inject_summary_noise",
            paper_id=str(corrupted.at[index, "paper_id"]),
            parameter={"noise": _NOISE_TEXT.strip()},
            before={"summary_chars": len(before_summary), "summary": before_summary},
            after={"summary_chars": len(after_summary), "summary": after_summary},
        )

    # 4) Truncate titles.
    title_count = min(max(1, len(corrupted) // 20), len(corrupted))
    for _ in range(title_count):
        index = take_index()
        before_title = str(corrupted.at[index, "title"])
        keep_chars = max(8, min(24, max(1, len(before_title) // 3)))
        after_title = before_title[:keep_chars].rstrip()
        corrupted.at[index, "title"] = after_title
        _append_event(
            events,
            corruption_type="truncate_title",
            paper_id=str(corrupted.at[index, "paper_id"]),
            parameter={"keep_chars": keep_chars},
            before={"title": before_title, "title_chars": len(before_title)},
            after={"title": after_title, "title_chars": len(after_title)},
        )

    # 5) Make publication dates stale by ten years.
    stale_count = min(max(1, len(corrupted) // 20), len(corrupted))
    for _ in range(stale_count):
        index = take_index()
        before_value = corrupted.at[index, "published"]
        parsed = pd.to_datetime(before_value, errors="coerce", utc=True)
        if pd.isna(parsed):
            continue
        stale_date = parsed - pd.DateOffset(years=10)
        after_value = stale_date.date().isoformat()
        corrupted.at[index, "published"] = after_value
        if "age_days" in corrupted.columns:
            current_age = pd.to_numeric(pd.Series([corrupted.at[index, "age_days"]]), errors="coerce").iloc[0]
            if pd.notna(current_age):
                corrupted.at[index, "age_days"] = int(current_age) + 3652
        _append_event(
            events,
            corruption_type="age_published_date",
            paper_id=str(corrupted.at[index, "paper_id"]),
            parameter={"years_subtracted": 10},
            before={"published": before_value},
            after={"published": after_value},
        )

    # Rebuild retrieval text after field-level corruption.
    if "text_for_embedding" in corrupted.columns:
        corrupted["text_for_embedding"] = corrupted.apply(_build_text_for_embedding, axis=1)

    # 6) Append duplicate rows last so duplicate count is explicit.
    duplicate_count = min(max(1, len(corrupted) // 20), len(corrupted))
    duplicate_source = corrupted.head(duplicate_count).copy(deep=True)
    before_duplicate_append = len(corrupted)
    corrupted = pd.concat([corrupted, duplicate_source], ignore_index=True)
    for offset, (_, row) in enumerate(duplicate_source.iterrows(), start=1):
        _append_event(
            events,
            corruption_type="duplicate_record",
            paper_id=str(row["paper_id"]),
            parameter={"copy_number": offset},
            before={"row_count": before_duplicate_append + offset - 1, "copies": 1},
            after={"row_count": before_duplicate_append + offset, "copies": 2},
        )

    output_path = Path(output_log_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_row_count": len(original),
        "corrupted_row_count": len(corrupted),
        "source_unique_paper_ids": int(original["paper_id"].nunique(dropna=False)),
        "corrupted_unique_paper_ids": int(corrupted["paper_id"].nunique(dropna=False)),
        "event_count": len(events),
        "events": events,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    corrupted.attrs["corruption_log"] = payload
    return corrupted
