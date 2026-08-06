# Individual Report — Role 5: Evaluation

## Scope

| Thành viên | MSSV |
|---|---|
| Nguyễn Thế Anh | 2A202601791 |

Role 5 owns the frozen evaluation set, answer artifacts and metric comparison.

## Work and evidence

- `data/eval/test_set.json` contains 12 questions with ground-truth document IDs.
- Baseline, corrupted and repaired evaluation use the same set and evaluator.
- Metrics and answers are stored separately in `data/results/` for all states.

## Results

| Metric | Baseline | Corrupted | Repaired |
|---|---:|---:|---:|
| Retrieval hit rate | 1.0000 | 1.0000 | 1.0000 |
| Mean token-F1 | 0.7518 | 0.7324 | 0.7518 |
| Judge accuracy | 0.6667 | 0.6667 | 0.6667 |
| Mean judge score | 3.7500 | 3.7500 | 3.7500 |

The unchanged judge metrics are reported transparently. The measurable agent
impact in this run is the token-F1 reduction and subsequent recovery.
