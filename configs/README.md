# Experiment configs

Each JSON file defines one reproducible experiment. Folder names match `results/` and the `study` field inside each config.

| Folder | Study | Experiments | Description |
|--------|-------|:-----------:|-------------|
| `study1_strategy_topic/` | Study 1 | 28 | 4 topics × 6 strategies + baselines |
| `study2_population_match/` | Study 2 | 14 | Audience trait × strategy matching |
| `study3_intervention/` | Study 3 | 7 | Defense interventions vs. Victim Narrative |
| `study4_robustness/` | Study 4 | 15 | Dose-response + network topology |
| `supplement_scale/` | Scale | 5 | N = 200, 500, 1k, 2k, 5k agents |

```bash
# Run one experiment
python run.py config configs/study1_strategy_topic/vaccine_baseline.json

# Run an entire study
python run.py study study1_strategy_topic

# Regenerate all configs from definitions
python run.py export-configs
```
