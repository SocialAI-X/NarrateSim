"""Core simulation engine for multi-agent discussion.

v2: Supports COT reasoning, intelligent malicious agents, and
    per-experiment directory output.
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

from .llm_client import LLMClient
from .models import (
    Agent,
    DynamicBeliefs,
    ExperimentConfig,
    InterventionConfig,
    MaliciousConfig,
    PopulationConfig,
    RoundRecord,
    StaticBeliefs,
    TopicConfig,
)
from .network import create_ba_network, get_neighbors, get_top_degree_nodes
from .prompts import build_user_prompt, format_system_prompt, INTERVENTION_BELIEFS


NICKNAMES_POOL = [
    "NovaWalker", "SilverFox", "RiverStone", "MidnightOwl", "SkyDrifter",
    "IronLeaf", "QuietStorm", "BrightSpark", "DeepCurrent", "WildReed",
    "GoldenHawk", "FrostByte", "SunChaser", "DarkMeadow", "SwiftTide",
    "BoldEcho", "CalmVoyager", "StoneRidge", "LightSeeker", "ThunderPeak",
    "MossyTrail", "StarForge", "PaleHorizon", "DuskRunner", "KeenEdge",
    "FlintSpark", "HollowRock", "VelvetDusk", "AshenGale", "DriftWood",
    "TrueNorth", "FernGully", "ElmShade", "RustNail", "CloudBreak",
    "IvoryCoast", "ZephyrCall", "RedDawn", "WillowBend", "StonePath",
    "GraniteHold", "BlueMist", "SageBrush", "CedarWind", "DawnLight",
    "EmberGlow", "NightShade", "CopperField", "JadeStone", "VividArc",
    "LoneWolf", "TidalForce", "GreenPulse", "OakHeart", "WhisperWind",
    "IronGate", "SilkRoad", "CrystalPeak", "WolfHeart", "SteelWing",
    "FireThorn", "GreyWolf", "LunarTide", "PineCone", "ReedFlute",
    "SolarFlare", "VineGrip", "AmberWave", "CoralReef", "DesertFox",
    "EagleEye", "FalconRise", "HawkWind", "JetStream", "KiteFlyer",
    "LarkSong", "MapleStar", "NorthStar", "OceanDeep", "PhoenixAsh",
    "QuartzField", "RainForge", "SnowDrift", "TigerLily", "UmbraShade",
    "VortexRun", "WaveBreaker", "XylemFlow", "YewBranch", "ZenithMark",
    "ArcticFern", "BramblePath", "CinderBlock", "DuneRider", "EchoValley",
    "FlareGun", "GlacierWalk", "HarborLight", "IndigoSky", "JuniperBlaze",
]


INTERVENTION_TEXTS = {
    "fact_check": (
        "Fact-check notice: Some claims in this discussion may lack evidence. "
        "Please verify information before sharing. Reliable sources include peer-reviewed "
        "research, official statistics, and established institutions."
    ),
    "inoculation": (
        "Media literacy notice: Common manipulation techniques in online discussions include: "
        "(1) Fake experts and cherry-picked data, (2) Emotionally charged personal anecdotes "
        "that may not be representative, (3) False dilemmas that ignore middle ground, "
        "(4) Ad hominem attacks that distract from the actual issue. "
        "Watch for these patterns and evaluate evidence critically."
    ),
    "community_report": (
        "⚠ COMMUNITY MODERATION ALERT: Multiple participants have flagged certain messages "
        "in this thread as potentially misleading or manipulative. Flagged content is marked "
        "with [⚠ FLAGGED]. Community flags don't mean a post is false, but indicate that "
        "other readers found it suspicious. Use your own judgment."
    ),
    "metacognitive": (
        "REFLECTION PROMPT: Before you respond, pause and consider:\n"
        "  1. Am I reacting to EVIDENCE or to EMOTION right now?\n"
        "  2. Has my position changed because of new facts, or because of social pressure?\n"
        "  3. If I removed the most emotional message I just read, would I still feel the same?\n"
        "  4. Am I being persuaded, or am I being manipulated?\n"
        "Take a breath. Then respond."
    ),
    "sentiment_transparency": None,  # dynamically generated per round
}


def generate_agents(
    config: ExperimentConfig,
    topic: TopicConfig,
    population: PopulationConfig,
    rng: np.random.Generator,
    exclude_ids: Optional[List[int]] = None,
) -> List[Optional[Agent]]:
    """Generate normal agents (skip IDs reserved for malicious injectors).

    RNG is consumed for ALL slots (including excluded) to guarantee identical
    initial conditions regardless of how many malicious agents are placed.
    """
    exclude_ids = set(exclude_ids or [])
    agents: List[Optional[Agent]] = []
    for i in range(config.n_agents):
        # Always consume RNG in the same order so initial conditions
        # are identical across different n_mal conditions.
        static = StaticBeliefs(
            D1_institutional_trust=float(np.clip(rng.normal(population.D1_mean, population.D1_std), 1, 10)),
            D2_care_fairness=float(np.clip(rng.normal(population.D2_mean, population.D2_std), 1, 10)),
            D3_loyalty_order=float(np.clip(rng.normal(population.D3_mean, population.D3_std), 1, 10)),
            D4_just_world=float(np.clip(rng.normal(population.D4_mean, population.D4_std), 1, 10)),
            D5_analytical_thinking=float(np.clip(rng.normal(population.D5_mean, population.D5_std), 1, 10)),
        )

        init_stance = int(np.clip(
            round(rng.normal(topic.initial_stance_mean, topic.initial_stance_std)), -5, 5
        ))
        init_confidence = int(np.clip(
            round(rng.normal(topic.initial_confidence_mean, topic.initial_confidence_std)), 1, 10
        ))

        if i in exclude_ids:
            agents.append(None)
            continue

        agent = Agent(
            agent_id=i,
            nickname=NICKNAMES_POOL[i % len(NICKNAMES_POOL)],
            static_beliefs=static,
            dynamic_beliefs=DynamicBeliefs(stance=init_stance, confidence=init_confidence),
            initial_stance=init_stance,
            initial_confidence=init_confidence,
            memory_window=config.memory_window,
        )
        agents.append(agent)
    return agents


class Simulation:
    """Run a multi-agent discussion simulation with COT reasoning."""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.topic = config.get_topic_config()
        self.malicious_config = config.get_malicious_config()
        self.intervention_config = config.get_intervention_config()
        self.population_config = config.get_population_config()
        self.rng = np.random.default_rng(config.random_seed)

        self.graph = create_ba_network(config.n_agents, config.network_m, config.random_seed)
        self.llm = LLMClient(model=config.model_name, max_concurrent=config.max_concurrent)

        self.malicious_agents_list = []
        self.malicious_ids: List[int] = []
        self.malicious_nicknames: Dict[int, str] = {}
        self.malicious_round_records: Dict[int, Dict[int, RoundRecord]] = {}

        if self.malicious_config.enabled:
            self._setup_malicious()

        self.agents = generate_agents(
            config, self.topic, self.population_config, self.rng,
            exclude_ids=self.malicious_ids,
        )
        self.round_data: List[Dict] = []

    def _setup_malicious(self):
        """Set up intelligent malicious agents.

        Uses a separate RNG for placement selection so the main RNG state
        (used for agent initialization) is identical across all conditions.
        """
        from .malicious_agents import create_malicious_agents, get_malicious_agent_positions

        placement_rng = np.random.default_rng(self.config.random_seed + 7777)
        placement = getattr(self.malicious_config, 'placement', 'hub')
        n_mal = self.malicious_config.n_agents
        if placement == "random":
            all_nodes = list(self.graph.nodes())
            placement_rng.shuffle(all_nodes)
            self.malicious_ids = all_nodes[:n_mal]
        elif placement == "mixed":
            hub_ids = get_malicious_agent_positions(self.graph, n=1)
            remaining = [n for n in self.graph.nodes() if n not in hub_ids]
            placement_rng.shuffle(remaining)
            self.malicious_ids = hub_ids + remaining[:max(0, n_mal - 1)]
        else:  # "hub" (default)
            self.malicious_ids = get_malicious_agent_positions(self.graph, n=n_mal)
        self.malicious_agents_list = create_malicious_agents(
            self.graph,
            strategy=self.malicious_config.strategy,
            coordination_mode=self.malicious_config.coordination,
            n=self.malicious_config.n_agents,
            nicknames=[NICKNAMES_POOL[nid % len(NICKNAMES_POOL)] for nid in self.malicious_ids],
            positions=self.malicious_ids,
        )
        for ma in self.malicious_agents_list:
            self.malicious_nicknames[ma.node_id] = ma.nickname
            self.malicious_round_records[ma.node_id] = {}

    def _malicious_active(self, round_num: int) -> bool:
        """Check if malicious agents should be active this round."""
        if not self.malicious_config.enabled:
            return False
        start = getattr(self.malicious_config, 'start_round', 0)
        end = getattr(self.malicious_config, 'end_round', -1)
        if round_num < start:
            return False
        if end >= 0 and round_num > end:
            return False
        return True

    async def run(self, progress_callback=None) -> Dict:
        start_time = time.time()

        if self._malicious_active(0):
            await self._inject_malicious_intelligent(0)
            if progress_callback:
                for ma in self.malicious_agents_list:
                    rec = self.malicious_round_records[ma.node_id].get(0)
                    if rec:
                        progress_callback(f"  [MAL R0] {ma.nickname}: {rec.message[:150]}")

        for round_num in range(1, self.config.n_rounds + 1):
            intervention_belief = self._get_intervention_belief(round_num)
            intervention_context = self._get_intervention_context(round_num)
            round_results = await self._run_round(round_num, intervention_belief, intervention_context)
            self.round_data.append(round_results)

            if progress_callback:
                normal_recs = [r for r in round_results["records"] if not r.get("is_malicious")]
                actions = {"speak": 0, "reply": 0, "silent": 0}
                stances = []
                for r in normal_recs:
                    actions[r.get("action", "silent")] += 1
                    if r.get("stance") is not None:
                        stances.append(r["stance"])
                avg_s = sum(stances) / max(len(stances), 1)
                progress_callback(
                    f"R{round_num}/{self.config.n_rounds} "
                    f"speak={actions['speak']} reply={actions['reply']} silent={actions['silent']} "
                    f"avg_stance={avg_s:.2f} errors={round_results.get('errors', 0)}"
                )

            if self._malicious_active(round_num):
                await self._inject_malicious_intelligent(round_num)
                if progress_callback:
                    for ma in self.malicious_agents_list:
                        rec = self.malicious_round_records[ma.node_id].get(round_num)
                        if rec:
                            progress_callback(f"  [MAL R{round_num}] {ma.nickname}: {rec.message[:150]}")

        elapsed = time.time() - start_time
        return self._compile_results(elapsed)

    async def _inject_malicious_intelligent(self, round_num: int):
        """Generate malicious messages sequentially for coordination.

        Each malicious agent sees what previous teammates posted this round,
        enabling them to differentiate their messaging and coordinate attacks.
        """
        from .malicious_agents import generate_intelligent_message

        sampled = self._sample_global_messages(n=12)
        teammate_messages = []

        for ma in self.malicious_agents_list:
            try:
                msg, mal_cot = await generate_intelligent_message(
                    agent=ma,
                    topic_description=self.topic.description,
                    round_num=round_num,
                    total_rounds=self.config.n_rounds,
                    sampled_messages=sampled,
                    llm=self.llm,
                    teammate_messages=teammate_messages if teammate_messages else None,
                )
            except Exception as e:
                msg = "I can't believe what I'm reading here."
                mal_cot = f"Error: {e}"

            record = RoundRecord(
                round_num=round_num, stance=0, confidence=0,
                action="speak", target=None, message=msg,
                cot=mal_cot,
            )
            self.malicious_round_records[ma.node_id][round_num] = record
            teammate_messages.append((ma.nickname, msg))

    def _sample_global_messages(self, n: int = 12) -> List[Tuple[str, str]]:
        """Sample recent messages from random normal agents for malicious agent awareness."""
        samples = []
        normal_agents = [a for a in self.agents if a is not None and a.trajectory]
        if not normal_agents:
            return samples

        sampled = self.rng.choice(normal_agents, size=min(n, len(normal_agents)), replace=False)
        for agent in sampled:
            last = agent.trajectory[-1]
            if last.message:
                samples.append((agent.nickname, last.message[:200]))
        return samples

    def _get_intervention_belief(self, round_num: int) -> Optional[str]:
        """Get belief-based intervention (injected into agent personality)."""
        cfg = self.intervention_config
        if not cfg.enabled:
            return None
        if round_num < cfg.start_round:
            return None
        return INTERVENTION_BELIEFS.get(cfg.type)

    def _get_intervention_context(self, round_num: int) -> Optional[str]:
        """Get context-based intervention (injected into round context)."""
        cfg = self.intervention_config
        if not cfg.enabled:
            return None
        if round_num < cfg.start_round:
            return None
        if (round_num - cfg.start_round) % cfg.frequency != 0:
            return None

        if cfg.type == "sentiment_transparency":
            return self._build_sentiment_transparency(round_num)
        if cfg.type == "community_report":
            return INTERVENTION_TEXTS.get(cfg.type)
        return None

    def _build_sentiment_transparency(self, round_num: int) -> str:
        """Generate dynamic sentiment transparency message based on recent rounds."""
        if not self.round_data:
            return "Discussion climate: This is an early round. No sentiment data yet."

        recent = self.round_data[-3:] if len(self.round_data) >= 3 else self.round_data
        neg_words = 0
        total_msgs = 0
        action_counts = {"speak": 0, "reply": 0, "silent": 0}
        for rd in recent:
            for rec in rd["records"]:
                if rec.get("is_malicious"):
                    continue
                msg = rec.get("message", "").lower()
                if msg:
                    total_msgs += 1
                    for w in ["angry", "disgusting", "terrible", "wrong", "hate", "fear",
                              "worried", "sick", "broken", "corrupt", "betrayal", "cruel"]:
                        if w in msg:
                            neg_words += 1
                            break
                action_counts[rec.get("action", "silent")] += 1

        neg_pct = int(neg_words / max(total_msgs, 1) * 100)
        reply_pct = int(action_counts["reply"] / max(sum(action_counts.values()), 1) * 100)
        silent_pct = int(action_counts["silent"] / max(sum(action_counts.values()), 1) * 100)

        return (
            f"📊 DISCUSSION CLIMATE UPDATE (last {len(recent)} rounds):\n"
            f"  • ~{neg_pct}% of messages contain negative/hostile language\n"
            f"  • {reply_pct}% of actions are direct replies (confrontational pattern)\n"
            f"  • {silent_pct}% of participants chose silence\n"
            f"Consider: Is the emotional temperature of this discussion affecting your judgment? "
            f"Are you engaging with IDEAS or reacting to EMOTIONS? "
            f"Research shows group negativity spirals can shift individual beliefs "
            f"even when no new evidence is presented."
        )

    async def _run_round(
        self, round_num: int,
        intervention_belief: Optional[str] = None,
        intervention_context: Optional[str] = None,
    ) -> Dict:
        """Execute one round for all normal agents."""
        tasks = []
        normal_agents = []
        for agent in self.agents:
            if agent is None:
                continue
            neighbors = get_neighbors(self.graph, agent.agent_id)
            neighbor_records = self._get_neighbor_last_records(neighbors, round_num)
            tasks.append(self._agent_turn(agent, round_num, neighbor_records,
                                          intervention_belief, intervention_context))
            normal_agents.append(agent)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        round_summary = {"round": round_num, "records": [], "errors": 0, "llm_errors": self.llm._error_count}

        for agent, result in zip(normal_agents, results):
            if isinstance(result, Exception):
                round_summary["errors"] += 1
                print(f"  [SIM] Agent {agent.agent_id} error R{round_num}: {str(result)[:80]}", flush=True)
                record = RoundRecord(
                    round_num=round_num,
                    stance=agent.dynamic_beliefs.stance,
                    confidence=agent.dynamic_beliefs.confidence,
                    action="silent", target=None, message="",
                )
            else:
                record = result
            agent.update(record)
            round_summary["records"].append({
                "agent_id": agent.agent_id,
                "nickname": agent.nickname,
                "action": record.action,
                "target": record.target,
                "stance": record.stance,
                "confidence": record.confidence,
                "message": record.message,
                "cot": record.cot,
                "is_malicious": False,
            })

        if self.malicious_config.enabled:
            # Malicious records for round R are generated BEFORE normal round R+1,
            # so during _run_round(R) the latest available records are for R-1 (or 0).
            mal_seen_round = round_num - 1 if round_num > 0 else 0
            for ma in self.malicious_agents_list:
                rec = self.malicious_round_records[ma.node_id].get(mal_seen_round)
                if rec:
                    round_summary["records"].append({
                        "agent_id": ma.node_id,
                        "nickname": ma.nickname,
                        "action": "speak",
                        "target": None,
                        "stance": None,
                        "confidence": None,
                        "message": rec.message,
                        "cot": rec.cot,
                        "is_malicious": True,
                    })

        return round_summary

    async def _agent_turn(
        self, agent: Agent, round_num: int,
        neighbor_records: List[Tuple[str, Optional[RoundRecord]]],
        intervention_belief: Optional[str] = None,
        intervention_context: Optional[str] = None,
    ) -> RoundRecord:
        system_prompt = format_system_prompt(agent, self.topic, intervention_belief)
        user_prompt = build_user_prompt(
            agent, self.topic, round_num, neighbor_records,
            self.config.memory_window, intervention_context,
        )

        temp = 0.78 + (agent.agent_id % 11) * 0.02
        raw = await self.llm.query(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temp,
            max_tokens=800,
        )

        cot = ""
        cot_match = re.search(r"\[COT\](.*?)\[/COT\]", raw, re.DOTALL)
        if cot_match:
            cot = cot_match.group(1).strip()

        cleaned = re.sub(r"\[COT\].*?\[/COT\]", "", raw, flags=re.DOTALL).strip()
        # Sometimes the model wraps JSON in extra text — try to extract the JSON object
        json_match = re.search(r'\{[^{}]*"action"[^{}]*\}', cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)
        try:
            response = self.llm._parse_json(cleaned)
        except Exception:
            # Last-resort: extract individual fields with regex
            action_m = re.search(r'"action"\s*:\s*"(\w+)"', cleaned)
            stance_m = re.search(r'"stance"\s*:\s*(-?\d+)', cleaned)
            conf_m = re.search(r'"confidence"\s*:\s*(\d+)', cleaned)
            msg_m = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
            response = {
                "action": action_m.group(1) if action_m else "silent",
                "stance": int(stance_m.group(1)) if stance_m else agent.dynamic_beliefs.stance,
                "confidence": int(conf_m.group(1)) if conf_m else agent.dynamic_beliefs.confidence,
                "message": msg_m.group(1).replace('\\"', '"') if msg_m else "",
                "target": None,
            }

        action = response.get("action", "silent")
        if action not in ("speak", "reply", "silent"):
            action = "silent"

        stance = int(np.clip(response.get("stance", agent.dynamic_beliefs.stance), -5, 5))
        confidence = int(np.clip(response.get("confidence", agent.dynamic_beliefs.confidence), 1, 10))
        message = response.get("message", "")
        target = response.get("target", None)

        return RoundRecord(
            round_num=round_num, stance=stance, confidence=confidence,
            action=action, target=target, message=message[:500],
            cot=cot,
        )

    def _get_neighbor_last_records(
        self, neighbor_ids: List[int], current_round: int,
    ) -> List[Tuple[str, Optional[RoundRecord]]]:
        flag_malicious = (
            self.intervention_config.enabled
            and self.intervention_config.type == "community_report"
            and current_round >= self.intervention_config.start_round
        )
        records = []
        for nid in neighbor_ids:
            if nid in self.malicious_ids:
                last_round = current_round - 1 if current_round > 0 else 0
                rec = self.malicious_round_records.get(nid, {}).get(last_round)
                nickname = self.malicious_nicknames.get(nid, f"Agent{nid}")
                if flag_malicious and rec and rec.message:
                    rec = RoundRecord(
                        round_num=rec.round_num, stance=rec.stance,
                        confidence=rec.confidence, action=rec.action,
                        target=rec.target,
                        message=f"[⚠ FLAGGED] {rec.message}",
                        cot=rec.cot,
                    )
                records.append((nickname, rec))
            else:
                agent = self.agents[nid] if nid < len(self.agents) else None
                if agent is None:
                    continue
                last_record = agent.trajectory[-1] if agent.trajectory else None
                records.append((agent.nickname, last_record))
        return records

    def _compile_results(self, elapsed: float) -> Dict:
        normal_agents = [a for a in self.agents if a is not None]

        return {
            "experiment_name": self.config.experiment_name,
            "study": self.config.study,
            "config": {
                "n_agents": self.config.n_agents,
                "n_rounds": self.config.n_rounds,
                "network_m": self.config.network_m,
                "memory_window": self.config.memory_window,
                "model": self.config.model_name,
                "seed": self.config.random_seed,
                "malicious": {
                    "enabled": self.malicious_config.enabled,
                    "strategy": self.malicious_config.strategy if self.malicious_config.enabled else None,
                    "coordination": self.malicious_config.coordination if self.malicious_config.enabled else None,
                    "positions": self.malicious_ids,
                },
                "intervention": {
                    "enabled": self.intervention_config.enabled,
                    "type": self.intervention_config.type if self.intervention_config.enabled else None,
                },
                "population": self.population_config.name,
            },
            "topic": {"name": self.topic.name, "name_cn": self.topic.name_cn},
            "elapsed_seconds": elapsed,
            "agents_initial": [
                {
                    "agent_id": a.agent_id,
                    "nickname": a.nickname,
                    "static_beliefs": {
                        "D1": round(a.static_beliefs.D1_institutional_trust, 2),
                        "D2": round(a.static_beliefs.D2_care_fairness, 2),
                        "D3": round(a.static_beliefs.D3_loyalty_order, 2),
                        "D4": round(a.static_beliefs.D4_just_world, 2),
                        "D5": round(a.static_beliefs.D5_analytical_thinking, 2),
                    },
                    "initial_stance": a.initial_stance,
                    "initial_confidence": a.initial_confidence,
                }
                for a in normal_agents
            ],
            "rounds": self.round_data,
            "agents_final": [
                {
                    "agent_id": a.agent_id,
                    "nickname": a.nickname,
                    "final_stance": a.dynamic_beliefs.stance,
                    "final_confidence": a.dynamic_beliefs.confidence,
                }
                for a in normal_agents
            ],
        }
