# Experiment results

Each subdirectory is one experiment run. File layout is identical across all studies:

```
<study>/<experiment_name>/
├── config.json            # Experiment configuration (mirror of configs/)
├── summary.json           # Stance metrics (shift, flip rate, negativity)
├── emotion_analysis.json  # Plutchik emotion metrics (ENI, EV, etc.)
└── results.json           # Full dialogue logs + BDI chain-of-thought
```

| Folder | Runs | Where it appears |
|--------|:----:|------------------|
| `study1_strategy_topic/` | 28 | Paper Table 1 (RQ1): 6 strategies + no attack x 4 topics |
| `study3_intervention/` | 7 | Paper Table 2 (RQ2): interventions vs. Victim Narrative |
| `study4_robustness/` | 15 | Paper Fig. 4 (`net_*`, attacker placement); project page (`dose_*`, attacker count) |
| `study2_population_match/` | 14 | Project page: audience composition |
| `supplement_scale/` | 5 | Project page: N = 200 ... 5,000 |

Recompute the paper tables from these files (no API key needed): `python run.py tables`.

Aggregated metrics: [`index.json`](index.json)
