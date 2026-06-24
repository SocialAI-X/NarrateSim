"""Async experiment runner for NarrateSim."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from src.experiment_defs import (
    GROUP_ORDER,
    RESULTS_ROOT,
    experiment_result_dir,
    generate_all_experiments,
    generate_scale_experiments,
)
from src.models import ExperimentConfig
from src.simulation import Simulation


MAX_CONCURRENT_SIMS = 5


def compute_study_metrics(results: dict) -> dict:
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


class ExperimentRunner:
    def __init__(self, rpm: int = 250, max_concurrent: int = MAX_CONCURRENT_SIMS):
        from src.llm_client import _GlobalRateLimiter, _GlobalStats

        _GlobalStats.reset()
        _GlobalRateLimiter.reset()
        _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.completed = 0
        self.total = 0
        self.cache: Dict[str, dict] = {}

    async def run_one(self, name: str, config_dict: dict) -> dict:
        study = config_dict["study"]
        out = experiment_result_dir(study, name)
        summary_path = out / "summary.json"
        if summary_path.exists():
            try:
                cached = json.loads(summary_path.read_text(encoding="utf-8"))
                if "mean_shift" in cached:
                    self.completed += 1
                    print(
                        f"  SKIP [{name[:35]:35s}] done ({self.completed}/{self.total})",
                        flush=True,
                    )
                    cached["name"] = name
                    cached["study"] = study
                    self.cache[name] = cached
                    return cached
            except Exception:
                pass

        async with self.semaphore:
            config = ExperimentConfig(**config_dict)
            out.mkdir(parents=True, exist_ok=True)
            out.joinpath("config.json").write_text(
                json.dumps(config_dict, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            label = f"[{name[:35]:35s}]"
            log_file = open(out / "run.log", "w", encoding="utf-8")

            def prog(msg: str):
                ts = time.strftime("%H:%M:%S")
                line = f"[{ts}] {msg}"
                print(f"  {label} {line}", flush=True)
                log_file.write(line + "\n")
                log_file.flush()

            start = time.time()
            try:
                prog(f"START n_agents={config.n_agents} rounds={config.n_rounds}")
                sim = Simulation(config)
                results = await sim.run(progress_callback=prog)
                elapsed = time.time() - start

                out.joinpath("results.json").write_text(
                    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                metrics = compute_study_metrics(results)
                metrics.update(
                    {
                        "elapsed_s": round(elapsed, 1),
                        "name": name,
                        "study": study,
                    }
                )
                summary_path.write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                self.completed += 1
                self.cache[name] = metrics
                prog(f"DONE shift={metrics['mean_shift']:+.2f} flip={metrics['flip_rate']:.1%}")
                return metrics
            except Exception as e:
                self.completed += 1
                prog(f"FAILED: {e}")
                return {"name": name, "error": str(e)}
            finally:
                log_file.close()

    async def run_batch(self, experiments: Dict[str, dict], group_order: Optional[List[str]] = None):
        RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
        self.total = len(experiments)
        self.completed = 0
        all_ok = []

        order = group_order or GROUP_ORDER
        seen = set()
        for study in order:
            group = {k: v for k, v in experiments.items() if v.get("study") == study}
            if not group:
                continue
            seen.update(group)
            print(f"\n{'='*72}\n  {study} ({len(group)} experiments)\n{'='*72}", flush=True)
            tasks = [self.run_one(name, cfg) for name, cfg in group.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict) and "error" not in r:
                    all_ok.append(r)

        remaining = {k: v for k, v in experiments.items() if k not in seen}
        if remaining:
            print(f"\n{'='*72}\n  other ({len(remaining)} experiments)\n{'='*72}", flush=True)
            tasks = [self.run_one(name, cfg) for name, cfg in remaining.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict) and "error" not in r:
                    all_ok.append(r)

        index_path = RESULTS_ROOT / "index.json"
        index_path.write_text(json.dumps(all_ok, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved {len(all_ok)} summaries -> {index_path}")
        return all_ok

    async def run_paper(self):
        return await self.run_batch(generate_all_experiments())

    async def run_scale(self):
        return await self.run_batch(
            generate_scale_experiments(), group_order=["supplement_scale"]
        )

    async def run_config(self, config_path: str):
        config_dict = json.loads(Path(config_path).read_text(encoding="utf-8"))
        name = config_dict["experiment_name"]
        return await self.run_one(name, config_dict)

    async def run_study(self, study: str):
        all_exp = {**generate_all_experiments(), **generate_scale_experiments()}
        batch = {k: v for k, v in all_exp.items() if v["study"] == study}
        if not batch:
            raise ValueError(f"No experiments for study: {study}")
        return await self.run_batch(batch, group_order=[study])
