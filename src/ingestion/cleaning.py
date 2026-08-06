from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


_CLEAN_COLUMNS = [
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
]


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return normalize_whitespace(str(value))


def _clean_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, (list, tuple, set)):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def _empty_clean_dataframe(input_rows: int, rejected: dict[str, int]) -> pd.DataFrame:
    result = pd.DataFrame(columns=_CLEAN_COLUMNS)
    result.attrs["cleaning_stats"] = {
        "input_rows": input_rows,
        "output_rows": 0,
        "duplicates_removed": 0,
        **rejected,
    }
    return result


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Convert raw Crossref records into the stable retrieval schema.

    Missing source metadata remains empty rather than being replaced with a
    fabricated value. Rejection and deduplication counts are exposed through
    ``DataFrame.attrs['cleaning_stats']`` for audit and reporting.
    """
    rejected = {
        "missing_paper_id": 0,
        "missing_title": 0,
        "missing_summary": 0,
        "invalid_published": 0,
    }
    rows: list[dict[str, Any]] = []

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
        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        primary_category = _clean_text(record.primary_category)
        if primary_category and primary_category.casefold() not in {
            value.casefold() for value in categories
        }:
            categories.insert(0, primary_category)

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category or (categories[0] if categories else ""),
                "published": published,
                "updated": updated,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
            }
        )

    if not rows:
        return _empty_clean_dataframe(len(records), rejected)

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
    df["age_days"] = (
        run_timestamp.normalize() - df["published"].dt.normalize()
    ).dt.days.astype(int)
    df["published"] = df["published"].dt.date.astype(str)
    df["updated"] = df["updated"].dt.date.astype(str)
    df["text_for_embedding"] = df.apply(
        lambda row: "\n".join(
            part
            for part in (
                f"Title: {row['title']}",
                f"Authors: {row['authors_joined']}" if row["authors_joined"] else "",
                f"Categories: {row['categories_joined']}" if row["categories_joined"] else "",
                f"Published: {row['published']}",
                f"Summary: {row['summary']}",
            )
            if part
        ),
        axis=1,
    )

    result = (
        df.sort_values(["published", "paper_id"], ascending=[False, True], kind="stable")
        .reset_index(drop=True)[_CLEAN_COLUMNS]
        .copy()
    )
    result.attrs["cleaning_stats"] = {
        "input_rows": len(records),
        "output_rows": len(result),
        "duplicates_removed": before_deduplication - len(result),
        **rejected,
    }
    return result
