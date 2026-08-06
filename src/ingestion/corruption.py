from __future__ import annotations

import pandas as pd
from datetime import UTC, datetime
from pathlib import Path

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate several deterministic data corruption scenarios.

    Pseudo-code:
    1. Drop mot so latest records.
    2. Blank summary o mot so dong.
    3. Inject noise vao text.
    4. Lam title bi truncate.
    5. Lam published date cu di.
    6. Add duplicate rows.
    7. Rebuild `text_for_embedding`.
    8. Ghi corruption log vao output_log_path.
    """
    if len(df) < 4:
        raise ValueError("At least four clean records are required for controlled corruption.")
    corrupted = df.copy(deep=True).reset_index(drop=True)
    logs = []

    def record(index: int, field: str, before, after, corruption_type: str) -> None:
        logs.append({
            "corruption_type": corruption_type,
            "paper_id": str(corrupted.at[index, "paper_id"]),
            "field": field,
            "before": before,
            "after": after,
            "parameter": {"seed": 10, "row_index": index},
            "timestamp": datetime.now(UTC).isoformat(),
        })

    before = corrupted.at[0, "summary"]
    corrupted.at[0, "summary"] = ""
    record(0, "summary", before, "", "blank_summary")

    before = corrupted.at[1, "published"]
    corrupted.at[1, "published"] = "2000-01-01"
    corrupted.at[1, "age_days"] = 9999
    record(1, "published", before, "2000-01-01", "stale_date")

    before = corrupted.at[2, "text_for_embedding"]
    corrupted.at[2, "text_for_embedding"] = f"{before} CONTROLLED_NOISE_10"
    record(2, "text_for_embedding", before, corrupted.at[2, "text_for_embedding"], "add_noise")

    duplicate = corrupted.iloc[[3]].copy()
    corrupted = pd.concat([corrupted, duplicate], ignore_index=True)
    record(3, "record", "one row", "duplicated row", "duplicate_row")

    corrupted["text_for_embedding"] = corrupted.apply(
        lambda row: (
            f"Title: {row['title']}\n"
            f"Authors: {row['authors_joined']}\n"
            f"Categories: {row['categories_joined']}\n"
            f"Published: {row['published']}\n"
            f"Summary: {row['summary']}"
        ),
        axis=1,
    )
    corrupted.at[2, "text_for_embedding"] += " CONTROLLED_NOISE_10"

    write_json(Path(output_log_path), logs)
    return corrupted
