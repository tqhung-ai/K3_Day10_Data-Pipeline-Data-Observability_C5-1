# Corruption and Repair Comparison

## Metrics
| Metric | Baseline | Corrupted | Repaired | Corrupted-Baseline | Repaired-Corrupted | Repaired-Baseline |
|---|---:|---:|---:|---:|---:|---:|
| judge_accuracy | 0.6000 | 0.5600 | 0.6000 | -0.0400 | 0.0400 | 0.0000 |
| mean_judge_score | 3.4000 | 3.2400 | 3.4000 | -0.1600 | 0.1600 | 0.0000 |
| mean_token_f1 | 0.6867 | 0.6277 | 0.6867 | -0.0590 | 0.0590 | 0.0000 |
| retrieval_hit_rate | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| samples | 25.0000 | 25.0000 | 25.0000 | 0.0000 | 0.0000 | 0.0000 |

## Quality and freshness

- Corrupted quality: **FAIL**
- Repaired quality: **PASS**
- Corrupted freshness: **FAIL**
- Repaired freshness: **PASS**

## Observability details
- Corrupted duplicate paper IDs: 1
- Corrupted stale rows: 1
- Repaired duplicate paper IDs: 0
- Repaired stale rows: 0
