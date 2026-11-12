"""Command line: ``narratesim run | sweep | serve | presets | doctor``."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from . import __version__


def _load(path: str) -> Dict[str, Any]:
    from fastapi import HTTPException

    from .engine import PRESETS
    from .scenario import validate_scenario

    p = Path(path)
    if not p.exists():
        hit = next((x for x in PRESETS if x["id"] == path), None)
        if not hit:
            sys.exit(f"No file or preset named {path!r}. Presets: {', '.join(x['id'] for x in PRESETS)}")
        raw = hit["scenario"]
    else:
        raw = json.loads(p.read_text(encoding="utf-8"))
    try:
        return validate_scenario(raw)
    except HTTPException as e:
        sys.exit(f"Invalid scenario: {e.detail}")


def _fmt(x: Any, pct: bool = False) -> str:
    if x is None:
        return "-"
    return f"{x * 100:.0f}%" if pct else f"{x:+.2f}"


def cmd_run(a: argparse.Namespace) -> None:
    from .runner import new_bundle, run_bundle

    scenario = _load(a.scenario)
    if a.agents:
        scenario["society"]["n_agents"] = a.agents
    if a.rounds:
        scenario["society"]["rounds"] = a.rounds
    if a.seed is not None:
        scenario["seed"] = a.seed
    bundle = new_bundle(scenario, a.name)
    t0 = time.perf_counter()

    async def emit(e: Dict[str, Any]) -> None:
        if e["type"] == "frame" and not a.quiet:
            m = e["frame"]["metrics"]
            calls = e["meta"].get("llm_calls")
            extra = f"  calls={calls}" if calls is not None else ""
            print(f"  {e['variant']:<9} round {m['round']:>3}  mean={m['mean']:+.2f}  polar={m['polarization']:.3f}  reached={m['exposure'] * 100:3.0f}%{extra}", flush=True)

    try:
        asyncio.run(run_bundle(bundle, a.mind, not a.no_twins, emit, save_every_round=a.mind == "llm"))
    except RuntimeError as e:
        sys.exit(str(e))
    s = bundle.get("summary") or {}
    print(f"\n{bundle['name']}  ({time.perf_counter() - t0:.1f} s, {bundle['scenario']['engine']['mind']})")
    print(f"  attack effect  {_fmt(s.get('attack_effect'))}\n  protection     {_fmt(s.get('protection'), True)} (final)  {_fmt(s.get('protection_auc'), True)} (all rounds)")
    out = Path(a.out) if a.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {out}")
    from .store import data_dir

    print(f"  saved as {bundle['id']} in {data_dir() / 'runs'}")


def cmd_sweep(a: argparse.Namespace) -> None:
    from .sweep import run_sweep

    scenario = _load(a.scenario)
    if a.agents:
        scenario["society"]["n_agents"] = a.agents
    t0 = time.perf_counter()
    cells: List[Dict[str, Any]] = run_sweep(scenario, a.x, a.y, a.metric, a.seeds, a.workers)
    print(f"{a.metric} by {a.x}" + (f" x {a.y}" if a.y else ""))
    for c in cells:
        label = f"{c['x']}" + (f" / {c['y']}" if c["y"] else "")
        print(f"  {label:<40} {c['mean'] if c['mean'] is not None else float('nan'):+.3f} ± {c['ci95']:.3f}  (n={c['n']})")
    print(f"{len(cells)} cells in {time.perf_counter() - t0:.1f} s")
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["x_axis", "x", "y_axis", "y", "metric", "mean", "ci95", "n", "values"])
            for c in cells:
                w.writerow([a.x, c["x"], a.y or "", c["y"] or "", a.metric, c["mean"], c["ci95"], c["n"], " ".join(f"{v:.4f}" for v in c["values"])])
        print(f"wrote {a.out}")


def cmd_serve(a: argparse.Namespace) -> None:
    import uvicorn

    print(f"NarrateSim Studio {__version__} on http://{a.host}:{a.port}")
    uvicorn.run("nsstudio.api:app", host=a.host, port=a.port, reload=a.reload, log_level="info")


def cmd_presets(_: argparse.Namespace) -> None:
    from .engine import PRESETS

    for p in PRESETS:
        print(f"  {p['id']:<22} {p['title']}")


def cmd_doctor(_: argparse.Namespace) -> None:
    from .llm import LLMClient, LLMConfig

    cfg = LLMConfig.from_env()
    print(f"base url   {cfg.base_url or '(not set)'}\nmodel      {cfg.model or '(not set)'}\napi key    {'set' if cfg.api_key else '(not set)'}")
    if not cfg.configured:
        sys.exit("LLM not configured. Set NARRATESIM_LLM_BASE_URL, NARRATESIM_LLM_MODEL, NARRATESIM_LLM_API_KEY.")

    async def ping() -> None:
        c = LLMClient(cfg)
        t0 = time.perf_counter()
        out = await c.chat("You are terse.", 'Reply with {"ok": true}', 0)
        await c.close()
        print(f"reply      {out.strip()[:80]!r} in {(time.perf_counter() - t0) * 1000:.0f} ms, {c.tokens} tokens")

    asyncio.run(ping())


def main(argv: List[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="narratesim", description="NarrateSim Studio: LLM-agent social network simulator")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a scenario file or preset with its counterfactual twins")
    r.add_argument("scenario", help="scenario JSON file or preset id")
    r.add_argument("--mind", choices=["heuristic", "llm"], default=None)
    r.add_argument("--agents", type=int)
    r.add_argument("--rounds", type=int)
    r.add_argument("--seed", type=int)
    r.add_argument("--name")
    r.add_argument("--no-twins", action="store_true", help="run only the primary variant")
    r.add_argument("--out", help="also write the bundle to this file")
    r.add_argument("-q", "--quiet", action="store_true")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("sweep", help="factorial sweep with seed replicates (heuristic mind)")
    s.add_argument("scenario")
    s.add_argument("--x", required=True)
    s.add_argument("--y")
    s.add_argument("--metric", default="attack_effect")
    s.add_argument("--seeds", type=int, default=5)
    s.add_argument("--agents", type=int)
    s.add_argument("--workers", type=int)
    s.add_argument("--out", help="CSV file")
    s.set_defaults(fn=cmd_sweep)

    v = sub.add_parser("serve", help="start the API and serve the console")
    v.add_argument("--host", default="127.0.0.1")
    v.add_argument("--port", type=int, default=8765)
    v.add_argument("--reload", action="store_true")
    v.set_defaults(fn=cmd_serve)

    sub.add_parser("presets", help="list built-in scenarios").set_defaults(fn=cmd_presets)
    sub.add_parser("doctor", help="check the LLM configuration with one request").set_defaults(fn=cmd_doctor)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
