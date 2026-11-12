import { DEFENSE_LABEL, hasDefense, Simulation, triadSummary, variantOf } from "./engine";
import { POPULATIONS } from "./topics";
import type { DefenseKind, Scenario } from "./types";

export interface Axis {
  id: string;
  label: string;
  values: { key: string; label: string; apply: (s: Scenario) => void }[];
}

const defenseOn = (s: Scenario, kind: DefenseKind, patch: Record<string, unknown> = {}) => {
  s.defenses = s.defenses.map((d) => (d.kind === kind ? { ...d, enabled: true, ...patch } : d));
};

export const AXES: Axis[] = [
  {
    id: "strategy",
    label: "Framing",
    values: (["victim_narrative", "fear_appeal", "pseudo_rational", "conspiracy", "fake_authority", "bandwagon"] as const).map((k) => ({ key: k, label: k.replace(/_/g, " "), apply: (s) => void (s.adversary.strategy = k) })),
  },
  {
    id: "population",
    label: "Value profile",
    values: (Object.keys(POPULATIONS) as (keyof typeof POPULATIONS)[]).map((k) => ({ key: k, label: POPULATIONS[k].label, apply: (s) => void (s.society.population = k) })),
  },
  { id: "placement", label: "Placement", values: (["hub", "bridge", "random", "periphery"] as const).map((k) => ({ key: k, label: k, apply: (s) => void (s.adversary.placement = k) })) },
  { id: "n_attackers", label: "Operation accounts", values: [1, 2, 4, 8, 12].map((n) => ({ key: String(n), label: String(n), apply: (s) => void (s.adversary.n_attackers = n) })) },
  {
    id: "network",
    label: "Topology",
    values: (["scale_free", "small_world", "random", "communities"] as const).map((k) => ({ key: k, label: k.replace("_", " "), apply: (s) => void (s.network.kind = k) })),
  },
  { id: "feed", label: "Feed ranking", values: (["chronological", "engagement"] as const).map((k) => ({ key: k, label: k, apply: (s) => void (s.feed.ranking = k) })) },
  {
    id: "coordination",
    label: "Coordination",
    values: (["independent", "echo", "complementary", "escalating"] as const).map((k) => ({ key: k, label: k, apply: (s) => void (s.adversary.coordination = k) })),
  },
  {
    id: "defense",
    label: "Defense",
    values: (["prebunking", "fact_check", "community_notes", "guardian", "reflection_prompt", "climate_report"] as DefenseKind[]).map((k) => ({
      key: k,
      label: DEFENSE_LABEL[k],
      apply: (s) => {
        s.defenses = s.defenses.map((d) => ({ ...d, enabled: false }));
        defenseOn(s, k);
      },
    })),
  },
  {
    id: "defense_start",
    label: "Defense start round",
    values: [1, 2, 3, 5, 8, 12].map((r) => ({
      key: String(r),
      label: `round ${r}`,
      apply: (s) => {
        if (!hasDefense(s)) defenseOn(s, "prebunking");
        s.defenses = s.defenses.map((d) => (d.enabled ? { ...d, start: r } : d));
      },
    })),
  },
  {
    id: "defense_strength",
    label: "Defense strength",
    values: [0.2, 0.4, 0.6, 0.8, 1].map((v) => ({
      key: String(v),
      label: v.toFixed(1),
      apply: (s) => {
        if (!hasDefense(s)) defenseOn(s, "prebunking");
        s.defenses = s.defenses.map((d) => (d.enabled ? { ...d, strength: v } : d));
      },
    })),
  },
];

export type MetricId = "attack_effect" | "protection" | "polarization" | "exposure" | "converted" | "silence" | "false_positive";
export const METRICS: { id: MetricId; label: string; diverging?: boolean; pct?: boolean }[] = [
  { id: "attack_effect", label: "Attack effect (stance points)" },
  { id: "protection", label: "Protection", pct: true, diverging: true },
  { id: "converted", label: "Share converted to the target side", pct: true },
  { id: "exposure", label: "Reached by the operation", pct: true },
  { id: "polarization", label: "Polarisation (Esteban–Ray)" },
  { id: "silence", label: "Silence ratio", pct: true },
  { id: "false_positive", label: "Honest posts flagged", pct: true },
];

export interface SweepSpec {
  base: Scenario;
  x: string;
  y: string | null;
  metric: MetricId;
  seeds: number;
}

export interface SweepCell {
  x: number;
  y: number;
  mean: number | null;
  ci: number;
  n: number;
  values: number[];
}

function measure(s: Scenario, metric: MetricId): number | null {
  const b = new Simulation(variantOf(s, "baseline"), "baseline").runSync().record();
  const a = new Simulation(variantOf(s, "attacked"), "attacked").runSync().record();
  const needDef = metric === "protection" || hasDefense(s);
  const d = needDef ? new Simulation(variantOf(s, "defended"), "defended").runSync().record() : undefined;
  const sum = triadSummary(b, a, d);
  const main = d ?? a;
  const fin = main.frames[main.frames.length - 1].metrics;
  switch (metric) {
    case "attack_effect":
      return sum.attack_effect;
    case "protection":
      return sum.protection_auc;
    case "polarization":
      return fin.polarization;
    case "exposure":
      return fin.exposure;
    case "converted":
      return fin.converted;
    case "silence":
      return fin.silence;
    case "false_positive": {
      const posts = main.frames.flatMap((f) => f.posts).filter((p) => !p.manipulative);
      return posts.length ? posts.filter((p) => p.label).length / posts.length : 0;
    }
  }
}

export function* runSweep(spec: SweepSpec): Generator<{ done: number; total: number; cell: SweepCell }> {
  const ax = AXES.find((a) => a.id === spec.x)!;
  const ay = spec.y ? AXES.find((a) => a.id === spec.y)! : null;
  const ys = ay ? ay.values : [null];
  const total = ax.values.length * ys.length * spec.seeds;
  let done = 0;
  for (let yi = 0; yi < ys.length; yi++)
    for (let xi = 0; xi < ax.values.length; xi++) {
      const values: number[] = [];
      for (let k = 0; k < spec.seeds; k++) {
        const s = structuredClone(spec.base);
        s.seed = spec.base.seed + k * 101;
        s.adversary.enabled = true;
        ys[yi]?.apply(s);
        ax.values[xi].apply(s);
        const v = measure(s, spec.metric);
        if (v !== null && Number.isFinite(v)) values.push(v);
        done++;
      }
      const n = values.length;
      const mean = n ? values.reduce((a, b) => a + b, 0) / n : null;
      const sd = n > 1 && mean !== null ? Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : 0;
      yield { done, total, cell: { x: xi, y: yi, mean, ci: n > 1 ? (1.96 * sd) / Math.sqrt(n) : 0, n, values } };
    }
}
