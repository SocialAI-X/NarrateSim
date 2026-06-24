"""
Master experiment runner for all four experiment groups.
Generates configs on-the-fly and runs with controlled concurrency.
"""
import asyncio
import json
import os
import sys
import time
import copy
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config_loader import load_config
from src.simulation import Simulation
from src.metrics import compute_full_metrics

# ============================================================
# CONSTANTS
# ============================================================
STUDY_ID = "20260521_v3"   # v3: RNG fix, hub placement, replaced gaslighting/emotional_flooding with authority_manipulation/social_proof
OUTPUT_ROOT = Path(f"results/full_study_{STUDY_ID}")
MAX_CONCURRENT_SIMS = 5

TOPICS = {
    "vaccine": {
        "name": "vaccine", "name_cn": "疫苗强制接种",
        "description": "Vaccines have proven effective at preventing disease outbreaks. Should governments require vaccination in certain situations to protect public health, or should vaccination remain entirely a personal choice?",
        "stance_negative": "Strongly oppose mandates / anti-vaccine",
        "stance_positive": "Strongly support mandates / pro-vaccine",
        "initial_stance_mean": 1.2, "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0, "initial_confidence_std": 2.0,
    },
    "climate": {
        "name": "climate", "name_cn": "气候变化与能源政策",
        "description": "Climate change poses serious risks according to scientific consensus. Should governments prioritize green energy transition and carbon limits, or focus on economic growth and energy independence?",
        "stance_negative": "Prioritize economy / skeptical of climate urgency",
        "stance_positive": "Aggressive climate action / green transition now",
        "initial_stance_mean": 1.2, "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0, "initial_confidence_std": 2.0,
    },
    "immigration": {
        "name": "immigration", "name_cn": "移民与边境政策",
        "description": "Immigration has historically contributed to economic growth and cultural enrichment in most countries. Should countries maintain open immigration policies to sustain growth and diversity, or implement stricter controls citing security and labor market concerns?",
        "stance_negative": "Strongly restrict immigration / close borders",
        "stance_positive": "Strongly support open immigration / welcome refugees",
        "initial_stance_mean": 1.2, "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0, "initial_confidence_std": 2.0,
    },
    "gmo_food": {
        "name": "gmo_food", "name_cn": "转基因食品安全",
        "description": "Major scientific organizations have concluded that approved GM foods are safe for consumption. Should genetically modified foods be more widely adopted to address food security, or should they face stricter regulation due to public concerns about long-term effects?",
        "stance_negative": "Strongly oppose GMO / ban or heavily regulate",
        "stance_positive": "Support GMO adoption / safe and necessary",
        "initial_stance_mean": 1.2, "initial_stance_std": 2.0,
        "initial_confidence_mean": 4.0, "initial_confidence_std": 2.0,
    },
}

STRATEGIES = ["pseudo_rational", "victim_narrative", "fear_appeal",
              "conspiracy_theory", "authority_manipulation", "social_proof"]

MAL_COUNTS_DOSE = [3, 5, 10, 20]  # for dose-response experiment only

# Population presets for strategy-population experiment
POPULATIONS = {
    "high_trust": {"name": "high_trust", "D1_mean": 8.0, "D1_std": 1.0,
                   "D2_mean": 5.5, "D2_std": 2.0, "D3_mean": 5.5, "D3_std": 2.0,
                   "D4_mean": 7.0, "D4_std": 1.5, "D5_mean": 5.5, "D5_std": 2.0},
    "low_trust": {"name": "low_trust", "D1_mean": 3.0, "D1_std": 1.0,
                  "D2_mean": 5.5, "D2_std": 2.0, "D3_mean": 5.5, "D3_std": 2.0,
                  "D4_mean": 4.0, "D4_std": 1.5, "D5_mean": 5.5, "D5_std": 2.0},
    "high_analytical": {"name": "high_analytical", "D1_mean": 5.5, "D1_std": 2.0,
                        "D2_mean": 5.5, "D2_std": 2.0, "D3_mean": 5.5, "D3_std": 2.0,
                        "D4_mean": 5.5, "D4_std": 2.0, "D5_mean": 8.0, "D5_std": 1.0},
    "low_analytical": {"name": "low_analytical", "D1_mean": 5.5, "D1_std": 2.0,
                       "D2_mean": 5.5, "D2_std": 2.0, "D3_mean": 5.5, "D3_std": 2.0,
                       "D4_mean": 5.5, "D4_std": 2.0, "D5_mean": 3.0, "D5_std": 1.0},
    "high_empathy": {"name": "high_empathy", "D1_mean": 5.5, "D1_std": 2.0,
                     "D2_mean": 8.5, "D2_std": 1.0, "D3_mean": 5.5, "D3_std": 2.0,
                     "D4_mean": 5.5, "D4_std": 2.0, "D5_mean": 5.5, "D5_std": 2.0},
    "authoritarian": {"name": "authoritarian", "D1_mean": 5.5, "D1_std": 2.0,
                      "D2_mean": 5.5, "D2_std": 2.0, "D3_mean": 8.5, "D3_std": 1.0,
                      "D4_mean": 7.0, "D4_std": 1.5, "D5_mean": 4.0, "D5_std": 1.5},
}

# Intervention types
INTERVENTIONS = {
    "inoculation_pre": {"type": "inoculation", "start_round": 0, "frequency": 1},
    "fact_check_post": {"type": "fact_check", "start_round": 5, "frequency": 3},
    "metacognitive": {"type": "metacognitive", "start_round": 0, "frequency": 1},
    "community_report": {"type": "community_report", "start_round": 5, "frequency": 3},
    "sentiment_transparency": {"type": "sentiment_transparency", "start_round": 3, "frequency": 3},
    "inoculation_late": {"type": "inoculation", "start_round": 5, "frequency": 1},
}


def make_config(name, study, topic_key, malicious=None, intervention=None, population=None,
                n_agents=100, n_rounds=15, network_m=3, seed=42):
    """Generate an experiment config dict."""
    topic = copy.deepcopy(TOPICS[topic_key])
    cfg = {
        "experiment_name": name,
        "study": study,
        "n_agents": n_agents,
        "n_rounds": n_rounds,
        "network_m": network_m,
        "memory_window": 10,
        "random_seed": seed,
        "model_name": "Pro/deepseek-ai/DeepSeek-V3.2",
        "max_concurrent": 20,
        "topic": topic,
        "malicious": malicious or {"enabled": False},
        "intervention": intervention or {"enabled": False},
        "population": population or {"name": "representative",
                                      "D1_mean": 5.5, "D1_std": 2.0,
                                      "D2_mean": 5.5, "D2_std": 2.0,
                                      "D3_mean": 5.5, "D3_std": 2.0,
                                      "D4_mean": 5.5, "D4_std": 2.0,
                                      "D5_mean": 5.5, "D5_std": 2.0},
    }
    return cfg


# ============================================================
# EXPERIMENT DEFINITIONS
# ============================================================

def generate_all_experiments():
    """Generate all experiment configs organized by group."""
    experiments = {}

    # ---- GROUP 1: Main experiment (6 strategies × 4 topics, n_mal=3) ----
    for topic in TOPICS:
        name = f"main_{topic}_baseline"
        experiments[name] = make_config(name, "main", topic)

    for topic in TOPICS:
        for strat in STRATEGIES:
            name = f"main_{topic}_{strat}"
            mal = {"enabled": True, "n_agents": 3, "strategy": strat,
                   "coordination": "independent", "placement": "hub"}
            experiments[name] = make_config(name, "main", topic, malicious=mal)

    # ---- GROUP 1b: Dose-response (vaccine × 2 strategies × 4 counts) ----
    for strat in ["victim_narrative", "pseudo_rational"]:
        for n_mal in MAL_COUNTS_DOSE:
            name = f"dose_vaccine_{strat}_n{n_mal}"
            mal = {"enabled": True, "n_agents": n_mal, "strategy": strat,
                   "coordination": "independent", "placement": "hub"}
            experiments[name] = make_config(name, "dose_response", "vaccine", malicious=mal)

    # ---- GROUP 2: Strategy-Population (vaccine topic, 3 mal agents) ----
    # 3 strategies × 6 populations = 18, but we pick 8 meaningful combos
    strat_pop_combos = [
        ("victim_narrative", "high_empathy"),        # emotional strategy vs emotional people
        ("victim_narrative", "high_analytical"),      # emotional strategy vs analytical people
        ("pseudo_rational", "high_trust"),            # rational deceit vs trusting people
        ("pseudo_rational", "low_trust"),             # rational deceit vs skeptical people
        ("conspiracy_theory", "high_analytical"),     # conspiracy vs analytical thinkers
        ("conspiracy_theory", "low_analytical"),      # conspiracy vs intuitive thinkers
        ("fear_appeal", "authoritarian"),             # fear vs order-oriented people
        ("authority_manipulation", "high_trust"),     # fake authority vs trusting people
    ]
    # Baselines per population
    for pop_name in set(p for _, p in strat_pop_combos):
        name = f"pop_{pop_name}_baseline"
        experiments[name] = make_config(name, "strategy_population", "vaccine",
                                        population=POPULATIONS[pop_name])
    for strat, pop_name in strat_pop_combos:
        name = f"pop_{pop_name}_{strat}"
        mal = {"enabled": True, "n_agents": 3, "strategy": strat,
               "coordination": "independent", "placement": "hub"}
        experiments[name] = make_config(name, "strategy_population", "vaccine",
                                        malicious=mal, population=POPULATIONS[pop_name])

    # ---- GROUP 3: Intervention (vaccine topic, victim_narrative, 3 mal) ----
    # Baseline with attack but no intervention
    mal_base = {"enabled": True, "n_agents": 3, "strategy": "victim_narrative",
                "coordination": "independent", "placement": "hub"}
    name = "intv_no_intervention"
    experiments[name] = make_config(name, "intervention", "vaccine", malicious=mal_base)

    for intv_name, intv_params in INTERVENTIONS.items():
        name = f"intv_{intv_name}"
        intv = {"enabled": True, **intv_params}
        experiments[name] = make_config(name, "intervention", "vaccine",
                                        malicious=copy.deepcopy(mal_base), intervention=intv)

    # ---- GROUP 4: Network structure (vaccine, victim_narrative, 3 mal) ----
    # Vary network density and malicious placement
    network_experiments = [
        ("net_sparse_hub", 2, "hub"),       # sparse network, hub placement
        ("net_dense_hub", 5, "hub"),         # dense network, hub placement
        ("net_default_hub", 3, "hub"),       # default (control — all hub)
        ("net_default_random", 3, "random"), # default density, random placement
        ("net_dense_random", 5, "random"),   # dense network, random placement
        ("net_sparse_random", 2, "random"),  # sparse network, random placement
    ]
    for net_name, m, placement in network_experiments:
        mal = {"enabled": True, "n_agents": 3, "strategy": "victim_narrative",
               "coordination": "independent", "placement": placement}
        experiments[net_name] = make_config(net_name, "network", "vaccine",
                                            malicious=mal, network_m=m)
    # Network baseline (no malicious, default m=3)
    experiments["net_baseline"] = make_config("net_baseline", "network", "vaccine")

    return experiments


# ============================================================
# METRICS
# ============================================================

import numpy as np

def compute_study_metrics(results):
    """Compute the 5 key metrics from results."""
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
# RUNNER
# ============================================================

semaphore = None
completed = 0
total_experiments = 0
results_cache = {}


async def run_one(name, config_dict, output_dir):
    """Run a single experiment with semaphore-controlled concurrency."""
    global completed
    # Skip if already completed
    summary_path = output_dir / name / "summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, encoding="utf-8") as f:
                cached = json.load(f)
            if "mean_shift" in cached:
                completed += 1
                print(f"  SKIP [{name[:35]:35s}] already done ({completed}/{total_experiments})", flush=True)
                cached["name"] = name
                cached["study"] = config_dict.get("study", "")
                results_cache[name] = cached
                return cached
        except Exception:
            pass

    async with semaphore:
        from src.models import ExperimentConfig
        config = ExperimentConfig(**config_dict)
        config.experiment_name = name

        out = output_dir / name
        out.mkdir(parents=True, exist_ok=True)

        with open(out / "config.json", "w", encoding="utf-8") as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)

        label = f"[{name[:35]:35s}]"
        log_path = out / "run.log"
        log_file = open(log_path, "w", encoding="utf-8")

        def prog(msg):
            ts = time.strftime('%H:%M:%S')
            line = f"[{ts}] {msg}"
            print(f"  {label} {line}", flush=True)
            log_file.write(line + "\n")
            log_file.flush()

        start = time.time()
        try:
            prog(f"START config: n_agents={config.n_agents} n_rounds={config.n_rounds} "
                 f"mal={config_dict.get('malicious', {}).get('strategy', 'none')} "
                 f"placement={config_dict.get('malicious', {}).get('placement', 'n/a')}")

            sim = Simulation(config)
            if sim.malicious_ids:
                prog(f"Malicious IDs: {sim.malicious_ids}")

            results = await sim.run(progress_callback=prog)
            elapsed = time.time() - start

            with open(out / "results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            metrics = compute_study_metrics(results)
            metrics["elapsed_s"] = round(elapsed, 1)
            metrics["name"] = name
            metrics["study"] = config_dict.get("study", "")

            with open(out / "summary.json", "w", encoding="utf-8") as f:
                json.dump(metrics, f, ensure_ascii=False, indent=2)

            completed += 1
            from src.llm_client import _GlobalStats
            gstats = _GlobalStats.get().summary()
            done_msg = (f"DONE ({completed}/{total_experiments}) "
                        f"shift={metrics['mean_shift']:+.2f} flip={metrics['flip_rate']:.1%} "
                        f"neg={metrics['negativity_ratio']:.1%} elapsed={elapsed:.0f}s | {gstats}")
            prog(done_msg)

            results_cache[name] = metrics
            return metrics

        except Exception as e:
            completed += 1
            err_msg = f"FAILED ({completed}/{total_experiments}): {e}"
            prog(err_msg)
            return {"name": name, "error": str(e)}
        finally:
            log_file.close()


async def run_group(group_name, experiments, output_dir):
    """Run a group of experiments."""
    group_exps = {k: v for k, v in experiments.items() if v.get("study") == group_name}
    if not group_exps:
        return

    print(f"\n{'='*80}")
    print(f"  GROUP: {group_name} ({len(group_exps)} experiments)")
    print(f"{'='*80}")

    tasks = [run_one(name, cfg, output_dir) for name, cfg in group_exps.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Print group summary
    print(f"\n  --- {group_name} SUMMARY ---")
    ok = [r for r in results if isinstance(r, dict) and "error" not in r]
    for r in sorted(ok, key=lambda x: x.get("mean_shift", 0)):
        print(f"    {r['name']:<40s} shift={r['mean_shift']:+.2f} "
              f"flip={r['flip_rate']:.1%} neg={r['negativity_ratio']:.1%}")

    return ok


GROUP_ORDER = ["main", "dose_response", "strategy_population", "intervention", "network"]


async def run_group_sequential(group_name, experiments, output_dir):
    """Run one experiment group with controlled concurrency, wait for completion."""
    group_exps = {k: v for k, v in experiments.items() if v.get("study") == group_name}
    if not group_exps:
        return []

    print(f"\n{'='*80}")
    print(f"  GROUP: {group_name} ({len(group_exps)} experiments)")
    print(f"{'='*80}", flush=True)

    group_start = time.time()
    tasks = [run_one(name, cfg, output_dir) for name, cfg in group_exps.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    group_elapsed = time.time() - group_start

    ok = [r for r in results if isinstance(r, dict) and "error" not in r]
    failed = [r for r in results if isinstance(r, dict) and "error" in r]
    errors = [r for r in results if isinstance(r, Exception)]

    from src.llm_client import _GlobalStats
    gstats = _GlobalStats.get().summary()
    print(f"\n  --- {group_name} DONE: {len(ok)} ok, {len(failed)} fail, {len(errors)} err "
          f"({group_elapsed/60:.1f} min) | {gstats} ---")
    print(f"  {'Name':<42s} {'Shift':>7} {'NegRate':>8} {'Flip':>7} {'NegRatio':>9} {'LrgChg':>7}")
    for r in sorted(ok, key=lambda x: x.get("mean_shift", 0)):
        print(f"  {r['name']:<42s} {r['mean_shift']:>+7.2f} {r['neg_shift_rate']:>7.1%} "
              f"{r['flip_rate']:>6.1%} {r['negativity_ratio']:>8.1%} {r['large_change_rate']:>6.1%}")

    if failed:
        for r in failed:
            print(f"  FAILED: {r['name']} - {r.get('error', '?')[:80]}")
    if errors:
        for e in errors:
            print(f"  ERROR: {e}")

    return ok


async def main(rpm: int = 250):
    global semaphore, total_experiments

    # Reset global singletons and initialise with chosen RPM
    from src.llm_client import _GlobalStats, _GlobalRateLimiter
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SIMS)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    experiments = generate_all_experiments()
    total_experiments = len(experiments)

    print(f"Generated {total_experiments} experiments")
    print(f"Output: {OUTPUT_ROOT}")
    print(f"Concurrency: {MAX_CONCURRENT_SIMS} parallel sims x 20 LLM concurrent | global RPM={rpm}")

    groups = {}
    for name, cfg in experiments.items():
        g = cfg.get("study", "other")
        groups.setdefault(g, []).append(name)
    for g, names in groups.items():
        print(f"  {g}: {len(names)} experiments")

    manifest = {name: {k: v for k, v in cfg.items() if k != "topic"}
                for name, cfg in experiments.items()}
    with open(OUTPUT_ROOT / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    global_start = time.time()
    all_ok = []

    # Progress monitor
    async def progress_monitor():
        from src.llm_client import _GlobalStats
        while completed < total_experiments:
            await asyncio.sleep(90)
            elapsed = time.time() - global_start
            gstats = _GlobalStats.get().summary()
            if completed > 2:
                eta = elapsed / completed * (total_experiments - completed)
                print(f"  >> PROGRESS: {completed}/{total_experiments} done, "
                      f"elapsed {elapsed/60:.0f}min, ETA ~{eta/60:.0f}min | {gstats}", flush=True)
            else:
                print(f"  >> PROGRESS: {completed}/{total_experiments} done, "
                      f"elapsed {elapsed/60:.0f}min | {gstats}", flush=True)

    monitor_task = asyncio.create_task(progress_monitor())

    for group_name in GROUP_ORDER:
        group_ok = await run_group_sequential(group_name, experiments, OUTPUT_ROOT)
        all_ok.extend(group_ok)

        elapsed_so_far = time.time() - global_start
        done_so_far = len(all_ok)
        remaining = total_experiments - completed
        if done_so_far > 0:
            eta = elapsed_so_far / done_so_far * remaining
            print(f"\n  >> After {group_name}: {done_so_far} done, "
                  f"{elapsed_so_far/60:.1f}min elapsed, ~{eta/60:.0f}min remaining\n", flush=True)

    monitor_task.cancel()
    total_elapsed = time.time() - global_start

    print(f"\n{'='*80}")
    print(f"  FINAL: {len(all_ok)} succeeded out of {total_experiments}")
    print(f"  Total time: {total_elapsed/60:.1f} min ({total_elapsed/3600:.1f} hours)")
    if all_ok:
        print(f"  Avg per experiment: {total_elapsed/len(all_ok):.0f}s")
    print(f"{'='*80}")

    with open(OUTPUT_ROOT / "all_summaries.json", "w", encoding="utf-8") as f:
        json.dump(all_ok, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", nargs="*", default=None,
                        help="Which groups to run. E.g. --groups main dose_response")
    parser.add_argument("--rpm", type=int, default=250,
                        help="Global RPM limit for this process (default 250)")
    args = parser.parse_args()

    if args.groups:
        GROUP_ORDER[:] = [g for g in GROUP_ORDER if g in args.groups]

    asyncio.run(main(rpm=args.rpm))
