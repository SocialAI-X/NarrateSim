import { useNavigate } from "react-router-dom";
import { DEFENSE_LABEL } from "@/engine/engine";
import { PRESETS } from "@/engine/presets";
import { POPULATIONS, TOPICS, topicById } from "@/engine/topics";
import type { DefenseKind, DefenseSpec, Scenario, StrategyId } from "@/engine/types";
import { useLab } from "@/store";
import { Field, Input, Pill, Section, Segmented, Select, Slider, Switch } from "./ui";

export const STRATEGIES: { value: StrategyId; label: string; hint: string }[] = [
  { value: "victim_narrative", label: "Victim narrative", hint: "Named, painful stories of harm" },
  { value: "fear_appeal", label: "Fear appeal", hint: "Concrete threats about what comes next" },
  { value: "pseudo_rational", label: "Pseudo-rational", hint: "Calm statistics and demands for data" },
  { value: "conspiracy", label: "Conspiracy", hint: "Hidden interests, who profits" },
  { value: "fake_authority", label: "Fake authority", hint: "Unnamed insiders who 'privately agree'" },
  { value: "bandwagon", label: "Bandwagon", hint: "Everyone is already turning" },
];

const DEFENSE_HELP: Record<DefenseKind, string> = {
  prebunking: "Teaches a share of people the manipulation tactics before they meet them.",
  fact_check: "Periodic notices that discount claim-based posts for people who trust institutions.",
  community_notes: "Readers who strongly disagree attach notes; noted authors stay noted.",
  guardian: "A noisy classifier scores every post; above threshold it labels, downranks or removes.",
  suspension: "Accounts that collect enough flags are suspended, honest ones included.",
  reflection_prompt: "Asks everyone to question their reactions. It also lowers certainty.",
  climate_report: "Shows how heated the thread is; cools arousal for a round.",
};

export function ScenarioPanel() {
  const { scenario: s, setScenario, loadScenario, status } = useLab();
  const nav = useNavigate();
  const up = (f: (s: Scenario) => void) =>
    setScenario((x) => {
      f(x);
      return x;
    });
  const topic = topicById(s.topic);
  const R = s.society.rounds;
  const setDef = (kind: DefenseKind, p: Partial<DefenseSpec>) => up((x) => (x.defenses = x.defenses.map((d) => (d.kind === kind ? { ...d, ...p } : d))));
  const nDef = s.defenses.filter((d) => d.enabled).length;

  return (
    <div aria-disabled={status === "running"} className={status === "running" ? "pointer-events-none opacity-60" : ""}>
      <Section title="Scenario">
        <Field label="Start from a preset">
          <Select
            ariaLabel="Preset"
            value={PRESETS.find((p) => p.title === s.name)?.id ?? ("" as string)}
            onChange={(id) => loadScenario(PRESETS.find((p) => p.id === id)!.scenario)}
            options={PRESETS.map((p) => ({ value: p.id, label: p.title, hint: p.blurb }))}
          />
        </Field>
        <Field label="Name">
          <Input value={s.name} onChange={(e) => up((x) => (x.name = e.target.value))} />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Seed">
            <Input className="num" type="number" value={s.seed} onChange={(e) => up((x) => (x.seed = Math.max(0, Number(e.target.value) | 0)))} />
          </Field>
          <Field label="Rounds">
            <Input className="num" type="number" min={2} max={60} value={R} onChange={(e) => up((x) => (x.society.rounds = Math.max(2, Math.min(60, Number(e.target.value) | 0))))} />
          </Field>
        </div>
      </Section>

      <Section title="Topic" aside={<span className="max-w-36 truncate text-[12px] text-muted">{topic.title}</span>}>
        <Select ariaLabel="Topic" value={topic.id} onChange={(v) => up((x) => (x.topic = v))} options={TOPICS.map((t) => ({ value: t.id, label: t.title, hint: t.question }))} />
        <p className="text-[12px] leading-relaxed text-soft">{topic.question}</p>
        <div className="flex flex-wrap gap-1.5">
          <Pill tone="negative">−5 {topic.neg_label}</Pill>
          <Pill tone="accent">+5 {topic.pos_label}</Pill>
        </div>
      </Section>

      <Section title="Society">
        <Slider label="Agents" value={s.society.n_agents} min={20} max={600} step={10} onChange={(v) => up((x) => (x.society.n_agents = v))} />
        <Field label="Value profile" hint={POPULATIONS[s.society.population].note}>
          <Select ariaLabel="Value profile" value={s.society.population} onChange={(v) => up((x) => (x.society.population = v))} options={Object.entries(POPULATIONS).map(([k, p]) => ({ value: k as Scenario["society"]["population"], label: p.label }))} />
        </Field>
      </Section>

      <Section title="Network and feed" defaultOpen={false}>
        <Field label="Topology">
          <Select
            ariaLabel="Topology"
            value={s.network.kind}
            onChange={(v) => up((x) => (x.network.kind = v))}
            options={[
              { value: "scale_free", label: "Scale-free", hint: "Barabási–Albert: a few hubs" },
              { value: "small_world", label: "Small world", hint: "Watts–Strogatz: local clusters, short paths" },
              { value: "random", label: "Random", hint: "Erdős–Rényi: no structure" },
              { value: "communities", label: "Echo chambers", hint: "Stochastic blocks with dense insides" },
            ]}
          />
        </Field>
        <Slider label={s.network.kind === "scale_free" ? "Ties per new agent" : "Ties per side"} value={s.network.degree} min={1} max={8} onChange={(v) => up((x) => (x.network.degree = v))} />
        {s.network.kind === "small_world" && <Slider label="Rewiring" value={s.network.rewire} min={0} max={1} step={0.05} format={(v) => v.toFixed(2)} onChange={(v) => up((x) => (x.network.rewire = v))} />}
        {s.network.kind === "communities" && (
          <>
            <Slider label="Communities" value={s.network.communities} min={2} max={6} onChange={(v) => up((x) => (x.network.communities = v))} />
            <Slider label="Ties inside a community" value={s.network.homophily} min={0.5} max={0.98} step={0.02} format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => up((x) => (x.network.homophily = v))} />
          </>
        )}
        <Field label="Feed ranking">
          <Segmented size="sm" value={s.feed.ranking} onChange={(v) => up((x) => (x.feed.ranking = v))} options={[{ value: "chronological", label: "Chronological" }, { value: "engagement", label: "Engagement-ranked" }]} />
        </Field>
        <Slider label="Posts read per round" value={s.feed.capacity} min={2} max={20} onChange={(v) => up((x) => (x.feed.capacity = v))} />
      </Section>

      <Section title="Operation" aside={<Switch label="Operation on" checked={s.adversary.enabled} onChange={(v) => up((x) => (x.adversary.enabled = v))} />}>
        <div className={s.adversary.enabled ? "grid gap-3.5" : "pointer-events-none grid gap-3.5 opacity-40"}>
          <Field label="Framing" hint={STRATEGIES.find((x) => x.value === s.adversary.strategy)?.hint}>
            <Select ariaLabel="Framing" value={s.adversary.strategy} onChange={(v) => up((x) => (x.adversary.strategy = v))} options={STRATEGIES} />
          </Field>
          <Field label="Pushes toward">
            <Segmented size="sm" value={String(s.adversary.target) as "-1" | "1"} onChange={(v) => up((x) => (x.adversary.target = Number(v) as -1 | 1))} options={[{ value: "-1", label: topic.neg_label }, { value: "1", label: topic.pos_label }]} />
          </Field>
          <Slider label="Accounts" value={s.adversary.n_attackers} min={1} max={20} onChange={(v) => up((x) => (x.adversary.n_attackers = v))} />
          <Field label="Placement">
            <Select
              ariaLabel="Placement"
              value={s.adversary.placement}
              onChange={(v) => up((x) => (x.adversary.placement = v))}
              options={[
                { value: "hub", label: "Hubs", hint: "Highest degree" },
                { value: "bridge", label: "Bridges", hint: "Highest betweenness" },
                { value: "random", label: "Random", hint: "Anywhere" },
                { value: "periphery", label: "Periphery", hint: "Lowest degree" },
              ]}
            />
          </Field>
          <Field label="Coordination">
            <Select
              ariaLabel="Coordination"
              value={s.adversary.coordination}
              onChange={(v) => up((x) => (x.adversary.coordination = v))}
              options={[
                { value: "independent", label: "Independent", hint: "Each account works alone" },
                { value: "echo", label: "Echo", hint: "Followers amplify the lead account" },
                { value: "complementary", label: "Complementary", hint: "Accounts split three framings" },
                { value: "escalating", label: "Escalating", hint: "Data, then fear, then conspiracy" },
              ]}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Slider label="Starts" value={s.adversary.start} min={1} max={R} onChange={(v) => up((x) => (x.adversary.start = v))} />
            <Slider label="Stops" value={s.adversary.end < 0 ? R : s.adversary.end} min={1} max={R} format={(v) => (v >= R ? "end" : String(v))} onChange={(v) => up((x) => (x.adversary.end = v >= R ? -1 : v))} />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[12px] text-muted">Adaptive targeting of undecided neighbours</span>
            <Switch label="Adaptive targeting" checked={s.adversary.adaptive} onChange={(v) => up((x) => (x.adversary.adaptive = v))} />
          </div>
        </div>
      </Section>

      <Section title="Defenses" aside={<span className="num text-[12px] text-muted">{nDef} on</span>}>
        {s.defenses.map((d) => (
          <div key={d.kind} className="grid gap-2.5 border-t border-rule pt-3 first:border-0 first:pt-0">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[13px] font-medium">{DEFENSE_LABEL[d.kind]}</div>
                <div className="text-[11px] leading-snug text-muted">{DEFENSE_HELP[d.kind]}</div>
              </div>
              <Switch label={DEFENSE_LABEL[d.kind]} checked={d.enabled} onChange={(v) => setDef(d.kind, { enabled: v })} />
            </div>
            {d.enabled && (
              <div className="grid grid-cols-2 gap-x-3 gap-y-2.5">
                <Slider label="Starts at round" value={d.start} min={1} max={R} onChange={(v) => setDef(d.kind, { start: v })} />
                {d.kind !== "suspension" && <Slider label="Strength" value={d.strength} min={0.1} max={1} step={0.05} format={(v) => v.toFixed(2)} onChange={(v) => setDef(d.kind, { strength: v })} />}
                {d.kind === "prebunking" && <Slider label="Coverage" value={d.coverage ?? 0.6} min={0.1} max={1} step={0.05} format={(v) => `${Math.round(v * 100)}%`} onChange={(v) => setDef(d.kind, { coverage: v })} />}
                {(d.kind === "fact_check" || d.kind === "climate_report") && <Slider label="Every N rounds" value={d.every ?? 3} min={1} max={6} onChange={(v) => setDef(d.kind, { every: v })} />}
                {d.kind === "guardian" && <Slider label="Threshold" value={d.threshold ?? 0.66} min={0.3} max={0.95} step={0.01} format={(v) => v.toFixed(2)} onChange={(v) => setDef(d.kind, { threshold: v })} />}
                {d.kind === "community_notes" && <Slider label="Raters needed" value={d.quorum ?? 3} min={1} max={8} onChange={(v) => setDef(d.kind, { quorum: v })} />}
                {d.kind === "suspension" && <Slider label="Flags before suspension" value={d.strikes ?? 3} min={1} max={8} onChange={(v) => setDef(d.kind, { strikes: v })} />}
                {d.kind === "guardian" && (
                  <div className="col-span-2">
                    <Segmented size="sm" value={d.action ?? "label"} onChange={(v) => setDef(d.kind, { action: v })} options={[{ value: "label", label: "Label" }, { value: "downrank", label: "Downrank" }, { value: "remove", label: "Remove" }]} />
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </Section>

      <Section title="Agent mind" aside={<span className="text-[12px] text-muted">{s.engine.mind === "llm" ? "LLM" : "Heuristic"}</span>}>
        <Segmented
          value={s.engine.mind}
          onChange={(v) => up((x) => (x.engine.mind = v))}
          options={[
            { value: "heuristic", label: "Heuristic (instant)" },
            { value: "llm", label: "LLM agents" },
          ]}
        />
        {s.engine.mind === "llm" ? (
          <p className="text-[12px] leading-relaxed text-soft">
            Every agent writes a belief–desire–intention trace and a JSON decision each round. Expect about {(s.society.n_agents * R * (s.defenses.some((d) => d.enabled) ? 3 : 2)).toLocaleString()} calls for the full set of twins.{" "}
            <button className="text-accent hover:underline" onClick={() => nav("/settings")}>
              Configure the model
            </button>
            .
          </p>
        ) : (
          <p className="text-[12px] leading-relaxed text-soft">A calibrated cognitive model: value-matched susceptibility, bounded confidence, emotional contagion, spiral of silence. Same protocol as the LLM agents, milliseconds per run.</p>
        )}
      </Section>
    </div>
  );
}
