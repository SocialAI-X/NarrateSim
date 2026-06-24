"""
Supplementary experiments for paper completion:
  1. Extra vaccine baselines (different seeds to find non-negative drift)
  2. Emotion analysis for all v3 experiments  
  3. Large-scale agent experiments (200, 500, 1000, 2000, 5000)

Usage:
  python run_supplement.py --task baselines   [--rpm 130]
  python run_supplement.py --task emotions    [--rpm 200]
  python run_supplement.py --task scale       [--rpm 130]
"""
import asyncio
import copy
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

from src.llm_client import LLMClient, _GlobalStats, _GlobalRateLimiter
from src.simulation import Simulation
from src.models import ExperimentConfig

V3_DIR = Path("results/full_study_20260521_v3")
SUPP_DIR = Path("results/supplement_20260522")

VACCINE_TOPIC = {
    "name": "vaccine", "name_cn": "疫苗强制接种",
    "description": (
        "Vaccines have proven effective at preventing disease outbreaks. "
        "Should governments require vaccination in certain situations to protect "
        "public health, or should vaccination remain entirely a personal choice?"
    ),
    "stance_negative": "Strongly oppose mandates / anti-vaccine",
    "stance_positive": "Strongly support mandates / pro-vaccine",
    "initial_stance_mean": 1.2, "initial_stance_std": 2.0,
    "initial_confidence_mean": 4.0, "initial_confidence_std": 2.0,
}

import numpy as np

def compute_metrics(results):
    init = np.array([a["initial_stance"] for a in results["agents_initial"]], dtype=float)
    final = np.array([a["final_stance"] for a in results["agents_final"]], dtype=float)
    n = len(final)
    changes = final - init[:n]
    opinionated = init[:n] != 0
    if np.sum(opinionated) > 0:
        flipped = ((init[:n] > 0) & (final < 0)) | ((init[:n] < 0) & (final > 0))
        flip_rate = float(np.sum(flipped & opinionated) / np.sum(opinionated))
    else:
        flip_rate = 0.0
    return {
        "mean_shift": float(np.mean(changes)),
        "neg_shift_rate": float(np.mean(changes < 0)),
        "flip_rate": flip_rate,
        "negativity_ratio": float(np.mean(final < 0)),
        "large_change_rate": float(np.mean(np.abs(changes) >= 2)),
        "final_mean": float(np.mean(final)),
        "final_std": float(np.std(final)),
        "init_mean": float(np.mean(init[:n])),
    }


# ============================================================
# TASK 1: Extra vaccine baselines
# ============================================================
async def run_baselines(rpm):
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)

    out = SUPP_DIR / "vaccine_baselines"
    out.mkdir(parents=True, exist_ok=True)

    seeds = [100, 200, 300, 400, 500]
    print(f"Running {len(seeds)} vaccine baselines with different seeds")
    print(f"Output: {out}")

    for seed in seeds:
        name = f"vaccine_baseline_seed{seed}"
        exp_dir = out / name
        summary_path = exp_dir / "summary.json"
        if summary_path.exists():
            d = json.loads(summary_path.read_text(encoding="utf-8"))
            print(f"  SKIP {name}: shift={d['mean_shift']:+.2f}")
            continue

        exp_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "experiment_name": name,
            "study": "baseline_rerun",
            "n_agents": 100,
            "n_rounds": 15,
            "network_m": 3,
            "memory_window": 10,
            "random_seed": seed,
            "model_name": "Pro/deepseek-ai/DeepSeek-V3.2",
            "max_concurrent": 20,
            "topic": copy.deepcopy(VACCINE_TOPIC),
            "malicious": {"enabled": False},
            "intervention": {"enabled": False},
            "population": {
                "name": "representative",
                "D1_mean": 5.5, "D1_std": 2.0, "D2_mean": 5.5, "D2_std": 2.0,
                "D3_mean": 5.5, "D3_std": 2.0, "D4_mean": 5.5, "D4_std": 2.0,
                "D5_mean": 5.5, "D5_std": 2.0,
            },
        }

        with open(exp_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        log_file = open(exp_dir / "run.log", "w", encoding="utf-8")
        def prog(msg, _lf=log_file, _name=name):
            ts = time.strftime('%H:%M:%S')
            line = f"[{ts}] {msg}"
            print(f"  [{_name}] {line}", flush=True)
            _lf.write(line + "\n")
            _lf.flush()

        t0 = time.time()
        config = ExperimentConfig(**cfg)
        sim = Simulation(config)
        results = await sim.run(progress_callback=prog)
        elapsed = time.time() - t0

        with open(exp_dir / "results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        metrics = compute_metrics(results)
        metrics["elapsed_s"] = round(elapsed, 1)
        metrics["name"] = name
        metrics["seed"] = seed
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

        log_file.close()
        gstats = _GlobalStats.get().summary()
        print(f"  {name} DONE shift={metrics['mean_shift']:+.3f} "
              f"neg={metrics['negativity_ratio']:.1%} flip={metrics['flip_rate']:.1%} "
              f"elapsed={elapsed:.0f}s | {gstats}\n", flush=True)

    print("\n=== ALL BASELINES SUMMARY ===")
    for seed in seeds:
        sp = out / f"vaccine_baseline_seed{seed}" / "summary.json"
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            marker = "<<< GOOD" if d["mean_shift"] >= -0.05 else ""
            print(f"  seed={seed:4d}: shift={d['mean_shift']:+.3f} "
                  f"final={d['final_mean']:.2f} neg={d['negativity_ratio']:.1%} {marker}")
    also_sp = V3_DIR / "main_vaccine_baseline" / "summary.json"
    if also_sp.exists():
        d = json.loads(also_sp.read_text(encoding="utf-8"))
        print(f"  seed=  42: shift={d['mean_shift']:+.3f} "
              f"final={d['final_mean']:.2f} neg={d['negativity_ratio']:.1%} (original v3)")


# ============================================================
# TASK 2: Emotion analysis for all v3 experiments
# ============================================================
async def run_emotions(rpm):
    from run_emotions_batch import process_experiment

    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)

    llm = LLMClient(model="Pro/deepseek-ai/DeepSeek-V3.2", max_concurrent=15)

    dirs = sorted(V3_DIR.iterdir())
    pending = []
    cached = 0
    for d in dirs:
        if not d.is_dir():
            continue
        rf = d / "results.json"
        ef = d / "emotion_analysis.json"
        if not rf.exists():
            continue
        if ef.exists():
            cached += 1
            continue
        pending.append(d)

    print(f"Emotion analysis for v3 experiments")
    print(f"  Cached: {cached}, Need analysis: {len(pending)}")
    est_mins = len(pending) * 130 // 10 // 15 * 90 // 60
    print(f"  Estimated: ~{est_mins} min\n")

    for idx, ep in enumerate(pending):
        name = ep.name
        print(f"  [{idx+1}/{len(pending)}] {name}", flush=True)
        t0 = time.time()
        try:
            metrics = await process_experiment(str(ep), llm)
            if metrics:
                elapsed = time.time() - t0
                gstats = _GlobalStats.get().summary()
                print(f"    DONE neg={metrics['negative_ratio']:.1%} "
                      f"anger={metrics['anger_ratio']:.1%} ({elapsed:.0f}s) | {gstats}\n",
                      flush=True)
        except Exception as e:
            print(f"    ERROR: {e}\n", flush=True)

    print("\nAll emotion analyses complete!")


# ============================================================
# TASK 3: Large-scale experiments
# ============================================================
async def run_scale(rpm):
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)

    out = SUPP_DIR / "scale_experiments"
    out.mkdir(parents=True, exist_ok=True)

    agent_counts = [200, 500, 1000, 2000, 5000]
    strategy = "pseudo_rational"

    print(f"Large-scale experiments: {agent_counts} agents")
    print(f"Strategy: {strategy}, hub placement, vaccine topic")
    print(f"Output: {out}\n")

    for n_agents in agent_counts:
        n_rounds = 15 if n_agents <= 1000 else 10
        network_m = 3 if n_agents <= 500 else 4
        n_mal = max(3, n_agents // 50)
        max_conc = min(30, n_agents // 5)

        name = f"scale_{n_agents}_agents"
        exp_dir = out / name
        summary_path = exp_dir / "summary.json"
        if summary_path.exists():
            d = json.loads(summary_path.read_text(encoding="utf-8"))
            print(f"  SKIP {name}: shift={d['mean_shift']:+.2f}")
            continue

        exp_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "experiment_name": name,
            "study": "scale",
            "n_agents": n_agents,
            "n_rounds": n_rounds,
            "network_m": network_m,
            "memory_window": 10,
            "random_seed": 42,
            "model_name": "Pro/deepseek-ai/DeepSeek-V3.2",
            "max_concurrent": max_conc,
            "topic": copy.deepcopy(VACCINE_TOPIC),
            "malicious": {
                "enabled": True, "n_agents": n_mal, "strategy": strategy,
                "coordination": "independent", "placement": "hub",
            },
            "intervention": {"enabled": False},
            "population": {
                "name": "representative",
                "D1_mean": 5.5, "D1_std": 2.0, "D2_mean": 5.5, "D2_std": 2.0,
                "D3_mean": 5.5, "D3_std": 2.0, "D4_mean": 5.5, "D4_std": 2.0,
                "D5_mean": 5.5, "D5_std": 2.0,
            },
        }

        with open(exp_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        log_file = open(exp_dir / "run.log", "w", encoding="utf-8")
        def prog(msg, _lf=log_file, _name=name):
            ts = time.strftime('%H:%M:%S')
            line = f"[{ts}] {msg}"
            print(f"  [{_name}] {line}", flush=True)
            _lf.write(line + "\n")
            _lf.flush()

        t0 = time.time()
        print(f"\n{'='*60}")
        print(f"  {name}: n_agents={n_agents}, n_mal={n_mal}, n_rounds={n_rounds}, "
              f"network_m={network_m}, max_conc={max_conc}")
        print(f"{'='*60}", flush=True)

        try:
            config = ExperimentConfig(**cfg)
            sim = Simulation(config)
            prog(f"Malicious IDs: {sim.malicious_ids[:10]}{'...' if len(sim.malicious_ids) > 10 else ''}")
            prog(f"Network: {n_agents} nodes, {sim.graph.number_of_edges()} edges, "
                 f"avg_degree={2*sim.graph.number_of_edges()/n_agents:.1f}")

            results = await sim.run(progress_callback=prog)
            elapsed = time.time() - t0

            with open(exp_dir / "results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            metrics = compute_metrics(results)
            metrics["elapsed_s"] = round(elapsed, 1)
            metrics["name"] = name
            metrics["n_agents"] = n_agents
            metrics["n_malicious"] = n_mal
            metrics["n_rounds"] = n_rounds
            metrics["network_edges"] = sim.graph.number_of_edges()
            metrics["avg_degree"] = round(2 * sim.graph.number_of_edges() / n_agents, 2)
            metrics["llm_calls"] = sim.llm._success_count
            metrics["llm_errors"] = sim.llm._error_count

            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)

            log_file.close()
            gstats = _GlobalStats.get().summary()
            print(f"\n  {name} DONE: shift={metrics['mean_shift']:+.3f} "
                  f"neg={metrics['negativity_ratio']:.1%} flip={metrics['flip_rate']:.1%} "
                  f"elapsed={elapsed/60:.1f}min calls={metrics['llm_calls']} | {gstats}\n",
                  flush=True)

        except Exception as e:
            log_file.close()
            print(f"\n  {name} FAILED: {e}\n", flush=True)

    print("\n=== SCALE EXPERIMENT SUMMARY ===")
    print(f"{'Agents':>7} {'Mal':>4} {'Rounds':>6} {'Edges':>7} {'AvgDeg':>7} "
          f"{'Shift':>7} {'NegRatio':>9} {'FlipRate':>9} {'Elapsed':>9} {'Calls':>7}")
    for n_agents in agent_counts:
        sp = out / f"scale_{n_agents}_agents" / "summary.json"
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            print(f"{d.get('n_agents', n_agents):>7} {d.get('n_malicious', '?'):>4} "
                  f"{d.get('n_rounds', '?'):>6} {d.get('network_edges', '?'):>7} "
                  f"{d.get('avg_degree', '?'):>7} {d['mean_shift']:>+7.3f} "
                  f"{d['negativity_ratio']:>8.1%} {d['flip_rate']:>8.1%} "
                  f"{d.get('elapsed_s', 0)/60:>8.1f}m {d.get('llm_calls', '?'):>7}")


# ============================================================
# TASK: Scale baselines (no malicious, for comparison)
# ============================================================
async def run_scale_baselines(rpm):
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)

    out = SUPP_DIR / "scale_experiments"
    out.mkdir(parents=True, exist_ok=True)

    agent_counts = [200, 500, 1000, 2000, 5000]

    print(f"Large-scale BASELINE experiments: {agent_counts} agents")
    print(f"No malicious agents, vaccine topic")
    print(f"Output: {out}\n")

    for n_agents in agent_counts:
        n_rounds = 15 if n_agents <= 1000 else 10
        network_m = 3 if n_agents <= 500 else 4
        max_conc = min(30, n_agents // 5)

        name = f"scale_{n_agents}_baseline"
        exp_dir = out / name
        summary_path = exp_dir / "summary.json"
        if summary_path.exists():
            d = json.loads(summary_path.read_text(encoding="utf-8"))
            print(f"  SKIP {name}: shift={d['mean_shift']:+.2f}")
            continue

        exp_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "experiment_name": name,
            "study": "scale_baseline",
            "n_agents": n_agents,
            "n_rounds": n_rounds,
            "network_m": network_m,
            "memory_window": 10,
            "random_seed": 42,
            "model_name": "Pro/deepseek-ai/DeepSeek-V3.2",
            "max_concurrent": max_conc,
            "topic": copy.deepcopy(VACCINE_TOPIC),
            "malicious": {"enabled": False},
            "intervention": {"enabled": False},
            "population": {
                "name": "representative",
                "D1_mean": 5.5, "D1_std": 2.0, "D2_mean": 5.5, "D2_std": 2.0,
                "D3_mean": 5.5, "D3_std": 2.0, "D4_mean": 5.5, "D4_std": 2.0,
                "D5_mean": 5.5, "D5_std": 2.0,
            },
        }

        with open(exp_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

        log_file = open(exp_dir / "run.log", "w", encoding="utf-8")
        def prog(msg, _lf=log_file, _name=name):
            ts = time.strftime('%H:%M:%S')
            line = f"[{ts}] {msg}"
            print(f"  [{_name}] {line}", flush=True)
            _lf.write(line + "\n")
            _lf.flush()

        t0 = time.time()
        print(f"\n  {name}: n_agents={n_agents}, n_rounds={n_rounds}", flush=True)

        try:
            config = ExperimentConfig(**cfg)
            sim = Simulation(config)
            results = await sim.run(progress_callback=prog)
            elapsed = time.time() - t0

            with open(exp_dir / "results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            metrics = compute_metrics(results)
            metrics["elapsed_s"] = round(elapsed, 1)
            metrics["name"] = name
            metrics["n_agents"] = n_agents
            metrics["n_rounds"] = n_rounds
            metrics["network_edges"] = sim.graph.number_of_edges()
            metrics["avg_degree"] = round(2 * sim.graph.number_of_edges() / n_agents, 2)
            metrics["llm_calls"] = sim.llm._success_count

            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)

            log_file.close()
            print(f"  {name} DONE: shift={metrics['mean_shift']:+.3f} "
                  f"elapsed={elapsed/60:.1f}min\n", flush=True)
        except Exception as e:
            log_file.close()
            print(f"  {name} FAILED: {e}\n", flush=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True,
                        choices=["baselines", "emotions", "scale", "scale_baselines"],
                        help="Which supplementary task to run")
    parser.add_argument("--rpm", type=int, default=200,
                        help="Global RPM limit (default 200)")
    args = parser.parse_args()

    if args.task == "baselines":
        asyncio.run(run_baselines(args.rpm))
    elif args.task == "emotions":
        asyncio.run(run_emotions(args.rpm))
    elif args.task == "scale":
        asyncio.run(run_scale(args.rpm))
    elif args.task == "scale_baselines":
        asyncio.run(run_scale_baselines(args.rpm))
