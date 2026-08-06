# Individual Report — Role 1: Integration & Release QA

## Scope

| Thành viên | MSSV |
|---|---|
| Trần Quốc Hùng | 2A202601683 |

Role 1 owns the shared contract, release checks and end-to-end handoff.

## Work and evidence

- Frozen the raw/clean/eval/index/quality artifact contract in
  `report/role1_cp0_handoff.md`.
- Verified separate baseline, corrupted and repaired paths/collections.
- Reviewed the CP5/CP6 flow and final comparison at
  `data/reports/corruption_report.md`.
- Evidence: 24 raw/clean/repaired records, 12 evaluation samples, three Chroma
  collections and `6/6` unit tests passing.

## Technical understanding

Crossref records are saved before parsing, cleaned into a stable schema, embedded
into Chroma, evaluated, observed, corrupted and finally repaired from raw. The
same evaluation set is required across all states so metric differences are
caused by data state rather than different questions.

## Result

The release passes technical checks. Corrupted token-F1 is `0.7324`; repaired
token-F1 returns to `0.7518`, while repaired quality and freshness both pass.
