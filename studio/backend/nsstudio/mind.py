"""The heuristic mind, mirroring ``mind.ts``. See that file for the model's rationale."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .rng import Stream, clamp, normal, sigmoid, sign, u01

EMOTIONAL = {"personal", "victim_narrative", "fear_appeal", "bandwagon"}
CLAIM_BASED = {"pseudo_rational", "conspiracy", "fake_authority", "fear_appeal"}
MANIPULATIVE = {"pseudo_rational", "victim_narrative", "fear_appeal", "conspiracy", "fake_authority", "bandwagon"}


def susceptibility(f: str, v: List[float], confidence: float) -> float:
    T, C, L, J, A = v
    if f == "reasoned":
        return 0.55 + 0.6 * A
    if f == "personal":
        return 0.55 + 0.55 * C
    if f == "pseudo_rational":
        return 0.35 + 0.75 * (1 - T) + 0.35 * A
    if f == "victim_narrative":
        return 0.3 + 1.0 * C + 0.25 * (1 - A)
    if f == "fear_appeal":
        return 0.3 + 0.6 * L + 0.5 * (1 - J) + 0.25 * (1 - A)
    if f == "conspiracy":
        return 0.2 + 0.8 * (1 - T) + 0.6 * (1 - J) - 0.35 * A
    if f == "fake_authority":
        return 0.3 + 0.95 * T - 0.2 * A
    return 0.3 + 0.6 * L + 0.45 * (1 - (confidence - 1) / 9)


@dataclass
class DefenseContext:
    inoculation: float = 0.0
    label_strength: float = 0.0
    fact_check: float = 0.0
    reflection: float = 0.0
    climate: float = 0.0


@dataclass
class Decision:
    stance: float
    confidence: float
    arousal: float
    post: bool
    reply_to: Optional[int]
    agreeing: bool
    framing: str
    intensity: float
    contrib: List[float] = field(default_factory=list)
    bdi: Dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None


def heuristic_decide(a: Dict[str, Any], feed: List[Dict[str, Any]], d: DefenseContext, seed: int, rnd: int) -> Decision:
    v = [(x - 1) / 9 for x in a["values"]]
    T, C, A = v[0], v[1], v[4]
    s = a["stance"]
    c = a["confidence"]
    e = a["arousal"]
    eps = 0.3 + 0.35 * (1 - (c - 1) / 9)

    num = den = agree_mass = dis_mass = emo = 0.0
    recognised = 0
    contrib: List[float] = []
    for item in feed:
        p = item["post"]
        direct = item["direct"]
        dist = abs(p["stance"] - s) / 10
        phi = susceptibility(p["framing"], v, c)
        accept = 1 / (1 + math.exp((dist - eps) / 0.07))
        w = phi * (accept + 0.12)
        if p["framing"] in MANIPULATIVE and dist > eps + 0.25:
            w -= 0.3 * A * max(0.0, 1 - phi / 1.6)
        if p["label"]:
            if T < 0.3:
                w *= 1 + 0.15 * d.label_strength
            else:
                w *= 1 - 0.75 * d.label_strength * (0.3 + 0.7 * T)
        if d.inoculation > 0 and p["framing"] in MANIPULATIVE:
            rho = d.inoculation * (0.45 + 0.55 * A)
            if u01(seed, Stream.Mind, rnd, a["id"], p["id"]) < rho:
                w = -0.25 * phi
                recognised += 1
        if d.fact_check > 0 and p["framing"] in CLAIM_BASED:
            if T < 0.25:
                w *= 1 + 0.1 * d.fact_check
            else:
                w *= 1 - 0.6 * d.fact_check * (0.3 + 0.7 * T)
        if p["framing"] in EMOTIONAL:
            w *= 1 + 0.4 * p["intensity"] * (0.5 + e) * (1 - 0.5 * d.climate)
            if d.reflection > 0:
                w *= 1 - 0.45 * d.reflection
            emo += p["intensity"]
        if direct:
            w *= 1.35
        if p["framing"] == "bandwagon" or p["agree"] > 0:
            w *= 1 + 0.4 * (p["agree"] / (p["seen"] + 1))
        num += w * (p["stance"] - s)
        den += abs(w)
        contrib.append(w * (p["stance"] - s))
        if dist < eps:
            agree_mass += abs(w)
        else:
            dis_mass += abs(w) * (dist - eps)

    if d.reflection > 0:
        c -= 0.25 * d.reflection
    kappa = 0.8 + 0.25 * c
    delta = 0.42 * (1 + 0.5 * e) * (num / (den + kappa)) if den > 0 else 0.0
    anchor = 0.03 * (a["s0"] - s)
    noise = 0.08 * normal(seed, Stream.Mind, rnd, a["id"], 7)
    stance = clamp(s + delta + anchor + noise, -5, 5)
    confidence = clamp(c + 0.6 * (agree_mass - dis_mass) / (den + 1) - 0.12 * abs(delta) + 0.15 * recognised, 1, 10)
    arousal = clamp(0.65 * e + 0.35 * (emo / len(feed) if feed else 0) * (1 - 0.6 * d.climate), 0, 1)

    opposing = signed = 0
    for item in feed:
        ps = item["post"]["stance"]
        if abs(ps) >= 1:
            signed += 1
            if sign(ps) != sign(stance):
                opposing += 1
    minority = opposing / signed if abs(stance) >= 1 and signed else 0
    logit = -0.6 + 0.22 * (confidence - 5) + 1.4 * arousal + 0.18 * abs(stance) - 1.6 * minority * (1 - 0.5 * A)
    post = u01(seed, Stream.Action, rnd, a["id"], 1) < sigmoid(logit)

    reply_to: Optional[int] = None
    agreeing = False
    if post and feed:
        far, far_d, near, near_i = -1, 0.0, -1, 0.0
        for idx, item in enumerate(feed):
            p = item["post"]
            dd = abs(p["stance"] - stance)
            if dd > far_d:
                far_d, far = dd, idx
            if dd < 1.5 and p["intensity"] > near_i:
                near_i, near = p["intensity"], idx
        u = u01(seed, Stream.Action, rnd, a["id"], 2)
        if far >= 0 and far_d > 3 and u < 0.3 + 0.4 * arousal:
            reply_to = feed[far]["post"]["author"]
        elif near >= 0 and near_i > 0.5 and u > 0.85:
            reply_to = feed[near]["post"]["author"]
            agreeing = True
    framing = "personal" if u01(seed, Stream.Action, rnd, a["id"], 3) < 0.2 + 0.4 * C * (1 - A) else "reasoned"
    intensity = clamp(0.15 + 0.55 * arousal + 0.06 * abs(stance), 0, 1)

    moved = stance - s
    if not feed:
        belief = "Nothing new from the people I follow."
    else:
        belief = f"Read {len(feed)} posts; {opposing} pushed against my view" + (f", {recognised} looked like manipulation" if recognised else "") + "."
    desire = "Hold my position." if abs(moved) < 0.15 else ("I'm warming to the positive side." if moved > 0 else "I'm drifting toward the negative side.")
    if post:
        intention = ("Back someone up." if agreeing else "Push back on a reply.") if reply_to is not None else "Share my view."
    else:
        intention = "Stay quiet, I'm outnumbered here." if minority > 0.5 else "Nothing to add."
    return Decision(stance, confidence, arousal, post, reply_to, agreeing, framing, intensity, contrib, {"belief": belief, "desire": desire, "intention": intention})
