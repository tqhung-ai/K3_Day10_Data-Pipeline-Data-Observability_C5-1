from __future__ import annotations

from typing import Any
from pathlib import Path

import pandas as pd

from core.utils import write_json


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Create a deterministic frozen evaluation set from clean data.

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
    required = {"paper_id", "title", "summary", "authors_joined", "categories_joined", "published"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Clean dataframe is missing test-set fields: {sorted(missing)}")
    if df.empty:
        raise ValueError("Cannot create an evaluation set from an empty dataframe.")

    samples: list[dict[str, Any]] = []
    for index, (_, row) in enumerate(df.head(5).iterrows(), start=1):
        paper_id = str(row["paper_id"])
        title = str(row["title"])
        questions = [
            ("title", f"What is the title of the paper with paper_id '{paper_id}'?", title),
            ("summary", f"What is the main topic of the paper '{title}'?", str(row["summary"])),
            ("authors", f"Who authored the paper '{title}'?", str(row["authors_joined"])),
            ("published", f"When was the paper '{title}' published?", str(row["published"])),
            ("categories", f"What categories are associated with the paper '{title}'?", str(row["categories_joined"])),
        ]
        for question_type, question, ground_truth in questions:
            samples.append(
                {
                    "id": f"q-{index:02d}-{question_type}",
                    "question_type": question_type,
                    "question": question,
                    "ground_truth": ground_truth,
                    "ground_truth_doc_ids": [paper_id],
                }
            )
    write_json(Path(output_path), samples)
    return samples
