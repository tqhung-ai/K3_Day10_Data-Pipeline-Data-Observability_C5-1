from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from evaluation.testset import build_test_set


def clean_dataframe(with_category: bool = False) -> pd.DataFrame:
    rows = []
    for index in range(8):
        rows.append(
            {
                "paper_id": f"10.1000/paper-{index}",
                "title": f"Paper {index}",
                "summary": f"Summary sentence {index}. More detail.",
                "authors_joined": f"Author {index}",
                "categories_joined": "RAG" if with_category and index == 0 else "",
                "published": f"2026-01-{index + 1:02d}",
            }
        )
    return pd.DataFrame(rows)


class BuildTestSetTests(unittest.TestCase):
    def test_builds_multiple_question_types_without_inventing_categories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_set.json"
            test_set = build_test_set(clean_dataframe(), output_path)

            self.assertEqual(len(test_set), 6)
            self.assertEqual(
                {item["question_type"] for item in test_set},
                {"summary", "authors", "date"},
            )
            self.assertEqual(len({item["id"] for item in test_set}), len(test_set))
            self.assertTrue(all(item["ground_truth_doc_ids"] for item in test_set))
            self.assertEqual(json.loads(output_path.read_text(encoding="utf-8")), test_set)

    def test_adds_category_questions_only_when_source_evidence_exists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            test_set = build_test_set(
                clean_dataframe(with_category=True),
                Path(temp_dir) / "test_set.json",
            )

        category_questions = [
            item for item in test_set if item["question_type"] == "categories"
        ]
        self.assertEqual(len(category_questions), 1)
        self.assertEqual(category_questions[0]["ground_truth"], "RAG")

    def test_rejects_missing_clean_contract(self) -> None:
        with TemporaryDirectory() as temp_dir, self.assertRaises(ValueError):
            build_test_set(pd.DataFrame([{"paper_id": "10.1000/x"}]), Path(temp_dir) / "x.json")


if __name__ == "__main__":
    unittest.main()
