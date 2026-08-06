from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def _clean_text(value: Any) -> str:
    """Return a stable, whitespace-normalized representation of a text field."""
    if value is None or pd.isna(value):
        return ""
    return normalize_whitespace(str(value))


def _clean_list(values: Any, fallback: str) -> list[str]:
    """Normalize list-like metadata while preserving its original order."""
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        values = []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned or [fallback]


def build_text_for_embedding(row: Any) -> str:
    """Render the single text representation indexed for a paper row.

    Cleaning and corruption both call this so a corrupted dataset differs from the
    baseline only by the corrupted fields, never by the embedding text format.
    """
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Published: {row['published']}\n"
        f"Summary: {row['summary']}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean Crossref records into the stable schema consumed by retrieval.

    Records without a usable DOI, title, summary, or publication date are removed.
    Duplicate DOIs retain the most recently updated record.  Cleaning statistics are
    exposed through ``DataFrame.attrs['cleaning_stats']`` for pipeline reporting.
    """
    rows: list[dict[str, Any]] = []
    rejected = {"missing_paper_id": 0, "missing_title": 0, "missing_summary": 0, "invalid_published": 0}

    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        published = pd.to_datetime(_clean_text(record.published), errors="coerce", utc=True)

        if not paper_id:
            rejected["missing_paper_id"] += 1
            continue
        if not title:
            rejected["missing_title"] += 1
            continue
        if not summary:
            rejected["missing_summary"] += 1
            continue
        if pd.isna(published):
            rejected["invalid_published"] += 1
            continue

        updated = pd.to_datetime(_clean_text(record.updated), errors="coerce", utc=True)
        if pd.isna(updated):
            updated = published
        authors = _clean_list(record.authors, "Unknown")
        categories = _clean_list(record.categories, "Uncategorized")

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": _clean_text(record.primary_category) or categories[0],
                "published": published,
                "updated": updated,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
            }
        )

    columns = [
        "paper_id", "title", "summary", "authors", "categories", "primary_category",
        "published", "updated", "abs_url", "pdf_url", "comment", "authors_joined",
        "categories_joined", "summary_chars", "age_days", "text_for_embedding",
    ]
    if not rows:
        result = pd.DataFrame(columns=columns)
        result.attrs["cleaning_stats"] = {"input_rows": len(records), "output_rows": 0, "duplicates_removed": 0, **rejected}
        return result

    df = pd.DataFrame(rows)
    before_deduplication = len(df)
    df = df.sort_values(["paper_id", "updated"], ascending=[True, False], kind="stable")
    df = df.drop_duplicates(subset="paper_id", keep="first").copy()

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize("UTC")
    else:
        run_timestamp = run_timestamp.tz_convert("UTC")
    df["authors_joined"] = df["authors"].map(compact_join)
    df["categories_joined"] = df["categories"].map(compact_join)
    df["summary_chars"] = df["summary"].str.len()
    df["age_days"] = (run_timestamp.normalize() - df["published"].dt.normalize()).dt.days.clip(lower=0)
    df["published"] = df["published"].dt.date.astype(str)
    df["updated"] = df["updated"].dt.date.astype(str)
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)
    result = df.sort_values(["published", "paper_id"], ascending=[False, True], kind="stable").reset_index(drop=True)[columns]
    result.attrs["cleaning_stats"] = {
        "input_rows": len(records),
        "output_rows": len(result),
        "duplicates_removed": before_deduplication - len(result),
        **rejected,
    }
    return result
