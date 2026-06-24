# Experiment results

Each subdirectory is one experiment run. File layout is identical across all studies:

```
<study>/<experiment_name>/
├── config.json            # Experiment configuration (mirror of configs/)
├── summary.json           # Stance metrics (shift, flip rate, negativity)
├── emotion_analysis.json  # Plutchik emotion metrics (ENI, EV, etc.)
└── results.json           # Full dialogue logs + BDI chain-of-thought
```

| Folder | Experiments | Paper section |
|--------|:-----------:|---------------|
| `study1_strategy_topic/` | 28 | Table 1 — strategy × topic |
| `study2_population_match/` | 14 | Study 2 — audience matching |
| `study3_intervention/` | 7 | Table 2 — interventions |
| `study4_robustness/` | 15 | Dose-response + network |
| `supplement_scale/` | 5 | Appendix — scale validation |

Aggregated metrics: [`index.json`](index.json)
