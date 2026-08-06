from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from html import unescape
import logging
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_API_URL = "https://api.crossref.org/works"
REQUEST_TIMEOUT_SECONDS = 30
MAX_REQUEST_ATTEMPTS = 4
MAX_RETRY_DELAY_SECONDS = 30.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "Day10DataObservabilityLab/0.1 (Crossref metadata ingestion)"

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_DOI_PREFIX_PATTERN = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)

logger = logging.getLogger(__name__)


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


_PAPER_RECORD_FIELDS = {field.name for field in fields(PaperRecord)}


def _clean_text(value: Any, *, strip_markup: bool = False) -> str:
    if value is None:
        return ""
    text = str(value)
    if strip_markup:
        text = _HTML_TAG_PATTERN.sub(" ", text)
    return normalize_whitespace(unescape(text))


def _first_text(value: Any, *, strip_markup: bool = False) -> str:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            text = _clean_text(item, strip_markup=strip_markup)
            if text:
                return text
        return ""
    return _clean_text(value, strip_markup=strip_markup)


def _canonical_doi(value: Any) -> str:
    doi = _clean_text(value)
    return _DOI_PREFIX_PATTERN.sub("", doi).strip().lower()


def _unique_texts(values: Any) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value, strip_markup=True)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def _parse_authors(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []

    authors: list[str] = []
    seen: set[str] = set()
    for entry in value:
        if isinstance(entry, Mapping):
            explicit_name = _clean_text(entry.get("name"))
            name = explicit_name or normalize_whitespace(
                " ".join(
                    part
                    for part in (
                        _clean_text(entry.get("given")),
                        _clean_text(entry.get("family")),
                    )
                    if part
                )
            )
        else:
            name = _clean_text(entry)

        key = name.casefold()
        if name and key not in seen:
            authors.append(name)
            seen.add(key)
    return authors


def _date_from_parts(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    raw_parts = value.get("date-parts")
    if (
        not isinstance(raw_parts, Sequence)
        or isinstance(raw_parts, (str, bytes, bytearray))
        or not raw_parts
    ):
        return ""
    parts = raw_parts[0]
    if not isinstance(parts, Sequence) or isinstance(parts, (str, bytes, bytearray)) or not parts:
        return ""

    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _date_time(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    return _clean_text(value.get("date-time"))


def _first_date(item: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = item.get(key)
        parsed = _date_from_parts(value)
        if parsed:
            return parsed
        date_time = _date_time(value)
        if date_time:
            return date_time
    return ""


def _pdf_url(value: Any) -> str:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ""

    fallback = ""
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        url = _clean_text(entry.get("URL"))
        if not url:
            continue
        content_type = _clean_text(entry.get("content-type")).lower()
        if content_type == "application/pdf":
            return url
        if not fallback and url.lower().split("?", 1)[0].endswith(".pdf"):
            fallback = url
    return fallback


def _retry_delay_seconds(response: requests.Response | None, attempt: int) -> float:
    retry_after = "" if response is None else _clean_text(response.headers.get("Retry-After"))
    if retry_after:
        try:
            return min(MAX_RETRY_DELAY_SECONDS, max(0.0, float(retry_after)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return min(
                    MAX_RETRY_DELAY_SECONDS,
                    max(0.0, (retry_at - datetime.now(UTC)).total_seconds()),
                )
            except (TypeError, ValueError, OverflowError):
                pass
    return min(MAX_RETRY_DELAY_SECONDS, float(2**attempt))


def _request_crossref_payload(params: dict[str, Any]) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(MAX_REQUEST_ATTEMPTS):
        response: requests.Response | None = None
        try:
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except (requests.ConnectionError, requests.Timeout):
            if attempt == MAX_REQUEST_ATTEMPTS - 1:
                raise
            time.sleep(_retry_delay_seconds(None, attempt))
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_REQUEST_ATTEMPTS - 1:
            time.sleep(_retry_delay_seconds(response, attempt))
            continue

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Crossref response must be a JSON object.")
        return payload

    raise RuntimeError("Crossref request exhausted all retry attempts.")


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref list response into the raw record contract.

    Records without a DOI or title cannot be traced reliably and are skipped.
    Optional Crossref metadata is preserved as an empty string/list so the
    cleaning stage can apply and report its own quality gates.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("Crossref payload must be a JSON object.")
    message = payload.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Crossref payload is missing the 'message' object.")
    items = message.get("items")
    if not isinstance(items, list):
        raise ValueError("Crossref payload 'message.items' must be a list.")

    records: list[PaperRecord] = []
    dropped: Counter[str] = Counter()
    for item in items:
        if not isinstance(item, Mapping):
            dropped["not_an_object"] += 1
            continue

        paper_id = _canonical_doi(item.get("DOI"))
        title = _first_text(item.get("title"), strip_markup=True)
        if not paper_id:
            dropped["missing_doi"] += 1
            continue
        if not title:
            dropped["missing_title"] += 1
            continue

        categories = _unique_texts(item.get("subject"))
        published = _first_date(
            item,
            ("published", "published-print", "published-online", "issued", "created"),
        )
        updated = _first_date(item, ("deposited", "indexed")) or published
        abs_url = _clean_text(item.get("URL")) or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=_clean_text(item.get("abstract"), strip_markup=True),
                authors=_parse_authors(item.get("author")),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_pdf_url(item.get("link")),
                comment="",
            )
        )

    logger.info(
        "Parsed Crossref payload: raw=%d parsed=%d dropped=%d reasons=%s",
        len(items),
        len(records),
        sum(dropped.values()),
        dict(dropped),
    )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref data and persist both source and parsed snapshots."""
    if settings.max_results <= 0:
        raise ValueError("settings.max_results must be greater than zero.")

    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    payload = _request_crossref_payload(params)

    # Preserve source evidence even when parsing later fails.
    write_json(settings.paths.raw_api_response, payload)
    # A new response must never be paired with parsed records from an older snapshot.
    settings.paths.raw_records_json.unlink(missing_ok=True)
    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])

    if not records:
        raise ValueError("Crossref returned no usable records with both DOI and title.")
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load and validate a previously persisted raw record snapshot."""
    payload = read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")

    records: list[PaperRecord] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record at index {index} must be a JSON object.")

        item_fields = set(item)
        missing = _PAPER_RECORD_FIELDS - item_fields
        extra = item_fields - _PAPER_RECORD_FIELDS
        if missing or extra:
            details = []
            if missing:
                details.append(f"missing={sorted(missing)}")
            if extra:
                details.append(f"extra={sorted(extra)}")
            raise ValueError(f"Invalid raw record schema at index {index}: {', '.join(details)}")

        for field_name in _PAPER_RECORD_FIELDS - {"authors", "categories"}:
            if not isinstance(item[field_name], str):
                raise ValueError(f"Raw record {index}.{field_name} must be a string.")
        for field_name in ("authors", "categories"):
            values = item[field_name]
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError(f"Raw record {index}.{field_name} must be a list of strings.")

        records.append(PaperRecord(**item))
    return records
