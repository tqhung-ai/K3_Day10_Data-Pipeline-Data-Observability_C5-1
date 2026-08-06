# Individual Report — Role 2: Crossref Ingestion

## Scope

| Thành viên | MSSV |
|---|---|
| Nguyễn Huy Nghĩa | 2A202601943 |

Role 2 owns Crossref fetching, retry behavior, parsing and raw snapshot
preservation.

## Work and evidence

- Implemented/verified `src/ingestion/crossref.py` and the `PaperRecord` contract.
- Preserved `data/raw/crossref_response.json` before parsing and
  `data/raw/crossref_records.json` after parsing.
- Snapshot contains 24 records with 24 unique DOI-based `paper_id` values.
- Raw snapshot hashes and contract are documented in
  `report/role2_ingestion_handoff.md`.

## Technical understanding

The parser normalizes DOI, title, authors, dates and optional metadata. Records
that cannot be traced safely are dropped; missing optional fields remain
explicit so cleaning and quality checks can report them. Repair reloads this
snapshot instead of calling the live API again.

## Result

Raw response/records exist and are the authoritative repair source. Crossref
unit tests pass, including raw-before-parse and malformed-schema cases.
