"""Emotion analysis for all v3 experiments."""
import asyncio, json, os, sys, time, re
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace', buffering=1)

from src.llm_client import LLMClient, _GlobalStats, _GlobalRateLimiter
from src.emotion_analysis import (CATEGORIES, NEGATIVE_CATEGORIES, POSITIVE_CATEGORIES,
                                   compute_emotion_metrics)

V3_DIR = Path("results/full_study_20260521_v3")
BATCH_SIZE = 10
MAX_CONCURRENT = 15

BATCH_SYSTEM_PROMPT = """\
Classify the emotional tone of each online discussion message into ONE category.

Categories (Plutchik's model, strictly defined):
- anger: hostile, aggressive, contemptuous, insulting, mocking, personally attacking.
- fear: intense anxiety, alarm, panic, dread about imminent catastrophic threats.
- sadness: deep disappointment, hopelessness, resignation, defeat, grief.
- disgust: visceral moral revulsion with EXPLICIT revulsion language.
- trust: actively endorsing, praising, or expressing confidence in another person's view.
- anticipation: genuinely hopeful, curious, optimistic, excited about possibilities.
- surprise: genuinely shocked, caught off guard, cognitive dissonance.
- neutral: the DEFAULT. Stating facts, opinions calmly, disagreement, policy discussion.

CALIBRATION: NEUTRAL is the default. Only classify as emotional with CLEAR, STRONG emotional language."""

BATCH_USER_PROMPT = """Classify each message below. Respond with ONLY a JSON array of categories.
Example: ["neutral", "anger", "neutral", "trust", "fear"]

Messages:
{messages_text}

JSON array:"""


def parse_batch(raw, n):
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            result = [a.lower() if isinstance(a, str) and a.lower() in CATEGORIES else "neutral" for a in arr]
            while len(result) < n:
                result.append("neutral")
            return result[:n]
    except Exception:
        pass
    cats = re.findall(r'"(\w+)"', raw)
    result = [c.lower() if c.lower() in CATEGORIES else "neutral" for c in cats]
    while len(result) < n:
        result.append("neutral")
    return result[:n]


async def classify_batch(messages, llm):
    all_cats = ["neutral"] * len(messages)
    chunks = [(i, messages[i:i+BATCH_SIZE]) for i in range(0, len(messages), BATCH_SIZE)]

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async def process(start, chunk):
        async with sem:
            text = "\n".join(f"[{j+1}] {m[:300]}" for j, m in enumerate(chunk))
            try:
                raw = await llm.query(BATCH_SYSTEM_PROMPT,
                                      BATCH_USER_PROMPT.format(messages_text=text),
                                      temperature=0.2, max_tokens=200)
                return start, parse_batch(raw, len(chunk))
            except Exception:
                return start, ["neutral"] * len(chunk)

    for batch_start in range(0, len(chunks), MAX_CONCURRENT):
        batch = chunks[batch_start:batch_start + MAX_CONCURRENT]
        results = await asyncio.gather(*[process(s, c) for s, c in batch], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                continue
            si, cats = r
            for j, cat in enumerate(cats):
                if si + j < len(all_cats):
                    all_cats[si + j] = cat
    return all_cats


async def process_experiment(exp_dir, llm):
    rf = exp_dir / "results.json"
    ef = exp_dir / "emotion_analysis.json"
    if not rf.exists():
        return None
    if ef.exists():
        return json.loads(ef.read_text(encoding="utf-8"))

    data = json.loads(rf.read_text(encoding="utf-8"))
    messages, agent_ids, round_nums = [], [], []
    for rd in data.get("rounds", []):
        rn = rd.get("round", 0)
        for rec in rd.get("records", []):
            if rec.get("is_malicious"):
                continue
            msg = rec.get("message", "")
            if msg and msg.strip():
                messages.append(msg)
                agent_ids.append(rec.get("agent_id", 0))
                round_nums.append(rn)

    if not messages:
        return None

    print(f"    {len(messages)} msgs, ~{len(messages)//BATCH_SIZE} calls...", flush=True)
    cats = await classify_batch(messages, llm)

    emotion_results = [{
        "agent_id": agent_ids[i], "round_num": round_nums[i],
        "message": messages[i][:200], "category": cats[i],
        "is_negative": cats[i] in NEGATIVE_CATEGORIES,
        "is_positive": cats[i] in POSITIVE_CATEGORIES,
    } for i in range(len(cats))]

    metrics = compute_emotion_metrics(emotion_results)
    ef.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


async def main():
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(200)
    llm = LLMClient(model="Pro/deepseek-ai/DeepSeek-V3.2", max_concurrent=MAX_CONCURRENT)

    pending, cached = [], 0
    for d in sorted(V3_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not (d / "results.json").exists():
            continue
        if (d / "emotion_analysis.json").exists():
            cached += 1
        else:
            pending.append(d)

    print(f"Emotion analysis for v3: cached={cached}, pending={len(pending)}", flush=True)

    for idx, ep in enumerate(pending):
        print(f"  [{idx+1}/{len(pending)}] {ep.name}", flush=True)
        t0 = time.time()
        try:
            m = await process_experiment(ep, llm)
            if m:
                elapsed = time.time() - t0
                gs = _GlobalStats.get().summary()
                print(f"    DONE neg={m['negative_ratio']:.1%} anger={m['anger_ratio']:.1%} "
                      f"({elapsed:.0f}s) | {gs}\n", flush=True)
        except Exception as e:
            print(f"    ERROR: {e}\n", flush=True)

    print("\nAll emotion analyses complete!", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
