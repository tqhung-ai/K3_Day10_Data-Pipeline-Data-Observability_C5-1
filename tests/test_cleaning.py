from __future__ import annotations

from datetime import UTC, datetime
import unittest

from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord


def make_record(**overrides) -> PaperRecord:
    values = {
        "paper_id": "10.1000/example",
        "title": "Example title",
        "summary": "A source-backed summary.",
        "authors": [" Jane Doe ", "Jane Doe"],
        "categories": [],
        "primary_category": "",
        "published": "2026-01-05",
        "updated": "2026-01-06",
        "abs_url": "https://doi.org/10.1000/example",
        "pdf_url": "",
        "comment": "",
    }
    values.update(overrides)
    return PaperRecord(**values)


class BuildCleanDataframeTests(unittest.TestCase):
    def test_filters_deduplicates_and_builds_embedding_fields(self) -> None:
        older = make_record()
        newer = make_record(title="Updated title", updated="2026-01-08")
        invalid = make_record(paper_id="10.1000/invalid", summary="")

        result = build_clean_dataframe(
            [older, newer, invalid],
            run_date=datetime(2026, 1, 10, tzinfo=UTC),
        )

        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual(row["title"], "Updated title")
        self.assertEqual(row["authors"], ["Jane Doe"])
        self.assertEqual(row["categories"], [])
        self.assertEqual(row["categories_joined"], "")
        self.assertEqual(row["age_days"], 5)
        self.assertNotIn("Categories:", row["text_for_embedding"])
        self.assertIn("Summary: A source-backed summary.", row["text_for_embedding"])
        self.assertEqual(
            result.attrs["cleaning_stats"],
            {
                "input_rows": 3,
                "output_rows": 1,
                "duplicates_removed": 1,
                "missing_paper_id": 0,
                "missing_title": 0,
                "missing_summary": 1,
                "invalid_published": 0,
            },
        )

    def test_preserves_real_primary_category_without_fabricating_missing_data(self) -> None:
        categorized = make_record(
            paper_id="10.1000/category",
            categories=[" Retrieval ", "retrieval"],
            primary_category="RAG",
        )
        uncategorized = make_record(paper_id="10.1000/no-category")

        result = build_clean_dataframe(
            [categorized, uncategorized],
            run_date=datetime(2026, 1, 10, tzinfo=UTC),
        ).set_index("paper_id")

        self.assertEqual(result.loc["10.1000/category", "categories"], ["RAG", "Retrieval"])
        self.assertEqual(result.loc["10.1000/no-category", "categories"], [])
        self.assertEqual(result.loc["10.1000/no-category", "primary_category"], "")


if __name__ == "__main__":
    unittest.main()
