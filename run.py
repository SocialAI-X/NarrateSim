"""NarrateSim unified entry point.

Usage:
  python run.py config configs/study1_strategy_topic/vaccine_baseline.json
  python run.py study study1_strategy_topic
  python run.py paper                    # all 64 main paper experiments
  python run.py scale                    # N=200..5000 scale supplement
  python run.py emotions                 # batch emotion labeling
  python run.py export-configs           # write configs/*.json from definitions
  python run.py tables                   # recompute the paper tables from results/ (no API)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.emotion_analysis import (
    CATEGORIES,
    NEGATIVE_CATEGORIES,
    POSITIVE_CATEGORIES,
    compute_emotion_metrics,
)
from src.experiment_defs import (
    CONFIGS_ROOT,
    RESULTS_ROOT,
    generate_all_experiments,
    generate_scale_experiments,
)
from src.llm_client import LLMClient, _GlobalRateLimiter, _GlobalStats
from src.runner import ExperimentRunner

BATCH_SIZE = 10
MAX_EMOTION_CONCURRENT = 15

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


def parse_batch(raw: str, n: int) -> list:
    raw = raw.strip()
    fence = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list):
            result = [
                a.lower() if isinstance(a, str) and a.lower() in CATEGORIES else "neutral"
                for a in arr
            ]
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
    chunks = [(i, messages[i : i + BATCH_SIZE]) for i in range(0, len(messages), BATCH_SIZE)]
    sem = asyncio.Semaphore(MAX_EMOTION_CONCURRENT)

    async def process(start, chunk):
        async with sem:
            text = "\n".join(f"[{j+1}] {m[:300]}" for j, m in enumerate(chunk))
            try:
                raw = await llm.query(
                    BATCH_SYSTEM_PROMPT,
                    BATCH_USER_PROMPT.format(messages_text=text),
                    temperature=0.2,
                    max_tokens=200,
                )
                return start, parse_batch(raw, len(chunk))
            except Exception:
                return start, ["neutral"] * len(chunk)

    for batch_start in range(0, len(chunks), MAX_EMOTION_CONCURRENT):
        batch = chunks[batch_start : batch_start + MAX_EMOTION_CONCURRENT]
        results = await asyncio.gather(
            *[process(s, c) for s, c in batch], return_exceptions=True
        )
        for r in results:
            if isinstance(r, Exception):
                continue
            si, cats = r
            for j, cat in enumerate(cats):
                if si + j < len(all_cats):
                    all_cats[si + j] = cat
    return all_cats


async def process_emotions(exp_dir: Path, llm) -> dict | None:
    rf, ef = exp_dir / "results.json", exp_dir / "emotion_analysis.json"
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

    cats = await classify_batch(messages, llm)
    emotion_results = [
        {
            "agent_id": agent_ids[i],
            "round_num": round_nums[i],
            "message": messages[i][:200],
            "category": cats[i],
            "is_negative": cats[i] in NEGATIVE_CATEGORIES,
            "is_positive": cats[i] in POSITIVE_CATEGORIES,
        }
        for i in range(len(cats))
    ]
    metrics = compute_emotion_metrics(emotion_results)
    ef.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    return metrics


async def cmd_emotions(study: str | None, rpm: int):
    _GlobalStats.reset()
    _GlobalRateLimiter.reset()
    _GlobalRateLimiter._instance = _GlobalRateLimiter(rpm)
    llm = LLMClient(model="Pro/deepseek-ai/DeepSeek-V3.2", max_concurrent=MAX_EMOTION_CONCURRENT)

    pending = []
    for study_dir in sorted(RESULTS_ROOT.iterdir()):
        if not study_dir.is_dir() or study_dir.name.startswith("."):
            continue
        if study and study_dir.name != study:
            continue
        for exp_dir in sorted(study_dir.iterdir()):
            if not exp_dir.is_dir():
                continue
            if (exp_dir / "results.json").exists() and not (exp_dir / "emotion_analysis.json").exists():
                pending.append(exp_dir)

    print(f"Emotion analysis: {len(pending)} pending", flush=True)
    for idx, ep in enumerate(pending):
        print(f"  [{idx+1}/{len(pending)}] {ep.parent.name}/{ep.name}", flush=True)
        t0 = time.time()
        try:
            m = await process_emotions(ep, llm)
            if m:
                print(
                    f"    DONE neg={m['negative_ratio']:.1%} ({time.time()-t0:.0f}s)",
                    flush=True,
                )
        except Exception as e:
            print(f"    ERROR: {e}", flush=True)


def cmd_export_configs():
    all_exp = {**generate_all_experiments(), **generate_scale_experiments()}
    for name, cfg in all_exp.items():
        study = cfg["study"]
        out_dir = CONFIGS_ROOT / study
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}.json"
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Exported {len(all_exp)} configs -> {CONFIGS_ROOT}/")


TOPICS = [("vaccine", "Vaccine Mandate"), ("climate", "Climate Policy"),
          ("immigration", "Immigration"), ("gmo_food", "GMO Food Safety")]
STRATEGIES = [("pseudo_rational", "Pseudo-Rational"), ("victim_narrative", "Victim Narrative"),
              ("fear_appeal", "Fear Appeal"), ("conspiracy_theory", "Conspiracy Theory"),
              ("authority_manipulation", "Authority Manip."), ("social_proof", "Social Proof"),
              ("baseline", "No attack")]
INTERVENTIONS = [("inoculation_pre", "Pre-bunking", "R1"), ("metacognitive", "Metacognitive", "R1"),
                 ("community_report", "Comm. reporting", "R5"),
                 ("inoculation_late", "Delayed pre-bunking", "R5"),
                 ("fact_check_post", "Fact-checking", "R5"),
                 ("sentiment_transparency", "Sentiment transp.", "R3"),
                 ("no_intervention", "No intervention", "--")]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _emotion(exp_dir: Path) -> tuple[float, float]:
    """EV = P+ - P- (pp) and ENI = P- / (P+ + P-) (%) over labelled messages."""
    e = _load(exp_dir / "emotion_analysis.json")
    pos, neg = e["positive_ratio"], e["negative_ratio"]
    return 100 * (pos - neg), 100 * neg / (pos + neg) if pos + neg else float("nan")


def cmd_tables():
    """Recompute Table 1 (RQ1), Table 2 (RQ2) and the network-position numbers."""
    print("Table 1 - RQ1: six strategies x four topics (3 attackers / 100 agents)")
    print(f"{'Strategy':<20}" + "".join(f"{t:>30}" for _, t in TOPICS))
    print(f"{'':<20}" + f"{'ds    NSR     EV    ENI':>30}" * len(TOPICS))
    for key, label in STRATEGIES:
        row = f"{label:<20}"
        for topic, _ in TOPICS:
            d = RESULTS_ROOT / "study1_strategy_topic" / f"{topic}_{key}"
            s = _load(d / "summary.json")
            ev, eni = _emotion(d)
            row += f"{s['mean_shift']:>+12.2f}{100 * s['neg_shift_rate']:>6.1f}{ev:>+6.1f}{eni:>6.1f}"
        print(row)

    print("\nTable 2 - RQ2: interventions against Victim Narrative (Vaccine Mandate)")
    root = RESULTS_ROOT / "study3_intervention"
    ctrl = abs(_load(root / "no_intervention" / "summary.json")["mean_shift"])
    print(f"{'Condition':<22}{'Onset':>6}{'ds':>8}{'Flip':>7}{'NSR':>7}{'Prot.':>8}")
    for key, label, onset in INTERVENTIONS:
        s = _load(root / key / "summary.json")
        prot = 100 * (1 - abs(s["mean_shift"]) / ctrl)
        print(f"{label:<22}{onset:>6}{s['mean_shift']:>+8.2f}{100 * s['flip_rate']:>7.1f}"
              f"{100 * s['neg_shift_rate']:>7.1f}{prot:>+8.1f}")

    print("\nNetwork position - Victim Narrative, final opposition share (%)")
    root = RESULTS_ROOT / "study4_robustness"
    for density, m in [("sparse", 2), ("default", 3), ("dense", 5)]:
        rnd = 100 * _load(root / f"net_{density}_random" / "summary.json")["negativity_ratio"]
        hub = 100 * _load(root / f"net_{density}_hub" / "summary.json")["negativity_ratio"]
        print(f"  m={m}  random {rnd:5.1f}  ->  hub {hub:5.1f}   (+{hub - rnd:.1f} pts)")


def main():
    parser = argparse.ArgumentParser(description="NarrateSim experiment runner")
    parser.add_argument("--rpm", type=int, default=250, help="Global LLM requests per minute")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cfg = sub.add_parser("config", help="Run a single config file")
    p_cfg.add_argument("path", help="Path to experiment JSON config")

    p_study = sub.add_parser("study", help="Run all experiments in a study folder")
    p_study.add_argument("name", help="e.g. study1_strategy_topic")

    sub.add_parser("paper", help="Run all 64 main paper experiments")
    sub.add_parser("scale", help="Run scale supplement (N=200..5000)")
    sub.add_parser("export-configs", help="Write configs/ from experiment definitions")
    sub.add_parser("tables", help="Recompute the paper tables from results/ (no API needed)")

    p_emo = sub.add_parser("emotions", help="Run batch emotion analysis on results")
    p_emo.add_argument("--study", default=None, help="Limit to one study folder")

    args = parser.parse_args()
    if args.command == "tables":
        cmd_tables()
        return
    runner = ExperimentRunner(rpm=args.rpm)

    if args.command == "config":
        asyncio.run(runner.run_config(args.path))
    elif args.command == "study":
        asyncio.run(runner.run_study(args.name))
    elif args.command == "paper":
        asyncio.run(runner.run_paper())
    elif args.command == "scale":
        asyncio.run(runner.run_scale())
    elif args.command == "export-configs":
        cmd_export_configs()
    elif args.command == "emotions":
        asyncio.run(cmd_emotions(args.study, args.rpm))


if __name__ == "__main__":
    main()
