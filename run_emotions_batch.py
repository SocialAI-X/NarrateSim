"""Batch emotion analysis — classify 10 messages per API call for 10x speedup."""

import asyncio
import json
import os
import sys
import time
import glob
import re
import shutil
from collections import Counter, defaultdict

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

from src.llm_client import LLMClient
from src.emotion_analysis import CATEGORIES, NEGATIVE_CATEGORIES, POSITIVE_CATEGORIES, compute_emotion_metrics

REUSE_DIRS = [
    "results/full_study_20260521_v3",
]

BATCH_SIZE = 10
MAX_CONCURRENT = 10

BATCH_SYSTEM_PROMPT = """\
Classify the emotional tone of each online discussion message into ONE category.

Categories (Plutchik's model, strictly defined):
- anger: hostile, aggressive, contemptuous, insulting, mocking, personally attacking. Requires EXPLICIT hostile language.
- fear: intense anxiety, alarm, panic, dread about imminent catastrophic threats. Requires urgency/panic BEYOND normal concern.
- sadness: deep disappointment, hopelessness, resignation, defeat, grief. Requires genuine despair.
- disgust: visceral moral revulsion with EXPLICIT revulsion language ("sickening", "disgusting", "revolting").
- trust: actively endorsing, praising, or expressing confidence in another person's view.
- anticipation: genuinely hopeful, curious, optimistic, excited about possibilities.
- surprise: genuinely shocked, caught off guard, cognitive dissonance.
- neutral: the DEFAULT. Stating facts, opinions calmly, disagreement, policy discussion, questions, arguments.

CALIBRATION: NEUTRAL is the default. Only classify as emotional when there is CLEAR, STRONG emotional language.
- "I think X is wrong/bad" = neutral. "I'm a bit worried" = neutral. Firm disagreement = neutral.
- Describing negative consequences factually = neutral. Moral disagreement = neutral unless visceral revulsion words."""

BATCH_USER_PROMPT = """Classify each message below. Respond with ONLY a JSON array of categories, one per message.
Example response: ["neutral", "anger", "neutral", "trust", "fear"]

Messages:
{messages_text}

Respond with ONLY the JSON array (no explanation):"""


def parse_batch_response(raw: str, expected_count: int) -> list:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            result = []
            for item in arr:
                if isinstance(item, str) and item.lower() in CATEGORIES:
                    result.append(item.lower())
                elif isinstance(item, dict) and "category" in item:
                    c = item["category"].lower()
                    result.append(c if c in CATEGORIES else "neutral")
                else:
                    result.append("neutral")
            while len(result) < expected_count:
                result.append("neutral")
            return result[:expected_count]
    except json.JSONDecodeError:
        pass
    cats = re.findall(r'"(\w+)"', raw)
    result = []
    for c in cats:
        result.append(c.lower() if c.lower() in CATEGORIES else "neutral")
    while len(result) < expected_count:
        result.append("neutral")
    return result[:expected_count]


async def classify_messages_batch(messages, llm):
    """Classify all messages using batch API calls (10 msgs per call)."""
    all_categories = ["neutral"] * len(messages)

    chunks = []
    for i in range(0, len(messages), BATCH_SIZE):
        chunk_msgs = messages[i:i + BATCH_SIZE]
        chunks.append((i, chunk_msgs))

    async def process_chunk(start_idx, chunk_msgs):
        msgs_text = "\n".join(f"[{j+1}] {m[:300]}" for j, m in enumerate(chunk_msgs))
        try:
            raw = await llm.query(
                BATCH_SYSTEM_PROMPT,
                BATCH_USER_PROMPT.format(messages_text=msgs_text),
                temperature=0.2,
                max_tokens=200,
            )
            cats = parse_batch_response(raw, len(chunk_msgs))
            return start_idx, cats
        except Exception:
            return start_idx, ["neutral"] * len(chunk_msgs)

    for batch_start in range(0, len(chunks), MAX_CONCURRENT):
        batch = chunks[batch_start:batch_start + MAX_CONCURRENT]
        tasks = [process_chunk(si, cm) for si, cm in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                continue
            start_idx, cats = r
            for j, cat in enumerate(cats):
                if start_idx + j < len(all_categories):
                    all_categories[start_idx + j] = cat
        done_msgs = min((batch_start + len(batch)) * BATCH_SIZE, len(messages))
        print(f"      {done_msgs}/{len(messages)} classified", flush=True)

    return all_categories


async def process_experiment(exp_dir, llm):
    rf = os.path.join(exp_dir, "results.json")
    ef = os.path.join(exp_dir, "emotion_analysis.json")

    if not os.path.exists(rf):
        return None
    if os.path.exists(ef):
        with open(ef, "r", encoding="utf-8") as f:
            return json.load(f)

    with open(rf, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages, agent_ids, round_nums = [], [], []
    for rd in data.get("rounds", []):
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

    if not messages:
        return None

    print(f"    {len(messages)} messages, ~{len(messages)//BATCH_SIZE} API calls...", flush=True)
    categories = await classify_messages_batch(messages, llm)

    emotion_results = []
    for idx, cat in enumerate(categories):
        emotion_results.append({
            "agent_id": agent_ids[idx],
            "round_num": round_nums[idx],
            "message": messages[idx][:200],
            "category": cat,
            "is_negative": cat in NEGATIVE_CATEGORIES,
            "is_positive": cat in POSITIVE_CATEGORIES,
        })

    metrics = compute_emotion_metrics(emotion_results)
    with open(ef, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return metrics


def find_reuse_emotion(exp_name, study):
    for d in REUSE_DIRS:
        p = os.path.join(d, study, exp_name, "emotion_analysis.json")
        if os.path.exists(p):
            return p
    return None


async def main():
    base = sorted(glob.glob("results/full_run_20260518_1546*"))[-1]
    print(f"Base dir: {base}", flush=True)
    print(f"Batch: {BATCH_SIZE} msgs/call, {MAX_CONCURRENT} concurrent calls", flush=True)

    llm = LLMClient(model="Pro/deepseek-ai/DeepSeek-V3.2", max_concurrent=MAX_CONCURRENT)

    pending = []
    cached = 0
    for study in sorted(os.listdir(base)):
        sp = os.path.join(base, study)
        if not os.path.isdir(sp) or study.startswith("comparative"):
            continue
        for exp in sorted(os.listdir(sp)):
            ep = os.path.join(sp, exp)
            rf = os.path.join(ep, "results.json")
            ef = os.path.join(ep, "emotion_analysis.json")
            if not os.path.exists(rf):
                continue
            if os.path.exists(ef):
                cached += 1
                continue
            reuse = find_reuse_emotion(exp, study)
            if reuse:
                shutil.copy2(reuse, ef)
                cached += 1
                print(f"  [REUSE] {exp}", flush=True)
            else:
                pending.append((study, exp, ep))

    print(f"\nCached: {cached}, Need analysis: {len(pending)}", flush=True)
    print(f"Estimated: ~{len(pending) * 1300 // BATCH_SIZE // MAX_CONCURRENT * 90 // 60} min\n", flush=True)

    for idx, (study, exp, ep) in enumerate(pending):
        print(f"  [{idx+1}/{len(pending)}] {exp}", flush=True)
        t0 = time.time()
        try:
            metrics = await process_experiment(ep, llm)
            if metrics:
                elapsed = time.time() - t0
                print(f"    DONE neg={metrics['negative_ratio']:.1%} "
                      f"anger={metrics['anger_ratio']:.1%} ({elapsed:.0f}s)\n", flush=True)
        except Exception as e:
            print(f"    ERROR: {e}\n", flush=True)

    print(f"\nAll emotion analyses complete!", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
