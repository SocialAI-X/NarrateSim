"""Run a scenario with its counterfactual twins, with either mind, and keep a bundle on disk."""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from . import store
from .engine import Simulation, has_defense, topic_by_id, triad_summary, variant_of
from .llm import LLMClient, LLMConfig, LLMMinds

Emit = Callable[[Dict[str, Any]], Awaitable[None]]


def variants_for(scenario: Dict[str, Any], twins: bool = True) -> List[str]:
    if not scenario["adversary"]["enabled"]:
        return ["baseline"]
    primary = "defended" if has_defense(scenario) else "attacked"
    if not twins:
        return [primary]
    order = [primary, "baseline"]
    if primary == "defended":
        order.append("attacked")
    return order


def new_bundle(scenario: Dict[str, Any], name: Optional[str] = None) -> Dict[str, Any]:
    return {
        "id": f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "name": name or scenario.get("name") or "Untitled",
        "created": datetime.now(timezone.utc).isoformat(),
        "status": "queued",
        "scenario": copy.deepcopy(scenario),
        "runs": {},
        "forks": [],
        "llm_log": [],
    }


def summarize(bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    r = bundle["runs"]
    if "baseline" in r and "attacked" in r:
        return triad_summary(r["baseline"], r["attacked"], r.get("defended"))
    return None


async def run_bundle(bundle: Dict[str, Any], mind: Optional[str] = None, twins: bool = True, emit: Optional[Emit] = None, llm_cfg: Optional[LLMConfig] = None, save_every_round: bool = True) -> Dict[str, Any]:
    """Run every variant of a bundle's scenario in place. Saves after each round so a crash keeps progress."""
    scenario = bundle["scenario"]
    if mind:
        scenario["engine"]["mind"] = mind
    client: Optional[LLMClient] = None
    if scenario["engine"]["mind"] == "llm":
        cfg = llm_cfg or LLMConfig.from_env()
        if not cfg.configured:
            raise RuntimeError("LLM mind requested but no model is configured (see `narratesim doctor`)")
        scenario["engine"]["model"] = cfg.model
        client = LLMClient(cfg)
    bundle["status"] = "running"
    store.save(bundle)
    try:
        for v in variants_for(scenario, twins):
            sim = Simulation(variant_of(scenario, v), v)
            minds = LLMMinds(client, topic_by_id(scenario["topic"]), scenario["adversary"]["target"], bundle["llm_log"]) if client else None
            bundle["runs"][v] = sim.record()
            if emit:
                await emit({"type": "variant", "variant": v, "record": bundle["runs"][v]})

            async def on_frame(s: Simulation, f: Dict[str, Any], v: str = v) -> None:
                bundle["runs"][v]["frames"] = s.frames
                bundle["runs"][v]["meta"] = dict(s.meta)
                if save_every_round:
                    store.save(bundle)
                if emit:
                    await emit({"type": "frame", "variant": v, "frame": f, "meta": s.meta})

            await sim.arun(minds, on_frame)
            bundle["runs"][v] = sim.record()
        bundle["summary"] = summarize(bundle)
        bundle["status"] = "done"
    except Exception as e:  # noqa: BLE001
        bundle["status"] = "error"
        bundle["error"] = str(e)[:500]
        raise
    finally:
        store.save(bundle)
        if client:
            await client.close()
        if emit:
            await emit({"type": "status", "status": bundle["status"], "summary": bundle.get("summary"), "error": bundle.get("error")})
    return bundle
