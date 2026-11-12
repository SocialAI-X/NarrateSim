import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GitBranch, Timer } from "lucide-react";
import { toast } from "sonner";
import { DEFENSE_LABEL, hasDefense, Simulation, triadSummary, variantOf } from "@/engine/engine";
import { topicById, VALUE_LABELS } from "@/engine/topics";
import type { DefenseKind, RunRecord, Scenario, StrategyId } from "@/engine/types";
import { primaryVariant, summaryOf, useLab, type Variant } from "@/store";
import { EChart, lineOption, SERIES } from "@/components/charts";
import { STRATEGIES } from "@/components/ScenarioPanel";
import { Button, Field, fmt, Select, Slider, Stat } from "@/components/ui";

const FORK_COLORS = ["#d9a441", "#44a282", "#c9c9cd", "#7fb0ea", "#e8a0ae"];

export default function Compare() {
  const { runs, scenario, forks, fork, view } = useLab();
  const nav = useNavigate();
  const summary = summaryOf(runs);
  const parent = runs[view] ?? runs[primaryVariant(scenario)];

  if (!parent) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-[24px] font-semibold">Counterfactuals</h1>
        <p className="mt-3 text-[14px] leading-relaxed text-soft">Nothing to compare yet. Run a scenario in the Lab first: every run comes with its baseline twin, and from here you can branch it at any round.</p>
        <Button className="mt-6" variant="primary" onClick={() => nav("/lab")}>
          Open the Lab
        </Button>
      </div>
    );
  }
  const t = scenario.adversary.target;
  const gap = (r: RunRecord) => r.frames.map((f, i) => (runs.baseline ? (f.metrics.mean - runs.baseline.frames[i].metrics.mean) * t : null));

  return (
    <div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold">Counterfactuals</h1>
          <p className="mt-1 max-w-3xl text-[14px] text-muted">
            {scenario.name}. Twins and forks share every random draw with their parent, so each gap below is caused by the change, not by chance.
          </p>
        </div>
      </header>

      <div className="card grid grid-cols-2 divide-x divide-border md:grid-cols-4">
        <Stat label="Attack effect" value={summary ? fmt.signed(summary.attack_effect) : "—"} caption="attacked − baseline, final round" />
        <Stat label="Residual with defenses" value={summary?.residual_effect !== null && summary ? fmt.signed(summary.residual_effect) : "—"} caption="defended − baseline" />
        <Stat label="Protection, final" value={summary?.protection !== null && summary ? fmt.pct(summary.protection) : "—"} caption="1 − residual / effect" />
        <Stat label="Protection, all rounds" value={summary?.protection_auc !== null && summary ? fmt.pct(summary.protection_auc) : "—"} caption="area between curves" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="card p-4">
          <h2 className="text-[14px] font-semibold">Gap to the baseline twin</h2>
          <p className="text-[12px] text-muted">Stance points toward the operation's target, per round. Zero means no difference from a world without the operation.</p>
          <EChart
            height={260}
            option={lineOption(
              [
                ...(runs.attacked ? [{ name: "Attacked", color: SERIES.attacked, data: gap(runs.attacked) }] : []),
                ...(runs.defended ? [{ name: "Defended", color: SERIES.defended, data: gap(runs.defended) }] : []),
                ...forks.map((f, i) => ({ name: (f.meta as any).label ?? `Fork ${i + 1}`, color: FORK_COLORS[i % FORK_COLORS.length], data: gap(f), dashed: true })),
              ],
              { legend: true },
            )}
          />
        </div>
        <Vulnerability runs={runs} />
      </div>

      <ForkLab parent={parent} scenario={scenario} onFork={(at, patch, label) => {
        try {
          fork(at, patch, label);
          toast.success(label);
        } catch (e) {
          toast.error((e as Error).message);
        }
      }} forks={forks} />

      <TimingCurve scenario={scenario} />
    </div>
  );
}

/** Who did the operation move? Per-agent difference between the attacked and baseline twins. */
function Vulnerability({ runs }: { runs: Partial<Record<Variant, RunRecord>> }) {
  const [dim, setDim] = useState(1);
  const { scenario } = useLab();
  const data = useMemo(() => {
    if (!runs.attacked || !runs.baseline) return null;
    const a = runs.attacked;
    const b = runs.baseline;
    const t = scenario.adversary.target;
    const last = a.frames.length - 1;
    return a.agents.filter((x) => !x.attacker).map((x) => [x.values[dim], (a.frames[last].stances[x.id] - b.frames[last].stances[x.id]) * t, x.degree]);
  }, [runs, dim, scenario]);
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-[14px] font-semibold">Who was moved</h2>
          <p className="text-[12px] text-muted">Each dot is a person: their value score against how far the operation moved them, relative to their own baseline twin.</p>
        </div>
        <div className="w-44 shrink-0">
          <Select ariaLabel="Value" value={String(dim)} onChange={(v) => setDim(Number(v))} options={VALUE_LABELS.map((l, i) => ({ value: String(i), label: l }))} />
        </div>
      </div>
      {data ? (
        <EChart
          height={260}
          option={{
            grid: { left: 40, right: 12, top: 16, bottom: 30 },
            xAxis: { type: "value", min: 1, max: 10, name: VALUE_LABELS[dim], nameLocation: "middle", nameGap: 22, nameTextStyle: { color: "#8a8c92", fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#8a8c92", fontSize: 11 }, splitLine: { show: false } },
            yAxis: { type: "value", axisLine: { show: false }, axisLabel: { color: "#8a8c92", fontSize: 11 }, splitLine: { lineStyle: { color: "#232327", type: "dashed" } } },
            tooltip: { backgroundColor: "#212023", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12 }, formatter: (p: any) => `value ${p.data[0].toFixed(1)}<br/>moved ${p.data[1] > 0 ? "+" : ""}${p.data[1].toFixed(2)} toward target` },
            series: [{ type: "scatter", data, symbolSize: (d: number[]) => 4 + Math.sqrt(d[2]) * 1.4, itemStyle: { color: "rgba(229,86,111,0.65)" } }],
          }}
        />
      ) : (
        <p className="py-10 text-[13px] text-muted">Needs an attacked twin.</p>
      )}
    </div>
  );
}

function ForkLab({ parent, scenario, onFork, forks }: { parent: RunRecord; scenario: Scenario; onFork: (at: number, patch: Partial<Scenario>, label: string) => void; forks: RunRecord[] }) {
  const R = scenario.society.rounds;
  const [at, setAt] = useState(Math.min(6, R - 1));
  const [kind, setKind] = useState<"stop" | "defense" | "framing">("defense");
  const [defense, setDefense] = useState<DefenseKind>("prebunking");
  const [framing, setFraming] = useState<StrategyId>("pseudo_rational");
  const topic = topicById(scenario.topic);

  const go = () => {
    const s = structuredClone(parent.scenario);
    let label = "";
    if (kind === "stop") {
      s.adversary.end = at;
      label = `Operation stopped after round ${at}`;
    } else if (kind === "defense") {
      s.defenses = s.defenses.map((d) => (d.kind === defense ? { ...d, enabled: true, start: at + 1 } : d));
      label = `${DEFENSE_LABEL[defense]} from round ${at + 1}`;
    } else {
      s.adversary.strategy = framing;
      label = `Switch to ${framing.replace(/_/g, " ")} after round ${at}`;
    }
    onFork(at, { adversary: s.adversary, defenses: s.defenses }, label);
  };

  const t = scenario.adversary.target;
  const parentFinal = parent.frames[parent.frames.length - 1].metrics.mean;
  return (
    <div className="card grid gap-4 p-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="grid content-start gap-4">
        <div>
          <h2 className="text-[14px] font-semibold">Fork the {parent.meta.variant} run</h2>
          <p className="text-[12px] text-muted">Restore the society exactly as it was after a round and continue it with one change.</p>
        </div>
        <Slider label="Branch after round" value={at} min={0} max={R - 1} onChange={setAt} />
        <Field label="Change">
          <Select
            ariaLabel="Change"
            value={kind}
            onChange={setKind}
            options={[
              { value: "defense", label: "Switch a defense on" },
              { value: "stop", label: "Stop the operation" },
              { value: "framing", label: "Change the framing" },
            ]}
          />
        </Field>
        {kind === "defense" && <Select ariaLabel="Defense" value={defense} onChange={setDefense} options={(Object.keys(DEFENSE_LABEL) as DefenseKind[]).map((k) => ({ value: k, label: DEFENSE_LABEL[k] }))} />}
        {kind === "framing" && <Select ariaLabel="Framing" value={framing} onChange={setFraming} options={STRATEGIES} />}
        <Button variant="primary" onClick={go} disabled={!parent.scenario.adversary.enabled && kind !== "defense"}>
          <GitBranch className="h-3.5 w-3.5" /> Branch
        </Button>
      </div>
      <div className="min-w-0">
        <EChart
          height={240}
          option={lineOption(
            [{ name: `Parent (${parent.meta.variant})`, color: SERIES[parent.meta.variant as Variant] ?? SERIES.ink, data: parent.frames.map((f) => f.metrics.mean) }, ...forks.map((f, i) => ({ name: (f.meta as any).label, color: FORK_COLORS[i % FORK_COLORS.length], data: f.frames.map((x) => x.metrics.mean), dashed: true }))],
            { yMin: -5, yMax: 5, legend: true, cursor: at },
          )}
        />
        {forks.length > 0 && (
          <table className="mt-2 w-full text-[13px]">
            <thead>
              <tr className="text-left text-[12px] text-muted">
                <th className="py-1.5 font-normal">Fork</th>
                <th className="py-1.5 text-right font-normal">Final mean</th>
                <th className="py-1.5 text-right font-normal">vs parent, toward {t < 0 ? topic.neg_label.toLowerCase() : topic.pos_label.toLowerCase()}</th>
              </tr>
            </thead>
            <tbody>
              {forks.map((f, i) => {
                const fin = f.frames[f.frames.length - 1].metrics.mean;
                return (
                  <tr key={f.meta.id} className="border-t border-rule">
                    <td className="py-1.5 text-soft">
                      <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: FORK_COLORS[i % FORK_COLORS.length] }} />
                      {(f.meta as any).label}
                    </td>
                    <td className="num py-1.5 text-right">{fmt.signed(fin)}</td>
                    <td className="num py-1.5 text-right">{fmt.signed((fin - parentFinal) * t)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/** Protection as a function of when the defense starts. */
function TimingCurve({ scenario }: { scenario: Scenario }) {
  const [kind, setKind] = useState<DefenseKind>(scenario.defenses.find((d) => d.enabled)?.kind ?? "prebunking");
  const [curve, setCurve] = useState<{ start: number; p: number | null }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const compute = () => {
    setBusy(true);
    setTimeout(() => {
      const base = structuredClone(scenario);
      base.engine.mind = "heuristic";
      base.adversary.enabled = true;
      const R = base.society.rounds;
      const b = new Simulation(variantOf(base, "baseline")).runSync().record();
      const a = new Simulation(variantOf(base, "attacked")).runSync().record();
      const out: { start: number; p: number | null }[] = [];
      for (let start = 1; start <= R; start++) {
        const s = structuredClone(base);
        s.defenses = s.defenses.map((d) => ({ ...d, enabled: d.kind === kind, start }));
        const d = new Simulation(variantOf(s, "defended")).runSync().record();
        out.push({ start, p: triadSummary(b, a, d).protection_auc });
      }
      setCurve(out);
      setBusy(false);
    }, 20);
  };
  return (
    <div className="card grid gap-4 p-4 lg:grid-cols-[320px_minmax(0,1fr)]">
      <div className="grid content-start gap-4">
        <div>
          <h2 className="text-[14px] font-semibold">When does a defense have to start?</h2>
          <p className="text-[12px] text-muted">Runs the same defense starting at every round and plots the protection it buys, against the same attacked twin.</p>
        </div>
        <Select ariaLabel="Defense" value={kind} onChange={setKind} options={(Object.keys(DEFENSE_LABEL) as DefenseKind[]).filter((k) => k !== "suspension").map((k) => ({ value: k, label: DEFENSE_LABEL[k] }))} />
        <Button variant="primary" onClick={compute} disabled={busy}>
          <Timer className="h-3.5 w-3.5" /> {busy ? "Running…" : `Run ${scenario.society.rounds + 2} simulations`}
        </Button>
        {hasDefense(scenario) && <p className="text-[11px] text-muted">Other defenses in the scenario are switched off for this curve.</p>}
      </div>
      <div className="min-w-0">
        {curve ? (
          <EChart
            height={240}
            option={{
              ...lineOption([{ name: "Protection", color: SERIES.defended, data: curve.map((c) => c.p) }], { yFormat: (v) => `${Math.round(v * 100)}%`, xName: "start round" }),
              xAxis: { type: "category", data: curve.map((c) => c.start), boundaryGap: false, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#8a8c92", fontSize: 11 } },
            }}
          />
        ) : (
          <div className="flex h-[240px] items-center justify-center rounded border border-dashed border-control text-[13px] text-muted">The curve appears here.</div>
        )}
      </div>
    </div>
  );
}
