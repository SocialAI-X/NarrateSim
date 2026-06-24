"""Unified experiment runner with proper directory management.

Usage:
  python run_experiment.py configs/study1_baseline.json
  python run_experiment.py configs/           # run all configs in directory
  python run_experiment.py --study study1     # run all study1 configs
  python run_experiment.py --preset pilot     # run predefined experiment preset
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional

from src.config_loader import load_config, load_all_configs
from src.models import ExperimentConfig
from src.simulation import Simulation
from src.metrics import compute_full_metrics


def get_experiment_dir(config: ExperimentConfig, base_dir: str = "results") -> str:
    """Create a timestamped experiment directory.

    Structure: results/<study>/<experiment_name>_<timestamp>/
    """
    study_dir = os.path.join(base_dir, config.study)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    exp_dir = os.path.join(study_dir, f"{config.experiment_name}_{timestamp}")
    os.makedirs(exp_dir, exist_ok=True)
    return exp_dir


def get_experiment_dir_latest(config: ExperimentConfig, base_dir: str = "results") -> str:
    """Get or create a 'latest' experiment directory (for quick runs).

    Structure: results/<study>/<experiment_name>/
    """
    study_dir = os.path.join(base_dir, config.study)
    exp_dir = os.path.join(study_dir, config.experiment_name)
    os.makedirs(exp_dir, exist_ok=True)
    return exp_dir


async def run_single_experiment(
    config: ExperimentConfig,
    base_dir: str = "results",
    use_timestamp: bool = True,
) -> Dict:
    """Run a single experiment and save all outputs to experiment directory."""
    if use_timestamp:
        exp_dir = get_experiment_dir(config, base_dir)
    else:
        exp_dir = get_experiment_dir_latest(config, base_dir)

    plots_dir = os.path.join(exp_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    print(f"\n{'='*70}", flush=True)
    print(f"  Experiment: {config.experiment_name}", flush=True)
    print(f"  Study: {config.study}", flush=True)
    print(f"  Agents: {config.n_agents}, Rounds: {config.n_rounds}, Memory: {config.memory_window}", flush=True)
    print(f"  Model: {config.model_name}", flush=True)
    mal = config.get_malicious_config()
    if mal.enabled:
        print(f"  Malicious: strategy={mal.strategy}, coordination={mal.coordination}", flush=True)
    inv = config.get_intervention_config()
    if inv.enabled:
        print(f"  Intervention: type={inv.type}, start_round={inv.start_round}", flush=True)
    pop = config.get_population_config()
    print(f"  Population: {pop.name}", flush=True)
    print(f"  Output: {exp_dir}", flush=True)
    print(f"{'='*70}", flush=True)

    config_path = os.path.join(exp_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "experiment_name": config.experiment_name,
            "study": config.study,
            "n_agents": config.n_agents,
            "n_rounds": config.n_rounds,
            "network_m": config.network_m,
            "memory_window": config.memory_window,
            "random_seed": config.random_seed,
            "model_name": config.model_name,
            "max_concurrent": config.max_concurrent,
            "topic": config.topic,
            "malicious": config.malicious,
            "intervention": config.intervention,
            "population": config.population,
        }, f, ensure_ascii=False, indent=2)

    sim = Simulation(config=config)

    def progress(msg):
        print(f"  [{config.experiment_name}] {msg}", flush=True)

    results = await sim.run(progress_callback=progress)
    metrics = compute_full_metrics(results)

    result_file = os.path.join(exp_dir, "results.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    metrics_file = os.path.join(exp_dir, "metrics.json")
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    print(f"\n  Results: {result_file}", flush=True)
    print(f"  Metrics: {metrics_file}", flush=True)
    print(f"  Elapsed: {results['elapsed_seconds']:.1f}s", flush=True)

    st = metrics["stance_trajectory"]
    print(f"  Stance: {st['initial']['mean_stance']:.2f} -> {st['final']['mean_stance']:.2f}", flush=True)
    print(f"  Polarization (ER): {metrics['er_polarization_initial']:.3f} -> {metrics['er_polarization_final']:.3f}", flush=True)

    return {
        "config": config.experiment_name,
        "exp_dir": exp_dir,
        "results_file": result_file,
        "metrics_file": metrics_file,
        "metrics": metrics,
        "results": results,
    }


async def run_experiments(
    configs: List[ExperimentConfig],
    base_dir: str = "results",
    use_timestamp: bool = True,
):
    """Run multiple experiments sequentially."""
    all_results = []
    total_start = time.time()

    for i, config in enumerate(configs, 1):
        print(f"\n[{i}/{len(configs)}] Starting: {config.experiment_name}", flush=True)
        result = await run_single_experiment(config, base_dir, use_timestamp)
        all_results.append(result)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*70}", flush=True)
    print(f"  ALL EXPERIMENTS COMPLETE ({len(configs)} total)", flush=True)
    print(f"  Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)", flush=True)
    print(f"{'='*70}", flush=True)

    return all_results


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run_experiment.py <config.json | config_dir/ | --study STUDY | --preset NAME>")
        print("\nPresets: pilot (small-scale pre-experiment)")
        sys.exit(1)

    configs_to_run = []

    if sys.argv[1] == "--study":
        study_name = sys.argv[2]
        all_configs = load_all_configs("configs")
        configs_to_run = [c for c in all_configs.values() if c.study == study_name]
        if not configs_to_run:
            print(f"No configs found for study: {study_name}")
            sys.exit(1)
    elif sys.argv[1] == "--preset":
        print("Use run_pilot.py for preset experiments")
        sys.exit(1)
    elif os.path.isdir(sys.argv[1]):
        all_configs = load_all_configs(sys.argv[1])
        configs_to_run = list(all_configs.values())
    else:
        config = load_config(sys.argv[1])
        configs_to_run = [config]

    print(f"Experiments to run: {len(configs_to_run)}", flush=True)
    for c in configs_to_run:
        print(f"  - {c.experiment_name} ({c.study})", flush=True)

    asyncio.run(run_experiments(configs_to_run))


if __name__ == "__main__":
    main()
