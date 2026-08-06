from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Build a deterministic evaluation set from cleaned paper data.

    Question wording intentionally matches the patterns handled by ``qa.py``.
    Category questions are omitted when the source only has the cleaning fallback
    ``Uncategorized``.
    """
    if df.empty:
        write_json(output_path, [])
        return []

    sample_size = min(4, len(df))
    sample_df = df.sort_values("paper_id", kind="stable").head(sample_size)
    test_set: list[dict[str, Any]] = []

    def add_question(
        paper_id: str,
        question_type: str,
        question: str,
        ground_truth: Any,
    ) -> None:
        test_set.append(
            {
                "id": f"{paper_id}::{question_type}",
                "question_type": question_type,
                "question": question,
                "ground_truth": str(ground_truth),
                "ground_truth_doc_ids": [paper_id],
            }
        )

    for _, row in sample_df.iterrows():
        paper_id = str(row["paper_id"])
        title = str(row["title"])
        add_question(
            paper_id,
            "summary",
            f"What is the main summary of the paper '{title}'?",
            row["summary"],
        )
        add_question(
            paper_id,
            "authors",
            f"Who authored the paper '{title}'?",
            row["authors_joined"],
        )
        add_question(
            paper_id,
            "date",
            f"When was the paper '{title}' published?",
            row["published"],
        )

        categories = str(row.get("categories_joined", "")).strip()
        if categories and categories.casefold() not in {"uncategorized", "unknown"}:
            add_question(
                paper_id,
                "categories",
                f"What categories does the paper '{title}' belong to?",
                categories,
            )

    write_json(output_path, test_set)
    return test_set
