from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from core.config import Settings
from core.utils import ensure_parent, normalize_whitespace


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


CROSSREF_API_URL = "https://api.crossref.org/works"


def _extract_authors(item: dict) -> list[str]:
    authors: list[str] = []
    for author in item.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        full = normalize_whitespace(f"{given} {family}")
        if full:
            authors.append(full)
    return authors


def _extract_categories(item: dict) -> list[str]:
    subjects = item.get("subject", [])
    if isinstance(subjects, list):
        return [normalize_whitespace(str(s)) for s in subjects if s]
    return []


def _extract_date(item: dict, key: str) -> str:
    date_info = item.get(key)
    if not date_info:
        return ""
    date_parts = date_info.get("date-parts", [])
    if date_parts and date_parts[0]:
        parts = date_parts[0]
        year = parts[0] if len(parts) > 0 else ""
        month = parts[1] if len(parts) > 1 else 1
        day = parts[2] if len(parts) > 2 else 1
        return f"{year}-{month:02d}-{day:02d}"
    return ""


def _extract_urls(item: dict) -> tuple[str, str]:
    abs_url = item.get("URL", "")
    pdf_url = ""
    for link in item.get("link", []):
        if link.get("content-type") == "application/pdf" or "pdf" in link.get("URL", "").lower():
            pdf_url = link.get("URL", "")
            break
    if not pdf_url:
        for link in item.get("link", []):
            url = link.get("URL", "")
            if url:
                pdf_url = url
                break
    return abs_url, pdf_url


def _extract_comment(item: dict) -> str:
    comment = item.get("comments", "")
    if not comment:
        comment = item.get("remark", "")
    return normalize_whitespace(str(comment)) if comment else ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Pseudo-code:
    1. Duyet `payload["message"]["items"]`.
    2. Lay DOI, title, abstract, authors, subject, dates, URLs.
    3. Chuan hoa text va bo record khong hop le.
    4. Tra ve list `PaperRecord`.
    """
    message = payload.get("message", {})
    items = message.get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        paper_id = item.get("DOI", "")
        if not paper_id:
            continue

        titles = item.get("title", [])
        title = normalize_whitespace(titles[0]) if titles else ""
        if not title:
            continue

        abstract = item.get("abstract", "")
        if abstract:
            abstract = normalize_whitespace(abstract)
        else:
            abstract = ""

        authors = _extract_authors(item)
        categories = _extract_categories(item)
        primary_category = categories[0] if categories else ""

        published = _extract_date(item, "issued") or _extract_date(item, "created")
        updated = _extract_date(item, "updated") if item.get("updated") else published

        abs_url, pdf_url = _extract_urls(item)
        comment = _extract_comment(item)

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=abstract,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records.

    Pseudo-code:
    1. Tao params tu `settings.source_query`, `settings.source_filter`, `settings.max_results`.
    2. Goi API voi retry cho cac status code nhu 429/503.
    3. Luu raw response vao `settings.paths.raw_api_response`.
    4. Parse payload bang `parse_crossref_payload`.
    5. Luu records vao `settings.paths.raw_records_json`.
    """
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    max_retries = 5
    backoff_seconds = 2
    response = None

    for attempt in range(max_retries):
        try:
            response = requests.get(CROSSREF_API_URL, params=params, timeout=30)
            if response.status_code == 200:
                break
            if response.status_code in (429, 503, 502, 504):
                wait = backoff_seconds * (2 ** attempt)
                time.sleep(wait)
                continue
            response.raise_for_status()
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2 ** attempt))
                continue
            raise

    if response is None or response.status_code != 200:
        raise RuntimeError(f"Failed to fetch from Crossref after {max_retries} retries.")

    payload = response.json()

    ensure_parent(settings.paths.raw_api_response)
    settings.paths.raw_api_response.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    records = parse_crossref_payload(payload)

    ensure_parent(settings.paths.raw_records_json)
    settings.paths.raw_records_json.write_text(
        json.dumps([asdict(r) for r in records], indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    data = json.loads(path.read_text(encoding="utf-8"))
    records: list[PaperRecord] = []
    for item in data:
        records.append(
            PaperRecord(
                paper_id=item["paper_id"],
                title=item["title"],
                summary=item["summary"],
                authors=item["authors"],
                categories=item["categories"],
                primary_category=item["primary_category"],
                published=item["published"],
                updated=item["updated"],
                abs_url=item["abs_url"],
                pdf_url=item["pdf_url"],
                comment=item["comment"],
            )
        )
    return records
