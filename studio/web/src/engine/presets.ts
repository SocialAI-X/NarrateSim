import type { DefenseKind, DefenseSpec, Scenario } from "./types";

export function defaultDefenses(): DefenseSpec[] {
  return [
    { kind: "prebunking", enabled: false, start: 1, strength: 0.7, coverage: 0.6 },
    { kind: "fact_check", enabled: false, start: 3, strength: 0.6, every: 3 },
    { kind: "community_notes", enabled: false, start: 2, strength: 0.6, quorum: 3 },
    { kind: "guardian", enabled: false, start: 2, strength: 0.7, threshold: 0.66, action: "label" },
    { kind: "suspension", enabled: false, start: 3, strength: 1, strikes: 3 },
    { kind: "reflection_prompt", enabled: false, start: 3, strength: 0.6 },
    { kind: "climate_report", enabled: false, start: 3, strength: 0.6, every: 3 },
  ];
}

export function defaultScenario(): Scenario {
  return {
    name: "Untitled scenario",
    seed: 42,
    topic: "vaccines",
    society: { n_agents: 120, rounds: 16, population: "representative", memory: 6 },
    network: { kind: "scale_free", degree: 3, rewire: 0.1, communities: 3, homophily: 0.8 },
    feed: { ranking: "chronological", capacity: 8 },
    adversary: {
      enabled: true,
      n_attackers: 4,
      placement: "hub",
      strategy: "victim_narrative",
      coordination: "independent",
      start: 1,
      end: -1,
      target: -1,
      adaptive: true,
    },
    defenses: defaultDefenses(),
    engine: { mind: "heuristic" },
  };
}

const withDefense = (s: Scenario, kind: DefenseKind, patch: Partial<DefenseSpec> = {}): Scenario => ({
  ...s,
  defenses: s.defenses.map((d) => (d.kind === kind ? { ...d, enabled: true, ...patch } : d)),
});

export interface Preset {
  id: string;
  title: string;
  blurb: string;
  scenario: Scenario;
}

function preset(id: string, title: string, blurb: string, f: (s: Scenario) => Scenario): Preset {
  const base = defaultScenario();
  const s = f(base);
  s.name = title;
  return { id, title, blurb, scenario: s };
}

export const PRESETS: Preset[] = [
  preset("hub-victim", "Hub accounts, victim stories", "Four high-degree accounts tell harm stories about childhood vaccines. No defense.", (s) => s),
  preset("prebunk-early", "Prebunking from round 1", "The same operation against a population prebunked before it starts.", (s) => withDefense(s, "prebunking", { start: 1 })),
  preset("prebunk-late", "Prebunking after round 6", "The same prebunking, delivered once the operation has had six rounds.", (s) => withDefense(s, "prebunking", { start: 6 })),
  preset("guardian-downrank", "Guardian with downranking", "A noisy classifier labels and downranks posts it scores as manipulative; it also catches honest emotional posts.", (s) =>
    withDefense(withDefense(s, "guardian", { action: "downrank", start: 2 }), "suspension", { strikes: 4 }),
  ),
  preset("echo-chambers", "Echo chambers, bridge accounts", "Three tight communities; the operation sits on the bridges between them and pushes conspiracy framing.", (s) => ({
    ...s,
    topic: "climate",
    network: { ...s.network, kind: "communities", degree: 3, communities: 3, homophily: 0.88 },
    adversary: { ...s.adversary, placement: "bridge", strategy: "conspiracy", coordination: "complementary" },
  })),
  preset("engagement-feed", "Engagement-ranked feed", "Same operation, but feeds rank by intensity and likes. Emotional content rises to the top.", (s) => ({
    ...s,
    feed: { ranking: "engagement", capacity: 6 },
    adversary: { ...s.adversary, strategy: "fear_appeal", coordination: "echo" },
  })),
  preset("distrust-pseudo", "Pseudo-rational vs distrustful", "Calm, numbers-led skepticism aimed at a population that distrusts institutions; fact-checks switched on.", (s) =>
    withDefense({ ...s, topic: "ai_regulation", society: { ...s.society, population: "distrustful" }, adversary: { ...s.adversary, strategy: "pseudo_rational" } }, "fact_check"),
  ),
  preset("reflection-backfire", "Reflection prompts", "A reflection prompt asks everyone to question their reactions. Watch what it does to certainty.", (s) =>
    withDefense({ ...s, adversary: { ...s.adversary, strategy: "fear_appeal" } }, "reflection_prompt", { start: 2, strength: 0.8 }),
  ),
];
