"""Scenario schema: defaults, validation and limits, shared by the API and the CLI."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .engine import TOPICS


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Society(_Strict):
    n_agents: int = Field(120, ge=10, le=5000)
    rounds: int = Field(16, ge=1, le=200)
    population: Literal["representative", "trusting", "distrustful", "polarized", "analytical"] = "representative"
    memory: int = Field(6, ge=0, le=50)


class Network(_Strict):
    kind: Literal["scale_free", "small_world", "random", "communities"] = "scale_free"
    degree: float = Field(3, ge=1, le=20)
    rewire: float = Field(0.1, ge=0, le=1)
    communities: int = Field(3, ge=2, le=8)
    homophily: float = Field(0.8, ge=0, le=1)


class Feed(_Strict):
    ranking: Literal["chronological", "engagement"] = "chronological"
    capacity: int = Field(8, ge=1, le=100)


Strategy = Literal["pseudo_rational", "victim_narrative", "fear_appeal", "conspiracy", "fake_authority", "bandwagon"]


class Adversary(_Strict):
    enabled: bool = True
    n_attackers: int = Field(4, ge=0, le=500)
    placement: Literal["hub", "bridge", "random", "periphery"] = "hub"
    strategy: Strategy = "victim_narrative"
    coordination: Literal["independent", "echo", "complementary", "escalating"] = "independent"
    start: int = Field(1, ge=0)
    end: int = -1
    target: Literal[-1, 1] = -1
    adaptive: bool = True


class Defense(_Strict):
    kind: Literal["prebunking", "fact_check", "community_notes", "guardian", "suspension", "reflection_prompt", "climate_report"]
    enabled: bool = False
    start: int = Field(1, ge=0)
    strength: float = Field(0.6, ge=0, le=1)
    coverage: Optional[float] = Field(None, ge=0, le=1)
    every: Optional[int] = Field(None, ge=1)
    threshold: Optional[float] = Field(None, ge=0, le=1)
    action: Optional[Literal["label", "downrank", "remove"]] = None
    quorum: Optional[int] = Field(None, ge=1)
    strikes: Optional[int] = Field(None, ge=1)


class Engine(_Strict):
    mind: Literal["heuristic", "llm"] = "heuristic"
    model: Optional[str] = None


class Scenario(_Strict):
    name: str = "Untitled scenario"
    seed: int = Field(42, ge=0, le=2**31 - 1)
    topic: Union[str, Dict[str, Any]] = "vaccines"
    society: Society = Society()
    network: Network = Network()
    feed: Feed = Feed()
    adversary: Adversary = Adversary()
    defenses: List[Defense] = []
    engine: Engine = Engine()


DEFAULT_DEFENSES: List[Dict[str, Any]] = [
    {"kind": "prebunking", "enabled": False, "start": 1, "strength": 0.7, "coverage": 0.6},
    {"kind": "fact_check", "enabled": False, "start": 3, "strength": 0.6, "every": 3},
    {"kind": "community_notes", "enabled": False, "start": 2, "strength": 0.6, "quorum": 3},
    {"kind": "guardian", "enabled": False, "start": 2, "strength": 0.7, "threshold": 0.66, "action": "label"},
    {"kind": "suspension", "enabled": False, "start": 3, "strength": 1, "strikes": 3},
    {"kind": "reflection_prompt", "enabled": False, "start": 3, "strength": 0.6},
    {"kind": "climate_report", "enabled": False, "start": 3, "strength": 0.6, "every": 3},
]


def validate_scenario(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Validate, fill defaults, and return a plain dict the engine accepts."""
    from fastapi import HTTPException

    try:
        m = Scenario.model_validate(raw)
        s = m.model_dump(exclude_none=True)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None
    if isinstance(s["topic"], str) and s["topic"] not in {t["id"] for t in TOPICS}:
        raise HTTPException(422, f"unknown topic {s['topic']!r}")
    # Every defense kind is present (disabled unless given), in the engine's canonical order.
    given = {d.kind: d.model_dump(exclude_unset=True, exclude_none=True) for d in m.defenses}
    s["defenses"] = [{**copy.deepcopy(d), **given.get(d["kind"], {})} for d in DEFAULT_DEFENSES]
    return s
