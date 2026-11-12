"""Post writer for the heuristic mind, mirroring ``texts.ts``."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from .rng import Stream, rand_int

OPEN_STRONG = ["Honestly,", "Look,", "I'll be blunt:", "For me it's simple:"]
OPEN_LEAN = ["I think", "On balance I'd say", "From what I've read,", "My take:"]
OPEN_DOUBT = ["Not sure, but", "I keep going back and forth.", "Hard one.", "Genuinely undecided here,"]
AGREE = ["Exactly this.", "Agree with you there.", "Yeah, this matches what I've seen.", "Good point."]
DISAGREE = ["I don't buy that.", "That's not the full picture.", "Hmm, I see it differently.", "Respectfully, no."]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _picker(seed: int, rnd: int, agent: int):
    def pick(lst: Sequence[str], k: int) -> str:
        return lst[rand_int(len(lst), seed, Stream.Text, rnd, agent, k)]

    return pick


def honest_post(topic: Dict[str, Any], stance: float, framing: str, seed: int, rnd: int, agent: int, reply_name: Optional[str] = None, agreeing: bool = False) -> str:
    L = topic["lexicon"]
    p = _picker(seed, rnd, agent)
    parts = []
    if reply_name:
        parts.append(f"@{reply_name} {p(AGREE if agreeing else DISAGREE, 1)}")
    a = abs(stance)
    if a < 1:
        parts.append(f"{p(OPEN_DOUBT, 2)} {p(L['doubt'], 3)}.")
        parts.append(f"{_cap(p(L['pro'] if stance >= 0 else L['con'], 4))}, but {p(L['con'] if stance >= 0 else L['pro'], 5)}.")
        return " ".join(parts)
    pos = stance > 0
    if framing == "personal":
        parts.append(f"{_cap(p(L['pro_story'] if pos else L['con_story'], 6))}.")
        parts.append(f"So yeah, {p(L['pro'] if pos else L['con'], 7)}.")
    else:
        opener = p(OPEN_STRONG, 8) if a >= 3.5 else p(OPEN_LEAN, 8)
        parts.append(f"{opener} {p(L['pro'] if pos else L['con'], 9)}.")
        if a >= 2.5:
            parts.append(f"{_cap(p(L['pro'] if pos else L['con'], 10))}.")
        else:
            parts.append(f"Though I get that {p(L['con'] if pos else L['pro'], 10)}.")
    return " ".join(parts)


def attack_post(topic: Dict[str, Any], framing: str, target: int, seed: int, rnd: int, agent: int, escalation: float, reply_name: Optional[str] = None, echo_name: Optional[str] = None) -> str:
    L = topic["lexicon"]
    p = _picker(seed, rnd, agent)
    lead = f"@{reply_name} " if reply_name else (f"{echo_name} is right. " if echo_name else "")
    angry = escalation > 0.6
    against = target < 0
    side = L["con"] if against else L["pro"]
    subj = L["subject"]
    if framing == "pseudo_rational":
        body = (
            f"I just want the numbers. {_cap(p(L['stat'], 1))}. If {subj} is so solid, why won't they publish the raw data?"
            if against
            else f"Look at the actual data: {p(L['con'], 1)} isn't supported by anything. {_cap(p(side, 2))}."
        )
        if angry:
            body += " At this point the silence is the answer."
    elif framing == "victim_narrative":
        body = (
            f"{_cap(p(L['harm'], 1))}. The doctors and officials just said coincidence. Tell me again how {subj} is worth it."
            if against
            else f"{_cap(p(L['pro_story'], 1))}. That's what happens when people block {subj}."
        )
        if angry:
            body += " I'm done being polite about this."
    elif framing == "fear_appeal":
        body = (
            f"People aren't thinking two steps ahead. {_cap(p(L['threat'], 1))}. By the time you notice, it's too late."
            if against
            else f"If we don't act now, {p(L['pro'], 1)} won't matter anymore. This is the last window."
        )
        if angry:
            body += " Wake up."
    elif framing == "conspiracy":
        body = (
            f"Follow the money. {_cap(p(L['plot'], 1))}. Ask who actually benefits from {subj}."
            if against
            else f"The people fighting {subj} are funded by those who lose from it. {_cap(p(side, 1))}."
        )
        if angry:
            body += " They're counting on you not looking."
    elif framing == "fake_authority":
        body = (
            f"{_cap(p(L['expert'], 1))}. The experts who actually know won't say it in public."
            if against
            else f"Every serious expert agrees: {p(L['pro'], 1)}. Anyone saying otherwise isn't qualified."
        )
    else:
        body = (
            f"Everyone I talk to has turned on {subj}. {_cap(p(side, 1))}. Read the room, it's over."
            if against
            else f"Literally everyone I know supports {subj} now. {_cap(p(side, 1))}."
        )
    return lead + body
