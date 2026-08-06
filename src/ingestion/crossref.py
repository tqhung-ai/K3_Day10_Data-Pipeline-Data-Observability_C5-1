from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.config import Settings
import re
import requests
import time
import logging
from core.utils import write_json, read_json


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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    records = []
    for item in payload.get("message", {}).get("items", []):
        paper_id = item.get("DOI", "")
        if not paper_id:
            continue
            
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        
        abstract = item.get("abstract", "")
        abstract = re.sub(r"<[^>]+>", "", abstract)
        
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "")
            family = author.get("family", "")
            if given or family:
                authors.append(f"{given} {family}".strip())
                
        categories = item.get("subject", [])
        primary_category = categories[0] if categories else ""
        
        published = ""
        issued = item.get("issued", {}).get("date-parts", [[]])
        if issued and issued[0]:
            parts = issued[0]
            year = str(parts[0])
            month = str(parts[1]).zfill(2) if len(parts) > 1 else "01"
            day = str(parts[2]).zfill(2) if len(parts) > 2 else "01"
            published = f"{year}-{month}-{day}"
            
        updated = published
        abs_url = f"https://doi.org/{paper_id}"
        pdf_url = ""
        
        links = item.get("link", [])
        for link in links:
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL", "")
                break
                
        records.append(PaperRecord(
            paper_id=paper_id, title=title, summary=abstract,
            authors=authors, categories=categories,
            primary_category=primary_category, published=published,
            updated=updated, abs_url=abs_url, pdf_url=pdf_url, comment=""
        ))
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    url = "https://api.crossref.org/works"
    params = {"query": settings.source_query, "filter": settings.source_filter, "rows": settings.max_results}
    
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            write_json(settings.paths.raw_api_response, data)
            records = parse_crossref_payload(data)
            
            # Save raw records as dict
            import dataclasses
            records_dicts = [dataclasses.asdict(r) for r in records]
            write_json(settings.paths.raw_records_json, records_dicts)
            return records
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)
    return []


def load_raw_records(path: Path) -> list[PaperRecord]:
    data = read_json(path)
    records = []
    for item in data:
        records.append(PaperRecord(
            paper_id=item.get("paper_id", ""), title=item.get("title", ""), summary=item.get("summary", ""),
            authors=item.get("authors", []), categories=item.get("categories", []),
            primary_category=item.get("primary_category", ""), published=item.get("published", ""),
            updated=item.get("updated", ""), abs_url=item.get("abs_url", ""), pdf_url=item.get("pdf_url", ""),
            comment=item.get("comment", "")
        ))
    return records
