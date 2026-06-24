from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StaticBeliefs:
    """Fixed value dimensions that don't change during simulation."""
    D1_institutional_trust: float      # 制度信任 [1,10]
    D2_care_fairness: float            # 关怀-公平道德 [1,10]
    D3_loyalty_order: float            # 忠诚-秩序道德 [1,10]
    D4_just_world: float               # 公正世界信念 [1,10]
    D5_analytical_thinking: float      # 分析性思维 [1,10]


@dataclass
class DynamicBeliefs:
    """Mutable beliefs that update each round."""
    stance: int       # [-5, 5]
    confidence: int   # [1, 10]


@dataclass
class RoundRecord:
    """Record of one agent's state in a single round."""
    round_num: int
    stance: int
    confidence: int
    action: str              # "speak" / "reply" / "silent"
    target: Optional[str]    # nickname of target or None
    message: str
    cot: Optional[str] = None


@dataclass
class Agent:
    """A simulation agent with beliefs, memory, and identity."""
    agent_id: int
    nickname: str
    static_beliefs: StaticBeliefs
    dynamic_beliefs: DynamicBeliefs
    initial_stance: int
    initial_confidence: int
    trajectory: List[RoundRecord] = field(default_factory=list)
    memory_window: int = 10

    @property
    def recent_memory(self) -> List[RoundRecord]:
        """Return last K rounds of own records."""
        return self.trajectory[-self.memory_window:]

    def update(self, record: RoundRecord):
        self.dynamic_beliefs.stance = record.stance
        self.dynamic_beliefs.confidence = record.confidence
        self.trajectory.append(record)


@dataclass
class TopicConfig:
    """Configuration for a discussion topic."""
    name: str
    name_cn: str
    description: str
    stance_negative: str
    stance_positive: str
    initial_stance_mean: float
    initial_stance_std: float
    initial_confidence_mean: float
    initial_confidence_std: float


@dataclass
class MaliciousConfig:
    """Configuration for malicious narrative agents."""
    enabled: bool = False
    n_agents: int = 3
    strategy: str = "pseudo_rational"
    coordination: str = "independent"
    intelligent: bool = True
    start_round: int = 0      # round when malicious agents start attacking
    end_round: int = -1        # round when malicious agents stop (-1 = never)
    placement: str = "hub"     # "hub" (default, high-degree nodes) or "random"


@dataclass
class InterventionConfig:
    """Configuration for intervention conditions."""
    enabled: bool = False
    type: str = "none"           # "none" / "fact_check" / "inoculation" / "community_report" / "metacognitive" / "sentiment_transparency"
    start_round: int = 3
    frequency: int = 3           # apply every N rounds


@dataclass
class PopulationConfig:
    """Configuration for population belief distributions."""
    name: str = "representative"
    D1_mean: float = 5.5
    D1_std: float = 2.0
    D2_mean: float = 5.5
    D2_std: float = 2.0
    D3_mean: float = 5.5
    D3_std: float = 2.0
    D4_mean: float = 5.5
    D4_std: float = 2.0
    D5_mean: float = 5.5
    D5_std: float = 2.0


@dataclass
class ExperimentConfig:
    """Full experiment configuration loaded from JSON."""
    experiment_name: str = "baseline"
    study: str = "study1"
    n_agents: int = 100
    n_rounds: int = 15
    network_m: int = 3
    memory_window: int = 10
    random_seed: int = 42
    model_name: str = "Pro/deepseek-ai/DeepSeek-V3.2"
    max_concurrent: int = 30
    topic: Optional[Dict[str, Any]] = None
    malicious: Optional[Dict[str, Any]] = None
    intervention: Optional[Dict[str, Any]] = None
    population: Optional[Dict[str, Any]] = None

    def get_topic_config(self) -> TopicConfig:
        if self.topic:
            return TopicConfig(**self.topic)
        raise ValueError("No topic config provided")

    def get_malicious_config(self) -> MaliciousConfig:
        if self.malicious:
            return MaliciousConfig(**self.malicious)
        return MaliciousConfig()

    def get_intervention_config(self) -> InterventionConfig:
        if self.intervention:
            return InterventionConfig(**self.intervention)
        return InterventionConfig()

    def get_population_config(self) -> PopulationConfig:
        if self.population:
            return PopulationConfig(**self.population)
        return PopulationConfig()
