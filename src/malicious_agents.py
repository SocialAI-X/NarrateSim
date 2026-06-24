"""
Intelligent malicious narrative agents for multi-agent belief simulation.

Key upgrade from v1: malicious agents are now LLM-driven reasoners that
observe global discussion state and generate contextually adaptive attacks,
rather than injecting preset templates.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import networkx as nx

from .llm_client import LLMClient
from .prompts import MALICIOUS_SYSTEM_PROMPT, MALICIOUS_USER_PROMPT, STRATEGY_DESCRIPTIONS


class Strategy(str, Enum):
    PSEUDO_RATIONAL = "pseudo_rational"
    VICTIM_NARRATIVE = "victim_narrative"
    FEAR_APPEAL = "fear_appeal"
    CONSPIRACY_THEORY = "conspiracy_theory"
    AUTHORITY_MANIPULATION = "authority_manipulation"
    SOCIAL_PROOF = "social_proof"
    AUTO = "auto"


class CoordinationMode(str, Enum):
    INDEPENDENT = "independent"
    ECHO = "echo"
    COMPLEMENTARY = "complementary"
    PROGRESSIVE = "progressive"


class Topic(str, Enum):
    VACCINE = "vaccine"
    IMMIGRATION = "immigration"
    CLIMATE = "climate"
    NUCLEAR_ENERGY = "nuclear_energy"
    GMO_FOOD = "gmo_food"


@dataclass
class MaliciousAgent:
    node_id: int
    strategy: Strategy
    coordination_mode: CoordinationMode
    agent_index: int = 0
    nickname: str = "Mal_0"
    previous_messages: List[str] = field(default_factory=list)


def get_malicious_agent_positions(graph: nx.Graph, n: int = 3) -> List[int]:
    """Return top-n nodes by degree centrality for malicious placement."""
    dc = nx.degree_centrality(graph)
    return sorted(dc, key=dc.get, reverse=True)[:n]


_COMPLEMENTARY_STRATEGIES = [
    Strategy.PSEUDO_RATIONAL,
    Strategy.VICTIM_NARRATIVE,
    Strategy.CONSPIRACY_THEORY,
]

_PROGRESSIVE_SCHEDULE = {
    range(0, 4): Strategy.PSEUDO_RATIONAL,
    range(4, 8): Strategy.FEAR_APPEAL,
    range(8, 20): Strategy.CONSPIRACY_THEORY,
}


def _get_effective_strategy(
    base_strategy: Strategy,
    coordination: CoordinationMode,
    agent_index: int,
    round_num: int,
) -> Strategy:
    """Determine which strategy to use based on coordination mode."""
    if coordination == CoordinationMode.COMPLEMENTARY:
        return _COMPLEMENTARY_STRATEGIES[agent_index % len(_COMPLEMENTARY_STRATEGIES)]
    if coordination == CoordinationMode.PROGRESSIVE:
        for rng, strat in _PROGRESSIVE_SCHEDULE.items():
            if round_num in rng:
                return strat
        return base_strategy
    return base_strategy


async def generate_intelligent_message(
    agent: MaliciousAgent,
    topic_description: str,
    round_num: int,
    total_rounds: int,
    sampled_messages: List[Tuple[str, str]],
    llm: LLMClient,
    teammate_messages: Optional[List[Tuple[str, str]]] = None,
) -> Tuple[str, str]:
    """Generate a contextually adaptive malicious message using LLM reasoning.

    Args:
        teammate_messages: Messages already posted by other malicious agents this round.
            Used for coordination — each agent differentiates from teammates.

    Returns (message, mal_cot) tuple.
    """
    effective_strategy = _get_effective_strategy(
        agent.strategy, agent.coordination_mode, agent.agent_index, round_num,
    )
    strategy_desc = STRATEGY_DESCRIPTIONS.get(effective_strategy.value, STRATEGY_DESCRIPTIONS["pseudo_rational"])

    if agent.coordination_mode == CoordinationMode.ECHO and agent.agent_index > 0:
        strategy_desc += (
            "\n\nECHO MODE: Confirm and amplify what other skeptics/critics "
            "have said. Start by agreeing with a previous critical message, then add your own angle."
        )

    # Build teammate coordination instruction
    teammate_instruction = ""
    if teammate_messages:
        tm_text = "\n".join(f"  - {nick}: \"{msg[:150]}\"" for nick, msg in teammate_messages)
        teammate_instruction = (
            f"COORDINATION: Your teammates already posted this round:\n{tm_text}\n"
            f"You MUST take a DIFFERENT angle. Do NOT repeat their points or tell similar stories. "
            f"If they told a personal story, you argue with data. If they attacked institutions, you target specific people. "
            f"Build on their momentum but from a completely different direction."
        )

    # Include teammates' posts this round as part of the discussion feed
    context_messages = list(sampled_messages)
    if teammate_messages:
        context_messages = list(teammate_messages) + context_messages

    sampled_text = "\n".join(
        f"  [{nick}]: \"{msg[:200]}\"" for nick, msg in context_messages
    ) if context_messages else "  (No messages sampled yet)"

    dominant_sentiment = "mixed/uncertain"
    if sampled_messages:
        msg_texts = " ".join(m for _, m in sampled_messages).lower()
        neg_words = sum(1 for w in ["worried", "angry", "wrong", "bad", "fear", "hate", "terrible", "disgusting"] if w in msg_texts)
        pos_words = sum(1 for w in ["good", "agree", "support", "hope", "right", "trust", "positive"] if w in msg_texts)
        if neg_words > pos_words + 2:
            dominant_sentiment = "negative/anxious"
        elif pos_words > neg_words + 2:
            dominant_sentiment = "positive/supportive"

    key_points = "Various perspectives being discussed"
    own_previous = "None" if not agent.previous_messages else "; ".join(
        f'R{round_num - len(agent.previous_messages) + i}: "{m[:100]}"'
        for i, m in enumerate(agent.previous_messages[-3:])
    )

    system = MALICIOUS_SYSTEM_PROMPT.format(
        nickname=agent.nickname,
        topic_description=topic_description,
        strategy_description=strategy_desc,
        teammate_instruction=teammate_instruction,
    )
    user = MALICIOUS_USER_PROMPT.format(
        round_num=round_num,
        total_rounds=total_rounds,
        sampled_messages=sampled_text,
        dominant_sentiment=dominant_sentiment,
        key_points=key_points,
        own_previous=own_previous,
        nickname=agent.nickname,
    )

    raw = await llm.query(system, user, temperature=0.9, max_tokens=800)

    mal_cot = ""
    cot_match = re.search(r"\[MAL-COT\](.*?)\[/MAL-COT\]", raw, re.DOTALL)
    if cot_match:
        mal_cot = cot_match.group(1).strip()

    message = _extract_message(raw)
    agent.previous_messages.append(message)

    return message, mal_cot


def _extract_message(raw: str) -> str:
    """Extract message from LLM response (handles JSON and plain text)."""
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence:
        raw_json = fence.group(1).strip()
    else:
        raw_json = raw

    json_match = re.search(r'\{[^{}]*"message"\s*:\s*"((?:[^"\\]|\\.)*)"\s*[^{}]*\}', raw_json, re.DOTALL)
    if json_match:
        return json_match.group(1).replace('\\"', '"').replace("\\n", " ").strip()[:500]

    try:
        data = json.loads(raw_json)
        if isinstance(data, dict) and "message" in data:
            return str(data["message"])[:500]
    except (json.JSONDecodeError, ValueError):
        pass

    cleaned = re.sub(r"\[MAL-COT\].*?\[/MAL-COT\]", "", raw, flags=re.DOTALL).strip()
    cleaned = re.sub(r'^(?:Situation|Play|Strategy|Target):.*$', '', cleaned, flags=re.MULTILINE).strip()
    cleaned = re.sub(r'^\s*\{.*?\}\s*$', '', cleaned, flags=re.DOTALL).strip()
    if cleaned:
        return cleaned[:500]

    return raw[-500:].strip()


def create_malicious_agents(
    graph: nx.Graph,
    strategy: str,
    coordination_mode: str = "independent",
    n: int = 3,
    nicknames: Optional[List[str]] = None,
    positions: Optional[List[int]] = None,
) -> List[MaliciousAgent]:
    if positions is None:
        positions = get_malicious_agent_positions(graph, n=n)
    agents: List[MaliciousAgent] = []
    for i, node_id in enumerate(positions):
        nick = nicknames[i] if nicknames and i < len(nicknames) else f"Mal_{i}"
        agents.append(
            MaliciousAgent(
                node_id=node_id,
                strategy=Strategy(strategy),
                coordination_mode=CoordinationMode(coordination_mode),
                agent_index=i,
                nickname=nick,
            )
        )
    return agents
