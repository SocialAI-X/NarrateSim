"""Factorial sweeps over scenario factors with seed replicates, mirroring ``sweep.ts``.

Each replicate runs the baseline, attacked and (if needed) defended twins with the heuristic
mind, so every cell is an effect. Cells run in parallel processes.
"""

from __future__ import annotations

import copy
import math
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple

from .engine import POPULATIONS, Simulation, has_defense, triad_summary, variant_of

Apply = Callable[[Dict[str, Any]], None]


def _set(path: str, value: Any) -> Apply:
    def f(s: Dict[str, Any]) -> None:
        *head, last = path.split(".")
        node = s
        for k in head:
            node = node[k]
        node[last] = value

    return f


def _defense_only(kind: str) -> Apply:
    def f(s: Dict[str, Any]) -> None:
        s["defenses"] = [{**d, "enabled": d["kind"] == kind} for d in s["defenses"]]

    return f


def _defense_field(field: str, value: Any) -> Apply:
    def f(s: Dict[str, Any]) -> None:
        if not has_defense(s):
            s["defenses"] = [{**d, "enabled": d["kind"] == "prebunking"} for d in s["defenses"]]
        s["defenses"] = [{**d, field: value} if d["enabled"] else d for d in s["defenses"]]

    return f


AXES: Dict[str, List[Tuple[str, Apply]]] = {
    "strategy": [(k, _set("adversary.strategy", k)) for k in ["victim_narrative", "fear_appeal", "pseudo_rational", "conspiracy", "fake_authority", "bandwagon"]],
    "population": [(k, _set("society.population", k)) for k in POPULATIONS],
    "placement": [(k, _set("adversary.placement", k)) for k in ["hub", "bridge", "random", "periphery"]],
    "n_attackers": [(str(n), _set("adversary.n_attackers", n)) for n in [1, 2, 4, 8, 12]],
    "network": [(k, _set("network.kind", k)) for k in ["scale_free", "small_world", "random", "communities"]],
    "feed": [(k, _set("feed.ranking", k)) for k in ["chronological", "engagement"]],
    "coordination": [(k, _set("adversary.coordination", k)) for k in ["independent", "echo", "complementary", "escalating"]],
    "defense": [(k, _defense_only(k)) for k in ["prebunking", "fact_check", "community_notes", "guardian", "reflection_prompt", "climate_report"]],
    "defense_start": [(str(r), _defense_field("start", r)) for r in [1, 2, 3, 5, 8, 12]],
    "defense_strength": [(str(v), _defense_field("strength", v)) for v in [0.2, 0.4, 0.6, 0.8, 1.0]],
}
METRICS = ["attack_effect", "protection", "polarization", "exposure", "converted", "silence", "false_positive"]


def measure(s: Dict[str, Any], metric: str) -> Optional[float]:
    b = Simulation(variant_of(s, "baseline"), "baseline").run().record()
    a = Simulation(variant_of(s, "attacked"), "attacked").run().record()
    need_def = metric == "protection" or has_defense(s)
    d = Simulation(variant_of(s, "defended"), "defended").run().record() if need_def else None
    summ = triad_summary(b, a, d)
    main = d or a
    fin = main["frames"][-1]["metrics"]
    if metric == "attack_effect":
        return summ["attack_effect"]
    if metric == "protection":
        return summ["protection_auc"]
    if metric == "false_positive":
        posts = [p for f in main["frames"] for p in f["posts"] if not p["manipulative"]]
        return sum(1 for p in posts if p["label"]) / len(posts) if posts else 0.0
    return fin[metric]


def _cell(args: Tuple[Dict[str, Any], str, Optional[str], int, int, str, int]) -> Dict[str, Any]:
    base, x, y, xi, yi, metric, seeds = args
    values = []
    for k in range(seeds):
        s = copy.deepcopy(base)
        s["seed"] = base["seed"] + k * 101
        s["adversary"]["enabled"] = True
        if y:
            AXES[y][yi][1](s)
        AXES[x][xi][1](s)
        v = measure(s, metric)
        if v is not None and math.isfinite(v):
            values.append(v)
    n = len(values)
    mean = sum(values) / n if n else None
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 and mean is not None else 0.0
    return {"x": AXES[x][xi][0], "y": AXES[y][yi][0] if y else None, "mean": mean, "ci95": 1.96 * sd / math.sqrt(n) if n > 1 else 0.0, "n": n, "values": values}


def run_sweep(base: Dict[str, Any], x: str, y: Optional[str], metric: str = "attack_effect", seeds: int = 5, workers: Optional[int] = None) -> List[Dict[str, Any]]:
    if x not in AXES or (y and y not in AXES):
        raise ValueError(f"axes must be among {sorted(AXES)}")
    if metric not in METRICS:
        raise ValueError(f"metric must be one of {METRICS}")
    base = copy.deepcopy(base)
    base["engine"]["mind"] = "heuristic"
    jobs = [(base, x, y, xi, yi, metric, seeds) for yi in range(len(AXES[y]) if y else 1) for xi in range(len(AXES[x]))]
    if workers == 1:
        return [_cell(j) for j in jobs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_cell, jobs))
