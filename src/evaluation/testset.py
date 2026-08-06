from __future__ import annotations

import json
from typing import Any

import pandas as pd

from core.utils import ensure_parent


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set tu cleaned dataframe.

    Pseudo-code:
    1. Kiem tra so luong document toi thieu.
    2. Chon mot so paper dai dien.
    3. Tao nhieu loai cau hoi:
       - summary
       - authors
       - date
       - categories
    4. Moi row can co:
       - id
       - question_type
       - question
       - ground_truth
       - ground_truth_doc_ids
    5. Ghi file JSON vao output_path.
    """
    min_docs = 5
    if len(df) < min_docs:
        raise ValueError(f"Need at least {min_docs} documents to build test set, got {len(df)}.")

    # Select representative papers (spread across the dataset)
    n_questions = min(12, len(df))
    selected_indices = df.index.tolist()[:n_questions]

    test_set: list[dict[str, Any]] = []
    question_id = 0

    for idx in selected_indices:
        row = df.loc[idx]
        paper_id = row["paper_id"]
        title = row["title"]
        summary = row["summary"]
        authors_joined = row["authors_joined"]
        categories_joined = row["categories_joined"]
        published = row["published"]

        # Summary question
        if summary and len(summary) > 20:
            question_id += 1
            test_set.append(
                {
                    "id": f"q{question_id:03d}",
                    "question_type": "summary",
                    "question": f"What is the summary of the paper '{title}'?",
                    "ground_truth": summary[:500],
                    "ground_truth_doc_ids": [paper_id],
                }
            )

        # Authors question
        if authors_joined:
            question_id += 1
            test_set.append(
                {
                    "id": f"q{question_id:03d}",
                    "question_type": "authors",
                    "question": f"Who are the authors of the paper '{title}'?",
                    "ground_truth": authors_joined,
                    "ground_truth_doc_ids": [paper_id],
                }
            )

        # Date question
        if published:
            question_id += 1
            test_set.append(
                {
                    "id": f"q{question_id:03d}",
                    "question_type": "date",
                    "question": f"When was the paper '{title}' published?",
                    "ground_truth": published,
                    "ground_truth_doc_ids": [paper_id],
                }
            )

        # Categories question
        if categories_joined:
            question_id += 1
            test_set.append(
                {
                    "id": f"q{question_id:03d}",
                    "question_type": "categories",
                    "question": f"What categories does the paper '{title}' belong to?",
                    "ground_truth": categories_joined,
                    "ground_truth_doc_ids": [paper_id],
                }
            )

    # Write to output path
    ensure_parent(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_set, f, indent=2, ensure_ascii=True)

    return test_set
