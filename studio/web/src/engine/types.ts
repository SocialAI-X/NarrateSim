/**
 * The NarrateSim Studio protocol. These shapes are shared by the browser engine, the Python
 * engine (`studio/backend/nsstudio`) and the JSON run files both of them write, so a run made
 * on a server with LLM agents can be replayed in the browser console and vice versa.
 * Field names are snake_case on purpose: they are the wire format.
 */

export type Framing =
  | "reasoned" // honest, argument-led
  | "personal" // honest, experience-led
  | "pseudo_rational"
  | "victim_narrative"
  | "fear_appeal"
  | "conspiracy"
  | "fake_authority"
  | "bandwagon";

export type StrategyId = Exclude<Framing, "reasoned" | "personal">;
export type Coordination = "independent" | "echo" | "complementary" | "escalating";
export type Placement = "hub" | "bridge" | "random" | "periphery";
export type NetworkKind = "scale_free" | "small_world" | "random" | "communities";
export type FeedRanking = "chronological" | "engagement";
export type MindKind = "heuristic" | "llm";
export type PopulationId = "representative" | "trusting" | "distrustful" | "polarized" | "analytical";

export type DefenseKind =
  | "prebunking"
  | "fact_check"
  | "community_notes"
  | "guardian"
  | "suspension"
  | "reflection_prompt"
  | "climate_report";

export interface Topic {
  id: string;
  title: string;
  /** The question the society argues about, phrased so + means "yes". */
  question: string;
  pos_label: string;
  neg_label: string;
  init_mean: number;
  init_std: number;
  conf_mean: number;
  conf_std: number;
  /** Phrase banks used by the heuristic mind to write posts. */
  lexicon: TopicLexicon;
}

export interface TopicLexicon {
  subject: string;
  pro: string[];
  con: string[];
  doubt: string[];
  pro_story: string[];
  con_story: string[];
  /** Material for attackers; written against the positive pole. */
  stat: string[];
  harm: string[];
  threat: string[];
  plot: string[];
  expert: string[];
}

export interface DefenseSpec {
  kind: DefenseKind;
  enabled: boolean;
  start: number;
  /** 0..1, how strong the mechanism is. */
  strength: number;
  /** Prebunking: share of the population reached. */
  coverage?: number;
  /** Fact check, climate report: repeat every N rounds. */
  every?: number;
  /** Guardian: decision threshold on its manipulation score. */
  threshold?: number;
  /** Guardian: what happens to a post above threshold. */
  action?: "label" | "downrank" | "remove";
  /** Community notes: disagreeing raters needed for a note. */
  quorum?: number;
  /** Suspension: flags before an account is suspended. */
  strikes?: number;
}

export interface Scenario {
  name: string;
  seed: number;
  topic: string | Topic;
  society: {
    n_agents: number;
    rounds: number;
    population: PopulationId;
    memory: number;
  };
  network: {
    kind: NetworkKind;
    /** scale_free: edges per new node; small_world: half-degree; random/communities: mean degree. */
    degree: number;
    /** small_world rewiring probability. */
    rewire: number;
    /** communities: number of groups and share of ties inside a group. */
    communities: number;
    homophily: number;
  };
  feed: { ranking: FeedRanking; capacity: number };
  adversary: {
    enabled: boolean;
    n_attackers: number;
    placement: Placement;
    strategy: StrategyId;
    coordination: Coordination;
    start: number;
    end: number; // -1 = until the end
    /** Which pole the operation pushes toward: -1 or +1. */
    target: -1 | 1;
    adaptive: boolean;
  };
  defenses: DefenseSpec[];
  engine: { mind: MindKind; model?: string };
}

export interface AgentState {
  id: number;
  name: string;
  handle: string;
  /** D1..D5 on 1..10: institutional trust, care, loyalty/order, just-world, analytic thinking. */
  values: [number, number, number, number, number];
  stance: number; // continuous, -5..5
  confidence: number; // 1..10
  arousal: number; // 0..1
  s0: number;
  c0: number;
  attacker: boolean;
  community: number;
  degree: number;
  inoculated: boolean;
  suspended: boolean;
  flags: number;
  /** Signed stance displacement attributable to the operation (toward its target is positive). */
  attack_shift: number;
  exposed: boolean;
}

export interface Post {
  id: number;
  round: number;
  author: number;
  reply_to: number | null;
  stance: number; // signal the post pushes
  framing: Framing;
  intensity: number; // 0..1
  text: string;
  /** Ground truth: written by an attacker. */
  manipulative: boolean;
  /** Share of the author's recent movement owed to the operation (1 for attackers). */
  taint: number;
  label: null | "guardian" | "note";
  downranked: boolean;
  removed: boolean;
  guardian_score: number | null;
  seen: number;
  agree: number;
  disagree: number;
  /** Belief–desire–intention trace (LLM runs) or the heuristic rationale. */
  bdi?: { belief: string; desire: string; intention: string } | null;
}

export interface InfluenceEdge {
  round: number;
  from: number;
  to: number;
  delta: number; // signed stance change of `to`
  via_attack: boolean;
  generation: number; // 1 = moved directly by an attacker post
}

export interface RoundMetrics {
  round: number;
  mean: number;
  std: number;
  polarization: number;
  extreme: number;
  converted: number; // share at or beyond 2 on the target side
  silence: number;
  confidence: number;
  arousal: number;
  homophily: number;
  exposure: number; // cumulative share of honest agents that saw an attacker post
  contamination: number; // mean attack_shift (toward target)
  posts: number;
  attacker_posts: number;
  labeled: number;
  removed: number;
  tp: number;
  fp: number;
  fn: number;
  suspended_honest: number;
  suspended_attackers: number;
  secondary: number; // agents moved by a tainted honest agent this round
}

export interface SystemEvent {
  round: number;
  kind: "attack_start" | "attack_end" | "defense_start" | "fact_check" | "climate_report" | "suspension" | "prebunk" | "fork";
  text: string;
  agent?: number;
}

export interface RoundFrame {
  round: number;
  stances: number[]; // per agent, rounded to 2 decimals
  confidences: number[];
  posts: Post[];
  influence: InfluenceEdge[];
  metrics: RoundMetrics;
  events: SystemEvent[];
}

export interface RunMeta {
  id: string;
  created: string;
  engine: "browser" | "python";
  mind: MindKind;
  model?: string;
  variant: "baseline" | "attacked" | "defended" | "single" | "fork";
  parent?: string;
  fork_round?: number;
  elapsed_ms: number;
  llm_calls?: number;
  tokens?: number;
}

export interface RunRecord {
  meta: RunMeta;
  scenario: Scenario;
  topic: Topic;
  graph: { n: number; edges: [number, number][]; communities: number[] };
  agents: AgentState[]; // initial state (round 0)
  frames: RoundFrame[]; // frames[0] is round 0
}

export interface TriadSummary {
  attack_effect: number | null;
  residual_effect: number | null;
  protection: number | null;
  protection_auc: number | null;
  final: { baseline: number; attacked: number; defended: number };
}
