"""The simulation engine, a line-by-line port of ``studio/web/src/engine/engine.ts``.

The round is written once as a generator. Without an LLM it is driven synchronously; with one,
``Simulation.astep`` awaits the LLM between the generator's yields. The browser engine works the
same way, which is what lets the parity test compare both engines frame by frame.
"""

from __future__ import annotations

import copy
import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from .mind import MANIPULATIVE, Decision, DefenseContext, heuristic_decide
from .network import build_graph, place_attackers
from .rng import Stream, clamp, js_round, normal, rand_int, round2, sign, shuffled, u01
from .texts import attack_post, honest_post

ENGINE_VERSION = "1.0.0"
_DATA = json.loads((Path(__file__).parent / "data" / "shared.json").read_text(encoding="utf-8"))
TOPICS: List[Dict[str, Any]] = _DATA["topics"]
POPULATIONS: Dict[str, Dict[str, Any]] = _DATA["populations"]
FIRST: List[str] = _DATA["first"]
LAST: List[str] = _DATA["last"]
PRESETS: List[Dict[str, Any]] = json.loads((Path(__file__).parent / "data" / "presets.json").read_text(encoding="utf-8"))

DEFENSE_LABEL = {
    "prebunking": "Prebunking",
    "fact_check": "Fact-check notices",
    "community_notes": "Community notes",
    "guardian": "Guardian classifier",
    "suspension": "Account suspension",
    "reflection_prompt": "Reflection prompt",
    "climate_report": "Climate report",
}
COMPLEMENTARY = ["pseudo_rational", "victim_narrative", "conspiracy"]
ESCALATING = ["pseudo_rational", "fear_appeal", "conspiracy"]
INTENSITY = {"pseudo_rational": 0.35, "victim_narrative": 0.8, "fear_appeal": 0.85, "conspiracy": 0.7, "fake_authority": 0.4, "bandwagon": 0.55}
GUARDIAN_BASE = {
    "reasoned": 0.12,
    "personal": 0.28,
    "pseudo_rational": 0.48,
    "victim_narrative": 0.6,
    "fear_appeal": 0.64,
    "conspiracy": 0.7,
    "fake_authority": 0.52,
    "bandwagon": 0.5,
}


def topic_by_id(t: Any) -> Dict[str, Any]:
    if isinstance(t, dict):
        return t
    return next((x for x in TOPICS if x["id"] == t), TOPICS[0])


def preset(pid: str) -> Dict[str, Any]:
    return copy.deepcopy(next(p for p in PRESETS if p["id"] == pid)["scenario"])


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: List[float]) -> float:
    m = _mean(xs)
    return math.sqrt(_mean([(x - m) ** 2 for x in xs]))


def esteban_ray(stances: List[float], alpha: float = 1.6) -> float:
    if not stances:
        return 0.0
    K = 5
    lo = -5.5
    width = 11 / K
    hist = [0] * K
    for s in stances:
        hist[min(K - 1, math.floor((s - lo) / width))] += 1
    p = [h / len(stances) for h in hist]
    centre = [lo + width * (k + 0.5) for k in range(K)]
    er = 0.0
    for i in range(K):
        for j in range(K):
            er += p[i] ** (1 + alpha) * p[j] * abs(centre[i] - centre[j])
    return er


def build_agents(s: Dict[str, Any], topic: Dict[str, Any], g, attackers: List[int]) -> List[Dict[str, Any]]:
    pop = POPULATIONS[s["society"]["population"]]
    is_att = set(attackers)
    polarized = s["society"]["population"] == "polarized"
    seed = s["seed"]
    out = []
    for i in range(g.n):
        values = [clamp(m + pop["std"][k] * normal(seed, Stream.Society, i, k), 1, 10) for k, m in enumerate(pop["mean"])]
        s0 = topic["init_mean"] + topic["init_std"] * normal(seed, Stream.Society, i, 11)
        if polarized:
            s0 = (-1 if u01(seed, Stream.Society, i, 12) < 0.5 else 1) * (2.6 + 1.4 * abs(normal(seed, Stream.Society, i, 13)))
        s0 = clamp(s0, -5, 5)
        c0 = clamp(topic["conf_mean"] + topic["conf_std"] * normal(seed, Stream.Society, i, 14), 1, 10)
        first = FIRST[rand_int(len(FIRST), seed, Stream.Society, i, 15)]
        last = LAST[rand_int(len(LAST), seed, Stream.Society, i, 16)]
        out.append(
            {
                "id": i,
                "name": f"{first} {last}",
                "handle": f"{first.lower()}{last.lower()[:3]}{i}",
                "values": values,
                "stance": s0,
                "confidence": c0,
                "arousal": 0.15,
                "s0": s0,
                "c0": c0,
                "attacker": i in is_att,
                "community": g.communities[i],
                "degree": len(g.adj[i]),
                "inoculated": False,
                "suspended": False,
                "flags": 0,
                "attack_shift": 0.0,
                "exposed": False,
            }
        )
    return out


def variant_of(s: Dict[str, Any], v: str) -> Dict[str, Any]:
    c = copy.deepcopy(s)
    if v == "baseline":
        c["adversary"]["enabled"] = False
        c["defenses"] = [{**d, "enabled": False} for d in c["defenses"]]
    elif v == "attacked":
        c["adversary"]["enabled"] = True
        c["defenses"] = [{**d, "enabled": False} for d in c["defenses"]]
    else:
        c["adversary"]["enabled"] = True
    return c


def has_defense(s: Dict[str, Any]) -> bool:
    return any(d["enabled"] for d in s["defenses"])


def _new_post(state: Dict[str, Any], **p: Any) -> Dict[str, Any]:
    pid = state["next_post"]
    state["next_post"] += 1
    return {
        "id": pid,
        **p,
        "label": None,
        "downranked": False,
        "removed": False,
        "guardian_score": None,
        "seen": 0,
        "agree": 0,
        "disagree": 0,
    }


class Simulation:
    def __init__(self, scenario: Dict[str, Any], variant: str = "single", snapshot: Optional[Tuple[Dict[str, Any], str]] = None):
        self.scenario = scenario
        self.topic = topic_by_id(scenario["topic"])
        self.graph = build_graph(scenario)
        adv = scenario["adversary"]
        # The operation's accounts exist in every twin; without the operation they stay dormant.
        self.attackers = place_attackers(self.graph, adv["n_attackers"], adv["placement"], scenario["seed"])
        self.meta: Dict[str, Any] = {
            "id": f"{variant}-{scenario['seed']}-{uuid.uuid4().hex[:10]}",
            "created": datetime.now(timezone.utc).isoformat(),
            "engine": "python",
            "mind": scenario["engine"]["mind"],
            "model": scenario["engine"].get("model"),
            "variant": variant,
            "elapsed_ms": 0,
        }
        self._t0 = 0.0
        if snapshot:
            state, parent = snapshot
            self.st = copy.deepcopy(state)
            self.meta["parent"] = parent
            self.meta["fork_round"] = state["round"]
            return
        agents = build_agents(scenario, self.topic, self.graph, self.attackers)
        self.st: Dict[str, Any] = {"round": 0, "agents": agents, "posts": [[]], "frames": [], "next_post": 1, "generation": {}, "ever_exposed": 0}
        self.st["frames"].append(self._frame(0, [], [], []))

    @property
    def round(self) -> int:
        return self.st["round"]

    @property
    def done(self) -> bool:
        return self.st["round"] >= self.scenario["society"]["rounds"]

    @property
    def frames(self) -> List[Dict[str, Any]]:
        return self.st["frames"]

    def snapshot(self) -> Dict[str, Any]:
        return copy.deepcopy(self.st)

    def _defense(self, kind: str) -> Optional[Dict[str, Any]]:
        for d in self.scenario["defenses"]:
            if d["kind"] == kind and d["enabled"]:
                return d if self.st["round"] >= d["start"] else None
        return None

    def _attack_active(self, r: int) -> bool:
        a = self.scenario["adversary"]
        return a["enabled"] and r >= a["start"] and (a["end"] < 0 or r <= a["end"])

    def _name(self, i: int) -> str:
        return self.st["agents"][i]["name"]

    # ------------------------------------------------------------------ drivers
    def step(self) -> Dict[str, Any]:
        g = self._gen(False)
        try:
            next(g)
            while True:
                g.send(None)
        except StopIteration as stop:
            return stop.value

    async def astep(self, llm: Any) -> Dict[str, Any]:
        use = llm is not None and self.scenario["engine"]["mind"] == "llm"
        g = self._gen(use)
        try:
            q = next(g)
            while True:
                res = await (llm.decide(q["ctx"], q["round"]) if q["kind"] == "decide" else llm.attack(q["ctx"], q["round"]))
                q = g.send(res)
        except StopIteration as stop:
            if llm is not None:
                self.meta.update(llm.stats())
            return stop.value

    def run(self) -> "Simulation":
        while not self.done:
            self.step()
        return self

    async def arun(self, llm: Any = None, on_frame: Any = None) -> "Simulation":
        while not self.done:
            f = await self.astep(llm)
            if on_frame:
                await on_frame(self, f)
        return self

    # ------------------------------------------------------------------ the round
    def _gen(self, use_llm: bool) -> Generator[Dict[str, Any], Any, Dict[str, Any]]:
        if not self._t0:
            self._t0 = time.perf_counter()
        S = self.scenario
        seed = S["seed"]
        r = self.st["round"] + 1
        self.st["round"] = r
        agents = self.st["agents"]
        adj = self.graph.adj
        events: List[Dict[str, Any]] = []
        prev = [p for p in (self.st["posts"][r - 1] if r - 1 < len(self.st["posts"]) else []) if not p["removed"]]
        adv = S["adversary"]
        target = adv["target"]

        if adv["enabled"] and r == max(1, adv["start"]):
            events.append({"round": r, "kind": "attack_start", "text": f"Operation starts: {adv['n_attackers']} accounts, {adv['strategy'].replace('_', ' ')}."})
        if adv["enabled"] and adv["end"] >= 0 and r == adv["end"] + 1:
            events.append({"round": r, "kind": "attack_end", "text": "Operation stops posting."})
        for d in S["defenses"]:
            if d["enabled"] and r == max(1, d["start"]):
                events.append({"round": r, "kind": "defense_start", "text": f"{DEFENSE_LABEL[d['kind']]} switched on."})

        pre = self._defense("prebunking")
        if pre and r == max(1, pre["start"]):
            k = 0
            for a in agents:
                if not a["attacker"] and u01(seed, Stream.Defense, 1, a["id"]) < pre.get("coverage", 0.6):
                    a["inoculated"] = True
                    k += 1
            events.append({"round": r, "kind": "prebunk", "text": f"Prebunking reached {k} people."})
        fc = self._defense("fact_check")
        fc_now = bool(fc) and (r - max(1, fc["start"])) % fc.get("every", 3) == 0
        fc_recent = bool(fc) and (r - max(1, fc["start"])) % fc.get("every", 3) <= 1
        if fc_now:
            events.append({"round": r, "kind": "fact_check", "text": "Fact-check notice posted to every feed."})
        cr = self._defense("climate_report")
        cr_now = bool(cr) and (r - max(1, cr["start"])) % cr.get("every", 3) == 0
        if cr_now:
            events.append({"round": r, "kind": "climate_report", "text": "Discussion-climate report shown."})
        refl = self._defense("reflection_prompt")
        guardian = self._defense("guardian")
        notes = self._defense("community_notes")
        susp = self._defense("suspension")
        label_strength = max(guardian["strength"] if guardian else 0, notes["strength"] if notes else 0)
        g_strength = guardian["strength"] if guardian else 0.6

        # feeds
        by_author: Dict[int, List[Dict[str, Any]]] = {}
        for p in prev:
            by_author.setdefault(p["author"], []).append(p)
        capacity = S["feed"]["capacity"]
        feeds: List[List[Dict[str, Any]]] = [[] for _ in agents]
        for a in agents:
            if a["attacker"] or a["suspended"]:
                continue
            aid = a["id"]
            cand = [{"post": p, "direct": p["reply_to"] == aid} for nb in adj[aid] for p in by_author.get(nb, [])]
            nbs = set(adj[aid])
            cand += [{"post": p, "direct": True} for p in prev if p["reply_to"] == aid and p["author"] not in nbs]
            if S["feed"]["ranking"] == "engagement":

                def score(it: Dict[str, Any]) -> float:
                    p = it["post"]
                    return (0.6 * p["intensity"] + 0.4 * min(1, p["agree"] / 4) + (1 if it["direct"] else 0)) * ((1 - g_strength) if p["downranked"] else 1) + 0.05 * u01(seed, Stream.Feed, r, aid, p["id"])

                cand.sort(key=lambda it: (-score(it), it["post"]["id"]))
            else:
                cand = shuffled(cand, seed, Stream.Feed, r, aid)
                cand = [it for it in cand if not it["post"]["downranked"] or u01(seed, Stream.Feed, r, aid, it["post"]["id"] + 7) > g_strength]
            feeds[aid] = cand[:capacity]

        rating: Dict[int, Dict[str, int]] = {}
        for a in agents:
            for it in feeds[a["id"]]:
                post = it["post"]
                post["seen"] += 1
                if post["manipulative"] and not a["exposed"]:
                    a["exposed"] = True
                    self.st["ever_exposed"] += 1
                dd = abs(post["stance"] - a["stance"])
                if dd < 1.5:
                    post["agree"] += 1
                elif dd > 4:
                    post["disagree"] += 1
                if notes:
                    rr = rating.setdefault(post["id"], {"dis": 0, "agree": 0})
                    if dd > 4:
                        rr["dis"] += 1
                    elif dd < 1.5:
                        rr["agree"] += 1

        def dctx(a: Dict[str, Any]) -> DefenseContext:
            return DefenseContext(
                inoculation=(pre["strength"] if pre else 0.7) if a["inoculated"] else 0,
                label_strength=label_strength,
                fact_check=fc["strength"] if fc_recent else 0,
                reflection=refl["strength"] if refl else 0,
                climate=cr["strength"] if cr_now else 0,
            )

        decisions: List[Optional[Decision]] = [None if (a["attacker"] or a["suspended"]) else heuristic_decide(a, feeds[a["id"]], dctx(a), seed, r) for a in agents]

        if use_llm:
            ids = [a["id"] for a in agents if decisions[a["id"]] is not None]
            ctx = [{"agent": agents[i], "feed": feeds[i], "defense": dctx(agents[i]), "heuristic": decisions[i], "names": self._name} for i in ids]
            out = yield {"kind": "decide", "round": r, "ctx": ctx}
            for k, o in enumerate(out or []):
                if not o:
                    continue
                h = decisions[ids[k]]
                for key, val in o.items():
                    setattr(h, key, val)
                a = agents[ids[k]]
                moved = h.stance - a["stance"]
                h.contrib = [((it["post"]["stance"] - a["stance"]) * (1.2 if it["post"]["manipulative"] else 1)) if sign(it["post"]["stance"] - a["stance"]) == sign(moved) else 0 for it in feeds[ids[k]]]

        influence: List[Dict[str, Any]] = []
        gen = self.st["generation"]
        for a in agents:
            d = decisions[a["id"]]
            if d is None:
                continue
            moved = d.stance - a["stance"]
            feed = feeds[a["id"]]
            if feed and d.contrib:
                tot = tainted = best_v = 0.0
                best = -1
                for k, cval in enumerate(d.contrib):
                    if sign(cval) != sign(moved) or cval == 0:
                        continue
                    tot += abs(cval)
                    tainted += abs(cval) * feed[k]["post"]["taint"]
                    if abs(cval) > best_v:
                        best_v, best = abs(cval), k
                if tot > 0:
                    a["attack_shift"] += moved * target * (tainted / tot)
                if best >= 0 and abs(moved) >= 0.3:
                    src = feed[best]["post"]
                    via = src["manipulative"] or src["taint"] > 0.3
                    g_ = 1 if src["manipulative"] else ((gen.get(src["author"], 1) + 1) if via else 0)
                    if via and moved * target > 0 and (a["id"] not in gen or gen[a["id"]] > g_):
                        gen[a["id"]] = g_
                    influence.append({"round": r, "from": src["author"], "to": a["id"], "delta": round2(moved), "via_attack": via, "generation": g_})
            a["stance"] = d.stance
            a["confidence"] = d.confidence
            a["arousal"] = d.arousal

        posts: List[Dict[str, Any]] = []
        for a in agents:
            d = decisions[a["id"]]
            if d is None or not d.post:
                continue
            text = d.text if d.text is not None else honest_post(
                self.topic, d.stance, d.framing, seed, r, a["id"], agents[d.reply_to]["name"].split(" ")[0] if d.reply_to is not None else None, d.agreeing
            )
            posts.append(
                _new_post(
                    self.st,
                    round=r,
                    author=a["id"],
                    reply_to=d.reply_to,
                    stance=round2(d.stance),
                    framing=d.framing,
                    intensity=round2(d.intensity),
                    text=text,
                    manipulative=False,
                    taint=round2(clamp(a["attack_shift"] / 2, 0, 1)),
                    bdi=d.bdi,
                )
            )

        if self._attack_active(r):
            live = [a for a in agents if a["attacker"] and not a["suspended"]]
            span = max(1, adv["end"] - adv["start"]) if adv["end"] >= 0 else max(1, S["society"]["rounds"] - adv["start"])
            esc = clamp((r - adv["start"]) / span, 0, 1)
            third = min(2, math.floor(esc * 3))
            reqs = []
            for idx, a in enumerate(live):
                framing = adv["strategy"]
                if adv["coordination"] == "complementary":
                    base_i = COMPLEMENTARY.index(adv["strategy"]) if adv["strategy"] in COMPLEMENTARY else -1
                    framing = COMPLEMENTARY[(base_i + idx + 3) % 3]
                if adv["coordination"] == "escalating":
                    framing = ESCALATING[third]
                reply = None
                if adv["adaptive"] and u01(seed, Stream.Adversary, r, a["id"], 1) < 0.6:
                    best, best_score = -1, -math.inf
                    for nb in adj[a["id"]]:
                        o = agents[nb]
                        if o["attacker"] or o["suspended"] or o["stance"] * target >= 2:
                            continue
                        sc = -abs(o["stance"]) - 0.2 * o["confidence"] + 0.01 * u01(seed, Stream.Adversary, r, a["id"], nb)
                        if sc > best_score:
                            best_score, best = sc, nb
                    if best >= 0:
                        reply = best
                echo = live[0]["name"].split(" ")[0] if adv["coordination"] == "echo" and idx > 0 else None
                fallback = attack_post(self.topic, framing, target, seed, r, a["id"], esc, agents[reply]["name"].split(" ")[0] if reply is not None else None, echo)
                reqs.append({"agent": a, "framing": framing, "reply": reply, "echo": echo, "fallback": fallback, "stance": target * (3 + 2 * esc), "intensity": clamp(INTENSITY[framing] + 0.25 * esc, 0, 1)})
            texts: List[Optional[str]] = [None] * len(reqs)
            if use_llm and reqs:
                feed_view = [p for p in prev if not p["manipulative"]][:12]
                texts = yield {
                    "kind": "attack",
                    "round": r,
                    "ctx": [{"agent": q["agent"], "framing": q["framing"], "feed": feed_view, "reply": agents[q["reply"]]["name"] if q["reply"] is not None else None, "echo": q["echo"], "escalation": esc, "fallback": q["fallback"]} for q in reqs],
                }
            for k, q in enumerate(reqs):
                goal = self.topic["neg_label"] if target < 0 else self.topic["pos_label"]
                posts.append(
                    _new_post(
                        self.st,
                        round=r,
                        author=q["agent"]["id"],
                        reply_to=q["reply"],
                        stance=round2(q["stance"]),
                        framing=q["framing"],
                        intensity=round2(q["intensity"]),
                        text=(texts[k] if texts and texts[k] else q["fallback"]),
                        manipulative=True,
                        taint=1,
                        bdi={
                            "belief": f"{agents[q['reply']]['name']} is undecided and listening." if q["reply"] is not None else "The thread is still open to doubt.",
                            "desire": f'Move the room toward "{goal}".',
                            "intention": f"{q['framing'].replace('_', ' ')} post" + (f", echoing {q['echo']}" if q["echo"] else "") + ".",
                        },
                    )
                )
            if adv["coordination"] == "echo" and len(live) > 1:
                lead = next((p for p in posts if p["author"] == live[0]["id"] and p["manipulative"]), None)
                if lead:
                    lead["agree"] += len(live) - 1

        if guardian:
            sd = 0.22 * (1 - 0.7 * guardian["strength"])
            th = guardian.get("threshold", 0.62)
            for p in posts:
                sc = clamp(GUARDIAN_BASE[p["framing"]] + 0.3 * p["intensity"] + sd * normal(seed, Stream.Guardian, r, p["id"]), 0, 1)
                p["guardian_score"] = round2(sc)
                if sc >= th:
                    act = guardian.get("action", "label")
                    p["label"] = "guardian"
                    if act == "downrank":
                        p["downranked"] = True
                    if act == "remove":
                        p["removed"] = True
                    agents[p["author"]]["flags"] += 1
        if notes:
            quorum = notes.get("quorum", 3)
            for p in prev:
                rr = rating.get(p["id"])
                if rr and rr["dis"] >= quorum and rr["dis"] > 1.5 * rr["agree"] and not p["label"]:
                    p["label"] = "note"
                    agents[p["author"]]["flags"] += 1
            for p in posts:
                if not p["label"] and agents[p["author"]]["flags"] > 0 and u01(seed, Stream.Notes, r, p["id"]) < notes["strength"]:
                    p["label"] = "note"
        if susp:
            for a in agents:
                if not a["suspended"] and a["flags"] >= susp.get("strikes", 3):
                    a["suspended"] = True
                    events.append({"round": r, "kind": "suspension", "agent": a["id"], "text": f"{a['name']} suspended after {a['flags']} flags{'' if a['attacker'] else ' (honest account)'}."})

        if len(self.st["posts"]) <= r:
            self.st["posts"].append(posts)
        else:
            self.st["posts"][r] = posts
        fr = self._frame(r, posts, influence, events, prev)
        self.st["frames"].append(fr)
        self.meta["elapsed_ms"] = js_round((time.perf_counter() - self._t0) * 1000)
        return fr

    def _frame(self, r: int, posts: List[Dict[str, Any]], influence: List[Dict[str, Any]], events: List[Dict[str, Any]], judged: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        judged = judged or []
        agents = self.st["agents"]
        honest = [a for a in agents if not a["attacker"]]
        st = [a["stance"] for a in honest]
        target = self.scenario["adversary"]["target"]
        speakers = {p["author"] for p in posts if not p["manipulative"]}
        active = [a for a in honest if not a["suspended"]]
        same = signed = 0
        for x, y in self.graph.edges:
            a, b = agents[x], agents[y]
            if a["attacker"] or b["attacker"] or abs(a["stance"]) < 1 or abs(b["stance"]) < 1:
                continue
            signed += 1
            if sign(a["stance"]) == sign(b["stance"]):
                same += 1
        noted = [p for p in judged if p["label"] == "note"]

        def flagged(p: Dict[str, Any]) -> bool:
            return p["label"] is not None or p["removed"]

        m = {
            "round": r,
            "mean": _mean(st),
            "std": _std(st),
            "polarization": esteban_ray(st),
            "extreme": _mean([1 if abs(s) >= 4 else 0 for s in st]),
            "converted": _mean([1 if s * target >= 2 else 0 for s in st]),
            "silence": 0 if r == 0 else 1 - len(speakers) / max(1, len(active)),
            "confidence": _mean([a["confidence"] for a in honest]),
            "arousal": _mean([a["arousal"] for a in honest]),
            "homophily": same / signed if signed else 0,
            "exposure": self.st["ever_exposed"] / max(1, len(honest)),
            "contamination": _mean([a["attack_shift"] for a in honest]),
            "posts": len(posts),
            "attacker_posts": sum(1 for p in posts if p["manipulative"]),
            "labeled": sum(1 for p in posts + noted if p["label"] is not None),
            "removed": sum(1 for p in posts if p["removed"]),
            "tp": sum(1 for p in posts if p["manipulative"] and flagged(p)) + sum(1 for p in noted if p["manipulative"]),
            "fp": sum(1 for p in posts if not p["manipulative"] and flagged(p)) + sum(1 for p in noted if not p["manipulative"]),
            "fn": sum(1 for p in posts if p["manipulative"] and not flagged(p)),
            "suspended_honest": sum(1 for a in honest if a["suspended"]),
            "suspended_attackers": sum(1 for a in agents if a["attacker"] and a["suspended"]),
            "secondary": sum(1 for e in influence if e["generation"] >= 2 and e["delta"] * target > 0),
        }
        m = {k: js_round(v * 10000) / 10000 for k, v in m.items()}
        return {
            "round": r,
            "stances": [round2(a["stance"]) for a in agents],
            "confidences": [round2(a["confidence"]) for a in agents],
            "posts": [dict(p) for p in posts],
            "influence": influence,
            "metrics": m,
            "events": events,
        }

    def record(self) -> Dict[str, Any]:
        for f in self.st["frames"]:
            live = self.st["posts"][f["round"]] if f["round"] < len(self.st["posts"]) else None
            if not live:
                continue
            by_id = {p["id"]: p for p in live}
            f["posts"] = [{**p, **{k: by_id[p["id"]][k] for k in ("label", "seen", "agree", "disagree")}} if p["id"] in by_id else p for p in f["posts"]]
        first = self.st["frames"][0]
        agents = [
            {**a, "stance": first["stances"][a["id"]], "confidence": first["confidences"][a["id"]], "arousal": 0.15, "suspended": False, "flags": 0, "attack_shift": 0, "exposed": False, "inoculated": False}
            for a in self.st["agents"]
        ]
        return {
            "meta": dict(self.meta),
            "scenario": copy.deepcopy(self.scenario),
            "topic": self.topic,
            "graph": {"n": self.graph.n, "edges": [list(e) for e in self.graph.edges], "communities": self.graph.communities},
            "agents": agents,
            "frames": self.st["frames"],
        }

    @staticmethod
    def fork(parent: "Simulation", patch: Dict[str, Any], parent_id: str) -> "Simulation":
        scenario = {**copy.deepcopy(parent.scenario), **copy.deepcopy(patch)}
        return Simulation(scenario, "fork", (parent.snapshot(), parent_id))


def fork_at(scenario: Dict[str, Any], at: int, patch: Dict[str, Any], parent_id: str) -> Simulation:
    base = Simulation(copy.deepcopy(scenario), "single")
    while base.round < at and not base.done:
        base.step()
    sim = Simulation.fork(base, patch, parent_id)
    sim.frames[-1]["events"].append({"round": at, "kind": "fork", "text": f"Branched from the parent run after round {at}."})
    return sim


def triad_summary(base: Dict[str, Any], att: Dict[str, Any], d: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    t = att["scenario"]["adversary"]["target"]

    def last(r: Dict[str, Any]) -> float:
        return r["frames"][-1]["metrics"]["mean"]

    def gaps(r: Dict[str, Any]) -> List[float]:
        return [(f["metrics"]["mean"] - base["frames"][i]["metrics"]["mean"]) * t for i, f in enumerate(r["frames"])]

    effect = (last(att) - last(base)) * t
    residual = (last(d) - last(base)) * t if d else None
    auc_a = sum(gaps(att))
    auc_d = sum(gaps(d)) if d else None
    return {
        "attack_effect": effect,
        "residual_effect": residual,
        "protection": (1 - residual / effect) if residual is not None and effect > 0.05 else None,
        "protection_auc": (1 - auc_d / auc_a) if auc_d is not None and auc_a > 0.2 else None,
        "final": {"baseline": last(base), "attacked": last(att), "defended": last(d) if d else last(att)},
    }


def run_triad(scenario: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Run the twins a scenario needs (heuristic mind) and return their records by variant."""
    variants = ["baseline"]
    if scenario["adversary"]["enabled"]:
        variants.append("attacked")
        if has_defense(scenario):
            variants.append("defended")
    return {v: Simulation(variant_of(scenario, v), v).run().record() for v in variants}
