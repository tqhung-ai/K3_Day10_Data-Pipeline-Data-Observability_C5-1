from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import requests

from ingestion.crossref import (
    PaperRecord,
    fetch_source_records,
    load_raw_records,
    parse_crossref_payload,
)


class FakeResponse:
    def __init__(self, status_code: int, payload: object, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> object:
        return self._payload


def sample_payload() -> dict:
    return {
        "status": "ok",
        "message": {
            "items": [
                {
                    "DOI": "https://doi.org/10.1000/ABC",
                    "title": ["  A <i>RAG</i> &amp; Agent Study  "],
                    "abstract": "<jats:p>Useful &amp; reproducible evidence.</jats:p>",
                    "author": [
                        {"given": " Jane ", "family": " Doe "},
                        {"name": "Research Group"},
                    ],
                    "subject": ["Artificial Intelligence", " artificial intelligence ", "RAG"],
                    "published": {"date-parts": [[2026, 2]]},
                    "deposited": {"date-time": "2026-03-04T12:30:00Z"},
                    "link": [
                        {"URL": "https://example.org/article", "content-type": "text/html"},
                        {
                            "URL": "https://example.org/article.pdf",
                            "content-type": "application/pdf",
                        },
                    ],
                },
                {
                    "DOI": "10.1000/fallback",
                    "title": ["Fallback metadata"],
                    "issued": {"date-parts": [[2025]]},
                },
                {"title": ["Missing DOI"]},
                {"DOI": "10.1000/missing-title", "title": []},
                "not-an-object",
            ]
        },
    }


class ParseCrossrefPayloadTests(unittest.TestCase):
    def test_maps_and_normalizes_crossref_fields(self) -> None:
        records = parse_crossref_payload(sample_payload())

        self.assertEqual(len(records), 2)
        record = records[0]
        self.assertEqual(record.paper_id, "10.1000/abc")
        self.assertEqual(record.title, "A RAG & Agent Study")
        self.assertEqual(record.summary, "Useful & reproducible evidence.")
        self.assertEqual(record.authors, ["Jane Doe", "Research Group"])
        self.assertEqual(record.categories, ["Artificial Intelligence", "RAG"])
        self.assertEqual(record.primary_category, "Artificial Intelligence")
        self.assertEqual(record.published, "2026-02-01")
        self.assertEqual(record.updated, "2026-03-04T12:30:00Z")
        self.assertEqual(record.abs_url, "https://doi.org/10.1000/abc")
        self.assertEqual(record.pdf_url, "https://example.org/article.pdf")
        self.assertEqual(record.comment, "")

    def test_keeps_optional_fields_empty_for_cleaning_quality_gates(self) -> None:
        record = parse_crossref_payload(sample_payload())[1]

        self.assertEqual(record.published, "2025-01-01")
        self.assertEqual(record.updated, "2025-01-01")
        self.assertEqual(record.authors, [])
        self.assertEqual(record.categories, [])
        self.assertEqual(record.summary, "")
        self.assertEqual(record.abs_url, "https://doi.org/10.1000/fallback")
        self.assertEqual(record.pdf_url, "")

    def test_rejects_malformed_envelopes(self) -> None:
        invalid_payloads = [{}, {"message": None}, {"message": {}}, {"message": {"items": {}}}]

        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_crossref_payload(payload)


class RawArtifactTests(unittest.TestCase):
    def _settings(self, root: Path) -> SimpleNamespace:
        return SimpleNamespace(
            source_query="agentic RAG",
            source_filter="from-pub-date:2026-01-01,has-abstract:true",
            max_results=24,
            paths=SimpleNamespace(
                raw_api_response=root / "crossref_response.json",
                raw_records_json=root / "crossref_records.json",
            ),
        )

    def test_fetch_retries_and_writes_round_trip_artifacts(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._settings(root)
            responses = [
                FakeResponse(429, {}, {"Retry-After": "0"}),
                FakeResponse(503, {}, {"Retry-After": "0"}),
                FakeResponse(200, sample_payload()),
            ]

            with (
                patch("ingestion.crossref.requests.get", side_effect=responses) as request_get,
                patch("ingestion.crossref.time.sleep") as sleep,
            ):
                records = fetch_source_records(settings)

            self.assertEqual(request_get.call_count, 3)
            self.assertEqual(sleep.call_count, 2)
            self.assertEqual(
                json.loads(settings.paths.raw_api_response.read_text()),
                sample_payload(),
            )
            self.assertEqual(load_raw_records(settings.paths.raw_records_json), records)
            self.assertEqual(request_get.call_args.kwargs["params"]["rows"], 24)

    def test_raw_response_is_saved_before_parsing(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = self._settings(root)
            settings.paths.raw_records_json.write_text('[{"stale": true}]', encoding="utf-8")
            with (
                patch(
                    "ingestion.crossref.requests.get",
                    return_value=FakeResponse(200, sample_payload()),
                ),
                patch(
                    "ingestion.crossref.parse_crossref_payload",
                    side_effect=ValueError("bad record"),
                ),
                self.assertRaisesRegex(ValueError, "bad record"),
            ):
                fetch_source_records(settings)

            self.assertEqual(
                json.loads(settings.paths.raw_api_response.read_text()),
                sample_payload(),
            )
            self.assertFalse(settings.paths.raw_records_json.exists())

    def test_load_rejects_wrong_schema_and_types(self) -> None:
        from tempfile import TemporaryDirectory

        valid_record = PaperRecord(
            paper_id="10.1000/example",
            title="Example",
            summary="Summary",
            authors=["Jane Doe"],
            categories=[],
            primary_category="",
            published="2026-01-01",
            updated="2026-01-02",
            abs_url="https://doi.org/10.1000/example",
            pdf_url="",
            comment="",
        )
        cases = [
            {"records": [dict(asdict(valid_record), unexpected=True)]},
            {
                "records": [
                    {key: value for key, value in asdict(valid_record).items() if key != "title"}
                ]
            },
            {"records": [dict(asdict(valid_record), authors="Jane Doe")]},
            {"records": {"not": "a list"}},
        ]

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "records.json"
            for case in cases:
                with self.subTest(case=case):
                    path.write_text(json.dumps(case["records"]), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_raw_records(path)


if __name__ == "__main__":
    unittest.main()
