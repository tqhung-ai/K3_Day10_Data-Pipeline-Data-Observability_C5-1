from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Pseudo-code:
    1. Normalize title, summary, authors, categories.
    2. Parse published/updated date.
    3. Tinh age_days.
    4. Tao cot helper:
       - authors_joined
       - categories_joined
       - summary_chars
       - text_for_embedding
    5. Drop duplicates va filter row xau.
    6. Sort dataframe va return.
    """
    rows: list[dict] = []
    for record in records:
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        authors = [normalize_whitespace(a) for a in record.authors if a]
        categories = [normalize_whitespace(c) for c in record.categories if c]
        primary_category = normalize_whitespace(record.primary_category)
        published = normalize_whitespace(record.published)
        updated = normalize_whitespace(record.updated)
        abs_url = normalize_whitespace(record.abs_url)
        pdf_url = normalize_whitespace(record.pdf_url)
        comment = normalize_whitespace(record.comment)

        # Parse published date for age calculation
        try:
            published_dt = datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=UTC)
        except (ValueError, TypeError):
            published_dt = None

        if published_dt:
            age_days = (run_date - published_dt).days
        else:
            age_days = None

        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        summary_chars = len(summary)

        # Build text_for_embedding: title + summary + authors + categories
        text_parts = [title]
        if summary:
            text_parts.append(summary)
        if authors_joined:
            text_parts.append(f"Authors: {authors_joined}")
        if categories_joined:
            text_parts.append(f"Categories: {categories_joined}")
        if published:
            text_parts.append(f"Published: {published}")
        text_for_embedding = normalize_whitespace(" ".join(text_parts))

        rows.append(
            {
                "paper_id": record.paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "comment": comment,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    # Drop duplicates by paper_id, keeping first
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # Filter out rows with empty title or empty text_for_embedding
    df = df[df["title"].str.len() > 0]
    df = df[df["text_for_embedding"].str.len() > 0]

    # Sort by published date descending (newest first)
    df = df.sort_values(by=["published"], ascending=False).reset_index(drop=True)

    return df
