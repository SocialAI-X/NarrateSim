"""Load experiment configurations from JSON files."""

import json
import os
from typing import Dict, Any

from .models import ExperimentConfig


def load_config(config_path: str) -> ExperimentConfig:
    """Load experiment config from a JSON file."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ExperimentConfig(**data)


def load_all_configs(config_dir: str = "configs") -> Dict[str, ExperimentConfig]:
    """Load all config files from a directory."""
    configs = {}
    for fname in sorted(os.listdir(config_dir)):
        if fname.endswith(".json"):
            path = os.path.join(config_dir, fname)
            config = load_config(path)
            configs[config.experiment_name] = config
    return configs


def get_results_dir(config: ExperimentConfig, base_dir: str = "results") -> str:
    """Get the output directory for an experiment."""
    study_dir = os.path.join(base_dir, config.study)
    exp_dir = os.path.join(study_dir, config.experiment_name)
    os.makedirs(exp_dir, exist_ok=True)
    return exp_dir
