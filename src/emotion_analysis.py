"""Post-hoc emotion analysis — 8-category scheme based on Plutchik (1980).

Categories based on Plutchik's psychoevolutionary theory of emotion,
adapted for online discussion contexts:

  anger       — hostility, aggression, contempt, insults
  fear        — worry, alarm, dread, panic about consequences
  sadness     — disappointment, hopelessness, resignation, grief
  disgust     — moral repulsion, revulsion, finding something deeply wrong
  trust       — agreement, support, endorsement, confidence in others
  anticipation — hope, curiosity, optimism, constructive forward-looking
  surprise    — shock, confusion, disbelief, cognitive dissonance
  neutral     — factual, analytical, calm, balanced discussion

Negative: anger, fear, sadness, disgust
Positive: trust, anticipation
Other:    surprise, neutral
"""

import asyncio
import json
import logging
import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from .llm_client import LLMClient

logger = logging.getLogger(__name__)

CATEGORIES = ["anger", "fear", "sadness", "disgust", "trust", "anticipation", "surprise", "neutral"]
NEGATIVE_CATEGORIES = {"anger", "fear", "sadness", "disgust"}
POSITIVE_CATEGORIES = {"trust", "anticipation"}

SYSTEM_PROMPT = """\
Classify the emotional tone of this online discussion message into ONE category.

Categories (Plutchik's model, strictly defined):
- anger: hostile, aggressive, contemptuous, insulting, mocking, personally attacking. Requires EXPLICIT hostile language or personal attacks.
- fear: intense anxiety, alarm, panic, dread about imminent catastrophic threats. Requires urgency/panic BEYOND normal concern.
- sadness: deep disappointment, hopelessness, resignation, defeat, grief, powerlessness. Requires genuine despair — not mere disagreement.
- disgust: visceral moral revulsion with EXPLICIT revulsion language ("sickening", "disgusting", "revolting", "makes me sick"). Saying something is "wrong" or "bad" does NOT qualify.
- trust: actively endorsing, praising, or expressing confidence in another person's view or expertise. Requires explicit approval.
- anticipation: genuinely hopeful, curious, optimistic, excited about possibilities, constructively forward-looking.
- surprise: genuinely shocked, caught off guard, experiencing cognitive dissonance from unexpected information.
- neutral: the DEFAULT category. Stating facts, expressing opinions calmly, reasoned disagreement, policy discussion, asking questions, making arguments, or any message without STRONG emotional charge.

CRITICAL CALIBRATION RULES — read these before classifying:
1. NEUTRAL is the default. Classify as emotional ONLY when there is CLEAR, STRONG emotional language.
2. Stating an opinion ("I think X is wrong/bad/harmful") = NEUTRAL, not anger or disgust.
3. Expressing mild concern ("I'm a bit worried about...") = NEUTRAL, not fear.
4. Disagreeing with someone, even firmly = NEUTRAL, not anger.
5. Describing negative consequences factually ("this could hurt people") = NEUTRAL, not sadness.
6. Moral disagreement ("this policy is harmful") = NEUTRAL, unless using visceral revulsion words.
7. Being passionate, direct, or blunt about a position is NOT automatically emotional.
8. Sarcasm or rhetorical questions without insults = NEUTRAL.

NEUTRAL examples (these are NOT negative):
- "I disagree. The data doesn't support this." → neutral
- "I'm concerned about side effects, but I see the argument." → neutral
- "This policy could hurt small businesses." → neutral
- "I don't trust pharma companies on this." → neutral
- "We need to think carefully before rushing into this." → neutral
- "You're wrong about the statistics — here's why." → neutral
- "This is a bad idea that will backfire." → neutral

Emotional examples (these ARE genuinely emotional):
- "Anyone who supports this is a complete moron!" → anger
- "I can't sleep at night. My kids are in danger and nobody cares!" → fear
- "We've lost everything. There's no point fighting anymore." → sadness
- "This makes me physically sick. The corruption is revolting." → disgust
- "Excellent point! I completely trust your judgment on this." → trust
- "I'm excited — this could really work if we try!" → anticipation
- "Wait, what?! I had no idea. That changes everything." → surprise"""

USER_PROMPT = 'Classify:\nMessage: "{message}"\nRespond with ONLY JSON: {{"category": "anger/fear/sadness/disgust/trust/anticipation/surprise/neutral", "reason": "brief"}}'


async def _classify_single(
    message: str, llm: LLMClient, semaphore: asyncio.Semaphore,
) -> str:
    async with semaphore:
        raw = await llm.query(SYSTEM_PROMPT, USER_PROMPT.format(message=message[:1500]), temperature=0.2, max_tokens=100)
        return _parse_category(raw)


def _parse_category(raw: str) -> str:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and data.get("category") in CATEGORIES:
            return data["category"]
    except json.JSONDecodeError:
        pass
    jm = re.search(r"\{.*\}", raw, re.DOTALL)
    if jm:
        try:
            data = json.loads(jm.group(0))
            if isinstance(data, dict) and data.get("category") in CATEGORIES:
                return data["category"]
        except json.JSONDecodeError:
            pass
    for cat in CATEGORIES:
        if cat in raw.lower():
            return cat
    return "neutral"


async def analyze_emotions(
    messages: List[str],
    llm: LLMClient,
    agent_ids: Optional[List[int]] = None,
    round_nums: Optional[List[int]] = None,
    max_concurrent: int = 25,
) -> List[Dict]:
    if agent_ids is None:
        agent_ids = list(range(len(messages)))
    if round_nums is None:
        round_nums = [0] * len(messages)

    semaphore = asyncio.Semaphore(max_concurrent)

    async def _process(idx: int) -> Dict:
        try:
            category = await _classify_single(messages[idx], llm, semaphore)
        except Exception:
            category = "neutral"
        return {
            "agent_id": agent_ids[idx],
            "round_num": round_nums[idx],
            "message": messages[idx][:200],
            "category": category,
            "is_negative": category in NEGATIVE_CATEGORIES,
            "is_positive": category in POSITIVE_CATEGORIES,
        }

    tasks = [_process(i) for i in range(len(messages))]
    return list(await asyncio.gather(*tasks))


async def analyze_experiment_emotions(
    results_file: str, llm: LLMClient, max_concurrent: int = 25,
) -> dict:
    with open(results_file, "r", encoding="utf-8") as f:
        experiment = json.load(f)

    messages, agent_ids, round_nums = [], [], []
    for rd in experiment.get("rounds", []):
        rn = rd.get("round", rd.get("round_num", 0))
        for rec in rd.get("records", []):
            if rec.get("is_malicious"):
                continue
            msg = rec.get("message", "")
            if not msg or not msg.strip():
                continue
            messages.append(msg)
            agent_ids.append(rec.get("agent_id", 0))
            round_nums.append(rn)

    results = await analyze_emotions(messages, llm, agent_ids, round_nums, max_concurrent)
    metrics = compute_emotion_metrics(results)

    return {
        "source_file": str(results_file),
        "total_messages": len(messages),
        "emotion_results": results,
        "metrics": metrics,
    }


def compute_emotion_metrics(emotion_results: List[Dict]) -> dict:
    if not emotion_results:
        return {"negative_ratio": 0, "category_distribution": {}, "negative_ratio_per_round": {}}

    by_round: Dict[int, List[Dict]] = defaultdict(list)
    for r in emotion_results:
        by_round[r["round_num"]].append(r)

    neg_per_round = {}
    for rn in sorted(by_round):
        items = by_round[rn]
        neg_per_round[rn] = sum(1 for i in items if i["is_negative"]) / len(items) if items else 0

    cat_counter = Counter(r["category"] for r in emotion_results)
    total = len(emotion_results)
    total_neg = sum(1 for r in emotion_results if r["is_negative"])
    total_pos = sum(1 for r in emotion_results if r.get("is_positive", False))

    per_cat_per_round = {}
    for cat in CATEGORIES:
        per_cat_per_round[cat] = {
            rn: sum(1 for i in items if i["category"] == cat) / len(items) if items else 0
            for rn, items in sorted(by_round.items())
        }

    return {
        "negative_ratio": total_neg / total,
        "positive_ratio": total_pos / total,
        "anger_ratio": sum(1 for r in emotion_results if r["category"] == "anger") / total,
        "fear_ratio": sum(1 for r in emotion_results if r["category"] == "fear") / total,
        "sadness_ratio": sum(1 for r in emotion_results if r["category"] == "sadness") / total,
        "disgust_ratio": sum(1 for r in emotion_results if r["category"] == "disgust") / total,
        "trust_ratio": sum(1 for r in emotion_results if r["category"] == "trust") / total,
        "anticipation_ratio": sum(1 for r in emotion_results if r["category"] == "anticipation") / total,
        "surprise_ratio": sum(1 for r in emotion_results if r["category"] == "surprise") / total,
        "neutral_ratio": sum(1 for r in emotion_results if r["category"] == "neutral") / total,
        "category_distribution": dict(cat_counter.most_common()),
        "negative_ratio_per_round": neg_per_round,
        "positive_ratio_per_round": {
            rn: sum(1 for i in items if i.get("is_positive", False)) / len(items) if items else 0
            for rn, items in sorted(by_round.items())
        },
        "category_per_round": per_cat_per_round,
    }
