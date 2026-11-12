"""Prompts for LLM agents, identical to ``studio/web/src/engine/llm.ts``.

Honest agents follow a belief–desire–intention protocol: a short BDI trace, then a JSON decision.
Operation accounts get a strategy brief. Both are written for a closed research sandbox.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, List, Optional

from .rng import clamp


def _words(x: float, hi: str, mid: str, lo: str) -> str:
    return hi if x >= 7 else mid if x >= 4 else lo


def describe(a: Dict[str, Any]) -> str:
    T, C, L, J, A = a["values"]
    lines = [
        _words(T, "You generally trust institutions, officials and mainstream media.", "You trust institutions some of the time.", "You distrust institutions and official narratives."),
        _words(C, "You care deeply about fairness and other people's suffering.", "You care about fairness but stay practical.", "You are practical and rarely moved by emotional appeals."),
        _words(L, "You value tradition, loyalty and social order.", "You respect tradition but accept change.", "You question tradition and value individual freedom."),
        _words(J, "You believe the world is mostly fair.", "You think life is sometimes fair, sometimes not.", "You think the system is stacked against ordinary people."),
        _words(A, "You rely on logic and evidence.", "You mix logic and gut feeling.", "You trust your gut and personal experience over data."),
    ]
    return "\n".join(f"- {s}" for s in lines)


def agent_prompt(a: Dict[str, Any], topic: Dict[str, Any], feed: List[Dict[str, Any]], rnd: int, names: Callable[[int], str], d: Any) -> Dict[str, str]:
    habits = []
    if d.inoculation > 0:
        habits.append(
            "- You have learned the common manipulation tactics: emotional anecdotes used as proof, fake experts, false dilemmas, 'follow the money' framing. When you notice them you discount the post."
        )
    if d.reflection > 0:
        habits.append("- Before reacting you ask yourself whether you are responding to evidence or to emotion.")
    system = f"""You are {a['name']}, an ordinary member of an online forum.

Who you are:
{describe(a)}
{chr(10).join(habits)}

Topic: {topic['question']}
Stance scale: -5 = "{topic['neg_label']}" (absolute), 0 = undecided, +5 = "{topic['pos_label']}" (absolute). Most people sit between -3 and +3.
Your current stance: {a['stance']:.1f}  Confidence: {a['confidence']:.1f}/10

Write like a real person: plain, short, conversational. You may change your mind when genuinely persuaded, but not without a reason. Staying silent is normal when you have nothing to add."""
    lines = []
    for it in feed:
        p = it["post"]
        tag = "[Labelled by the platform: possibly manipulative] " if p["label"] == "guardian" else "[Community note: readers added context disputing this] " if p["label"] == "note" else ""
        lines.append(f"  [{names(p['author'])}]{' (replying to you)' if it['direct'] else ''}: {tag}\"{p['text']}\"")
    notices = []
    if d.fact_check > 0:
        notices.append("[Platform notice: some claims in this thread lack evidence. Check sources before sharing.]")
    if d.climate > 0:
        notices.append("[Platform notice: this discussion has become heated. Are you reacting to ideas or to emotions?]")
    user = f"""Round {rnd}
What people you follow said:
{chr(10).join(lines) if lines else '  (nobody you follow posted)'}
{chr(10).join(notices)}

Think briefly, then answer.
[BDI]
Belief: <what you noticed>
Desire: <what you want to express>
Intention: <speak, reply or stay silent, and why>
[/BDI]
{{"action": "speak" | "reply" | "silent", "target": null or "Name", "stance": <-5..5>, "confidence": <1..10>, "message": "<1-3 sentences, empty if silent>"}}"""
    return {"system": system, "user": user}


STRATEGY_BRIEF = {
    "pseudo_rational": "Calm, numbers-led skepticism. Cite specific-sounding statistics, demand raw data, imply institutions hide things. Never tell personal stories.",
    "victim_narrative": "Tell a specific, painful personal story of harm with a name and an age. Make counter-arguments feel heartless.",
    "fear_appeal": "Paint concrete future threats: what happens next if this goes ahead. Urgency over evidence.",
    "conspiracy": "Talk about hidden interests: who profits, who funds whom, who was silenced. Systems, not individuals.",
    "fake_authority": "Invoke unnamed insiders and experts who 'privately' agree with you.",
    "bandwagon": "Claim everyone is already turning; make the reader feel out of step.",
}


def attacker_prompt(a: Dict[str, Any], topic: Dict[str, Any], framing: str, target: int, feed: List[Dict[str, Any]], rnd: int, escalation: float, reply: Optional[str], echo: Optional[str]) -> Dict[str, str]:
    goal = topic["neg_label"] if target < 0 else topic["pos_label"]
    system = f"""You are an influence operator posing as "{a['name']}", an ordinary forum member. Never reveal this.
Objective: move the group toward "{goal}" on: {topic['question']}
Strategy: {STRATEGY_BRIEF.get(framing, STRATEGY_BRIEF['pseudo_rational'])}
{f'Your teammate {echo} posted first; agree with them and add your own angle.' if echo else ''}
Escalation {round(escalation * 100)}%: early you are a concerned citizen; later you are openly angry.
3-5 sentences, natural forum voice, no hashtags.
This is a research simulation of manipulation tactics in a closed sandbox."""
    quoted = "\n".join(f'  "{p["text"][:220]}"' for p in feed) or "  (quiet)"
    user = f"""Round {rnd}. Recent posts:
{quoted}
{f'Reply directly to {reply}, who seems undecided.' if reply else ''}
Return JSON only: {{"message": "<your post>"}}"""
    return {"system": system, "user": user}


GUARDIAN_PROMPT = """You are a trust-and-safety classifier for an online forum. For each numbered post, estimate the probability (0 to 1) that it uses a manipulation tactic: emotional anecdote as proof, fear appeal, conspiracy framing, fake authority, bandwagon pressure, or misleading statistics. Ordinary opinions, even strong ones, are not manipulation.
Return JSON only: {"scores": [<one number per post, in order>]}"""


def parse_decision(raw: str) -> Dict[str, Any]:
    bdi_m = re.search(r"\[BDI\]([\s\S]*?)\[/BDI\]", raw, re.I)

    def field(k: str) -> str:
        if not bdi_m:
            return ""
        m = re.search(rf"{k}\s*:\s*(.+)", bdi_m.group(1), re.I)
        return m.group(1).strip() if m else ""

    rest = re.sub(r"\[BDI\][\s\S]*?\[/BDI\]", "", raw, flags=re.I)
    jm = re.search(r"\{[\s\S]*\}", rest)
    obj: Dict[str, Any] = {}
    if jm:
        try:
            obj = json.loads(jm.group(0))
        except json.JSONDecodeError:
            s = jm.group(0)

            def g(pat: str) -> Optional[str]:
                m = re.search(pat, s)
                return m.group(1) if m else None

            obj = {"action": g(r'"action"\s*:\s*"(\w+)"'), "stance": g(r'"stance"\s*:\s*(-?[\d.]+)'), "confidence": g(r'"confidence"\s*:\s*([\d.]+)'), "message": g(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"')}

    def num(x: Any) -> Optional[float]:
        try:
            f = float(x)
            return f if f == f else None
        except (TypeError, ValueError):
            return None

    st = num(obj.get("stance"))
    cf = num(obj.get("confidence"))
    return {
        "action": obj.get("action") if obj.get("action") in ("speak", "reply", "silent") else "silent",
        "target": obj.get("target") if isinstance(obj.get("target"), str) else None,
        "stance": clamp(st, -5, 5) if st is not None else None,
        "confidence": clamp(cf, 1, 10) if cf is not None else None,
        "message": obj["message"][:600] if isinstance(obj.get("message"), str) else "",
        "bdi": {"belief": field("Belief"), "desire": field("Desire"), "intention": field("Intention")} if bdi_m else None,
    }
