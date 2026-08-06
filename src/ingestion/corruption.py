from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd

from core.utils import ensure_parent, normalize_whitespace


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate nhieu dang data corruption.

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
    random.seed(42)
    corrupted = df.copy()
    log: list[dict] = []

    n = len(corrupted)
    if n == 0:
        ensure_parent(Path(output_log_path))
        Path(output_log_path).write_text(json.dumps([], indent=2), encoding="utf-8")
        return corrupted

    # 1. Drop some latest records (newest by published date)
    n_drop = max(1, n // 6)
    drop_indices = corrupted.head(n_drop).index.tolist()
    for idx in drop_indices:
        log.append({"action": "drop_record", "paper_id": corrupted.loc[idx, "paper_id"], "index": int(idx)})
    corrupted = corrupted.drop(index=drop_indices).reset_index(drop=True)

    n = len(corrupted)

    # 2. Blank summary on some rows
    n_blank = max(1, n // 5)
    blank_indices = random.sample(corrupted.index.tolist(), n_blank)
    for idx in blank_indices:
        log.append({"action": "blank_summary", "paper_id": corrupted.loc[idx, "paper_id"], "index": int(idx)})
        corrupted.loc[idx, "summary"] = ""
        corrupted.loc[idx, "summary_chars"] = 0

    # 3. Inject noise into text (summary) on some rows
    n_noise = max(1, n // 5)
    noise_indices = random.sample(corrupted.index.tolist(), n_noise)
    noise_strings = ["[NOISE]", "xxx", "???", "###", "$$$"]
    for idx in noise_indices:
        original = corrupted.loc[idx, "summary"]
        noise = random.choice(noise_strings)
        corrupted.loc[idx, "summary"] = normalize_whitespace(f"{noise} {original} {noise}")
        log.append({"action": "inject_noise", "paper_id": corrupted.loc[idx, "paper_id"], "index": int(idx), "noise": noise})

    # 4. Truncate title on some rows
    n_truncate = max(1, n // 6)
    truncate_indices = random.sample(corrupted.index.tolist(), n_truncate)
    for idx in truncate_indices:
        original_title = corrupted.loc[idx, "title"]
        truncated = original_title[: max(5, len(original_title) // 3)]
        corrupted.loc[idx, "title"] = truncated
        log.append({"action": "truncate_title", "paper_id": corrupted.loc[idx, "paper_id"], "index": int(idx), "original": original_title, "truncated": truncated})

    # 5. Make published date stale (old) on some rows
    n_stale = max(1, n // 5)
    stale_indices = random.sample(corrupted.index.tolist(), n_stale)
    for idx in stale_indices:
        original_date = corrupted.loc[idx, "published"]
        corrupted.loc[idx, "published"] = "2000-01-01"
        corrupted.loc[idx, "age_days"] = None
        log.append({"action": "stale_date", "paper_id": corrupted.loc[idx, "paper_id"], "index": int(idx), "original": original_date, "new": "2000-01-01"})

    # 6. Add duplicate rows
    n_dup = max(1, n // 8)
    dup_sample = corrupted.sample(n=n_dup, random_state=42)
    corrupted = pd.concat([corrupted, dup_sample], ignore_index=True)
    for _, row in dup_sample.iterrows():
        log.append({"action": "duplicate_row", "paper_id": row["paper_id"]})

    # 7. Rebuild text_for_embedding
    for idx in corrupted.index:
        title = corrupted.loc[idx, "title"]
        summary = corrupted.loc[idx, "summary"]
        authors_joined = corrupted.loc[idx, "authors_joined"]
        categories_joined = corrupted.loc[idx, "categories_joined"]
        published = corrupted.loc[idx, "published"]

        text_parts = [title]
        if summary:
            text_parts.append(summary)
        if authors_joined:
            text_parts.append(f"Authors: {authors_joined}")
        if categories_joined:
            text_parts.append(f"Categories: {categories_joined}")
        if published:
            text_parts.append(f"Published: {published}")
        corrupted.loc[idx, "text_for_embedding"] = normalize_whitespace(" ".join(text_parts))

    # 8. Write corruption log
    ensure_parent(Path(output_log_path))
    Path(output_log_path).write_text(json.dumps(log, indent=2, ensure_ascii=True), encoding="utf-8")

    return corrupted
