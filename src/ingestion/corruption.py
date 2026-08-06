from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import build_text_for_embedding

CORRUPTION_SEED = 20251010

# Each scenario targets a distinct slice of rows so an observed metric change can be
# attributed to one corruption instead of an overlap of several.  The counts below are
# sized for the default 24-record fetch and scale down proportionally on smaller
# datasets, so a short Crossref response cannot leave the corrupted frame empty.
REFERENCE_ROWS = 24
LATEST_DROP_ROWS = 4
BLANK_SUMMARY_ROWS = 3
NOISE_ROWS = 3
TRUNCATED_TITLE_CHARS = 12
TRUNCATED_TITLE_ROWS = 3
STALE_DATE_ROWS = 3
STALE_DATE_SHIFT_DAYS = 2000
DUPLICATE_ROWS = 3

NOISE_TOKENS = [
    "lorem ipsum dolor sit amet",
    "###UNPARSED-XML-FRAGMENT###",
    "\\u00c2\\u00a0 &nbsp; &amp;lt;p&amp;gt;",
    "click here for the full text advertisement",
    "TODO fix encoding TODO fix encoding",
]


def _reserve(available: list[int], count: int) -> list[int]:
    """Take up to ``count`` row labels off the pool so scenarios never overlap."""
    taken = available[:count]
    del available[:count]
    return taken


def _scaled(reference_count: int, total_rows: int) -> int:
    """Scale a scenario size down for datasets smaller than the reference fetch.

    Keeps at least one row per scenario so every corruption still appears in the log,
    while leaving enough untouched rows that the corrupted dataset stays usable.
    """
    if total_rows >= REFERENCE_ROWS:
        return reference_count
    scaled = round(reference_count * total_rows / REFERENCE_ROWS)
    return max(1, min(reference_count, scaled))


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Inject deliberate, logged data-quality defects into a cleaned dataset.

    Six scenarios are applied to disjoint rows: dropping the most recent papers,
    blanking summaries, injecting noise into summaries, truncating titles, backdating
    publication dates, and duplicating rows.  ``text_for_embedding`` is rebuilt with
    the same renderer cleaning uses, so the corrupted index differs from the baseline
    only by the corrupted fields.  The input frame is never mutated.

    A JSON log is written to ``output_log_path`` recording, per scenario, the affected
    ``paper_id`` values, the parameters used, and the row count before/after.  The
    caller keeps that log as the evidence linking corruption to metric changes.
    """
    corrupted = df.copy(deep=True)
    rng = np.random.default_rng(CORRUPTION_SEED)
    events: list[dict[str, Any]] = []
    input_rows = len(corrupted)

    def record(
        corruption_type: str,
        parameters: dict[str, Any],
        paper_ids: list[str],
        rows_before: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        events.append(
            {
                "type": corruption_type,
                "parameters": parameters,
                "affected_paper_ids": paper_ids,
                "affected_rows": len(paper_ids),
                "rows_before": rows_before,
                "rows_after": len(corrupted),
                **(details or {}),
            }
        )

    if input_rows == 0:
        write_json(
            Path(output_log_path),
            {
                "generated_at": now_utc().isoformat(),
                "seed": CORRUPTION_SEED,
                "input_rows": 0,
                "output_rows": 0,
                "corruptions": [],
                "note": "Empty clean dataset: nothing to corrupt.",
            },
        )
        return corrupted

    # 1. Drop the newest papers. Freshness degrades and any test-set question whose
    #    ground truth is a recent paper becomes unanswerable from the corpus.
    drop_count = _scaled(LATEST_DROP_ROWS, input_rows)
    rows_before = len(corrupted)
    newest_first = corrupted.sort_values("published", ascending=False, kind="stable")
    dropped_labels = list(newest_first.index[:drop_count])
    dropped_ids = corrupted.loc[dropped_labels, "paper_id"].astype(str).tolist()
    dropped_dates = corrupted.loc[dropped_labels, "published"].astype(str).tolist()
    corrupted = corrupted.drop(index=dropped_labels)
    record(
        "drop_latest_records",
        {"rows_requested": drop_count},
        dropped_ids,
        rows_before,
        {"dropped_published_dates": dropped_dates},
    )

    # Remaining scenarios edit surviving rows; shuffle once and hand out disjoint slices.
    pool = list(corrupted.index)
    rng.shuffle(pool)

    # 2. Blank the summary: the field carrying most of the retrievable signal.
    blank_count = _scaled(BLANK_SUMMARY_ROWS, input_rows)
    rows_before = len(corrupted)
    blank_labels = _reserve(pool, blank_count)
    corrupted.loc[blank_labels, "summary"] = ""
    corrupted.loc[blank_labels, "summary_chars"] = 0
    record(
        "blank_summary",
        {"rows_requested": blank_count},
        corrupted.loc[blank_labels, "paper_id"].astype(str).tolist(),
        rows_before,
    )

    # 3. Inject boilerplate/markup noise, simulating a broken abstract parser.
    noise_count = _scaled(NOISE_ROWS, input_rows)
    rows_before = len(corrupted)
    noise_labels = _reserve(pool, noise_count)
    noise_applied: list[str] = []
    for label in noise_labels:
        token = NOISE_TOKENS[int(rng.integers(len(NOISE_TOKENS)))]
        corrupted.loc[label, "summary"] = f"{token} {corrupted.loc[label, 'summary']} {token}"
        corrupted.loc[label, "summary_chars"] = len(str(corrupted.loc[label, "summary"]))
        noise_applied.append(token)
    record(
        "noise_in_summary",
        {"rows_requested": noise_count, "tokens_used": noise_applied},
        corrupted.loc[noise_labels, "paper_id"].astype(str).tolist(),
        rows_before,
    )

    # 4. Truncate titles, breaking exact-title lookup and weakening title matching.
    title_count = _scaled(TRUNCATED_TITLE_ROWS, input_rows)
    rows_before = len(corrupted)
    title_labels = _reserve(pool, title_count)
    original_titles = corrupted.loc[title_labels, "title"].astype(str).tolist()
    corrupted.loc[title_labels, "title"] = (
        corrupted.loc[title_labels, "title"].astype(str).str.slice(0, TRUNCATED_TITLE_CHARS)
    )
    record(
        "truncate_title",
        {"rows_requested": title_count, "keep_chars": TRUNCATED_TITLE_CHARS},
        corrupted.loc[title_labels, "paper_id"].astype(str).tolist(),
        rows_before,
        {
            "titles_before": original_titles,
            "titles_after": corrupted.loc[title_labels, "title"].astype(str).tolist(),
        },
    )

    # 5. Backdate publication so freshness monitoring reports stale rows. age_days is
    #    shifted by the same amount to stay consistent with the new published date.
    stale_count = _scaled(STALE_DATE_ROWS, input_rows)
    rows_before = len(corrupted)
    stale_labels = _reserve(pool, stale_count)
    shifted = pd.to_datetime(
        corrupted.loc[stale_labels, "published"], errors="coerce"
    ) - pd.Timedelta(days=STALE_DATE_SHIFT_DAYS)
    dates_before = corrupted.loc[stale_labels, "published"].astype(str).tolist()
    corrupted.loc[stale_labels, "published"] = shifted.dt.date.astype(str)
    corrupted.loc[stale_labels, "age_days"] = (
        pd.to_numeric(corrupted.loc[stale_labels, "age_days"], errors="coerce").fillna(0)
        + STALE_DATE_SHIFT_DAYS
    ).astype(int)
    record(
        "stale_published_date",
        {"rows_requested": stale_count, "shift_days": STALE_DATE_SHIFT_DAYS},
        corrupted.loc[stale_labels, "paper_id"].astype(str).tolist(),
        rows_before,
        {
            "published_before": dates_before,
            "published_after": corrupted.loc[stale_labels, "published"].astype(str).tolist(),
        },
    )

    # 6. Re-append rows so paper_id is no longer unique: the uniqueness check must fail
    #    and retrieval can spend top-k slots on the same paper twice.
    duplicate_count = _scaled(DUPLICATE_ROWS, input_rows)
    rows_before = len(corrupted)
    duplicate_labels = _reserve(pool, duplicate_count)
    if duplicate_labels:
        corrupted = pd.concat([corrupted, corrupted.loc[duplicate_labels]], ignore_index=False)
    duplicate_ids = corrupted.loc[duplicate_labels, "paper_id"].astype(str).drop_duplicates().tolist()
    record(
        "duplicate_rows",
        {"rows_requested": duplicate_count},
        duplicate_ids,
        rows_before,
    )

    # 7. Rebuild the embedding text so the index reflects the corrupted fields.
    corrupted = corrupted.reset_index(drop=True)
    corrupted["text_for_embedding"] = corrupted.apply(build_text_for_embedding, axis=1)

    corrupted.attrs["corruption_stats"] = {
        "input_rows": input_rows,
        "output_rows": len(corrupted),
        "corruptions_applied": len(events),
    }

    # 8. Persist the log: this file is the evidence tying each metric change to a cause.
    write_json(
        Path(output_log_path),
        {
            "generated_at": now_utc().isoformat(),
            "seed": CORRUPTION_SEED,
            "input_rows": input_rows,
            "output_rows": len(corrupted),
            "rows_dropped": len(dropped_ids),
            "rows_duplicated": len(duplicate_labels),
            "corruptions": events,
        },
    )
    return corrupted
