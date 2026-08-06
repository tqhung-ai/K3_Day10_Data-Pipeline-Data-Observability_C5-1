from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, normalize_whitespace, write_json


_REQUIRED_COLUMNS = {
    "paper_id",
    "title",
    "summary",
    "authors_joined",
    "categories_joined",
    "published",
}


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return normalize_whitespace(str(value))


def build_test_set(df: pd.DataFrame, output_path: Path) -> list[dict[str, Any]]:
    """Build a deterministic evaluation set using only clean source evidence."""
    missing_columns = _REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing columns: {sorted(missing_columns)}")

    candidates = df.copy()
    for column in _REQUIRED_COLUMNS:
        candidates[column] = candidates[column].map(_text)
    candidates = candidates[
        candidates["paper_id"].ne("")
        & candidates["title"].ne("")
        & candidates["summary"].ne("")
        & candidates["published"].ne("")
    ].copy()
    candidates = candidates.drop_duplicates(subset="paper_id", keep="first")
    candidates = candidates.sort_values(
        ["published", "paper_id"],
        ascending=[False, True],
        kind="stable",
    ).reset_index(drop=True)
    if len(candidates) < 3:
        raise ValueError("At least three valid clean documents are required to build the test set.")

    specifications = [
        (
            "summary",
            "summary",
            lambda row: f"What is the main summary of '{row['title']}'?",
            lambda row: first_sentence(row["summary"]),
        ),
        (
            "authors",
            "authors_joined",
            lambda row: f"Who authored '{row['title']}'?",
            lambda row: row["authors_joined"],
        ),
        (
            "date",
            "published",
            lambda row: f"When was '{row['title']}' published?",
            lambda row: row["published"],
        ),
        (
            "categories",
            "categories_joined",
            lambda row: f"What categories are listed for '{row['title']}'?",
            lambda row: row["categories_joined"],
        ),
    ]

    test_set: list[dict[str, Any]] = []
    offset = 0
    questions_per_type = 2
    for question_type, evidence_column, build_question, build_answer in specifications:
        eligible = candidates[candidates[evidence_column].ne("")]
        if eligible.empty:
            continue
        selected = eligible.iloc[offset : offset + questions_per_type]
        if selected.empty:
            selected = eligible.head(questions_per_type)
        offset += questions_per_type

        for row in selected.to_dict(orient="records"):
            ground_truth = _text(build_answer(row))
            if not ground_truth:
                continue
            paper_id = row["paper_id"]
            test_set.append(
                {
                    "id": f"{question_type}:{paper_id}",
                    "question_type": question_type,
                    "question": build_question(row),
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    if len({item["question_type"] for item in test_set}) < 2:
        raise ValueError("The clean data does not support at least two evaluation question types.")
    if len({item["id"] for item in test_set}) != len(test_set):
        raise ValueError("Evaluation question IDs must be unique.")

    write_json(Path(output_path), test_set)
    return test_set
