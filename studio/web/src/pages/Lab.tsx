import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Download, GitBranch, Pause, Play, Save, SkipBack, SkipForward, Square, Zap } from "lucide-react";
import { motion } from "motion/react";
import { topicById } from "@/engine/topics";
import { download, primaryVariant, summaryOf, useLab, type Variant } from "@/store";
import { ScenarioPanel } from "@/components/ScenarioPanel";
import { NetworkCanvas, StanceLegend } from "@/components/NetworkCanvas";
import { Feed } from "@/components/Feed";
import { AgentInspector } from "@/components/AgentInspector";
import { CascadePanel } from "@/components/CascadePanel";
import { EChart, histogramOption, lineOption, SERIES } from "@/components/charts";
import { Button, cn, fmt, Segmented, Stat, Tip } from "@/components/ui";

const VARIANT_LABEL: Record<Variant, string> = { baseline: "Baseline twin", attacked: "Attacked", defended: "Defended" };

export default function Lab() {
  const st = useLab();
  const { scenario, runs, status, cursor, playing, speed, selected, view } = st;
  const nav = useNavigate();
  const [tab, setTab] = useState<"feed" | "agent" | "cascade" | "log">("feed");
  const run = runs[view] ?? runs[primaryVariant(scenario)];
  const last = run ? run.frames.length - 1 : 0;
  const round = Math.min(cursor, last);
  const frame = run?.frames[round];
  const topic = topicById(scenario.topic);
  const summary = summaryOf(runs);
  const streaming = status === "running" && scenario.engine.mind === "llm";

  // playback
  useEffect(() => {
    if (!playing || !run) return;
    if (cursor >= last) {
      if (status !== "running") st.setPlaying(false);
      return;
    }
    const t = setTimeout(() => st.setCursor(cursor + 1), 1000 / speed);
    return () => clearTimeout(t);
  }, [playing, cursor, last, speed, run, status]);

  // keyboard: space play/pause, arrows step
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || (e.target as HTMLElement)?.closest?.("[role=slider],[role=tablist]")) return;
      if (!run) return;
      if (e.key === " ") (e.preventDefault(), st.setPlaying(!playing));
      if (e.key === "ArrowRight") st.setCursor(Math.min(last, cursor + 1));
      if (e.key === "ArrowLeft") st.setCursor(Math.max(0, cursor - 1));
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [run, playing, cursor, last]);

  const onAgent = (id: number | null) => {
    st.select(id);
    if (id !== null) setTab("agent");
  };

  const events = useMemo(() => (run ? run.frames.flatMap((f) => f.events) : []), [run]);
  const meanLines = useMemo(
    () => (Object.keys(runs) as Variant[]).sort((a, b) => ["baseline", "attacked", "defended"].indexOf(a) - ["baseline", "attacked", "defended"].indexOf(b)).map((v) => ({ name: VARIANT_LABEL[v], color: SERIES[v], data: runs[v]!.frames.map((f) => f.metrics.mean), width: v === view ? 2.4 : 1.5 })),
    [runs, view],
  );
  const hist = useMemo(() => {
    if (!run || !frame) return null;
    const honest = run.agents.filter((a) => !a.attacker).map((a) => a.id);
    const groups = [{ name: "Round 0", color: "#3a3a3e", values: honest.map((i) => run.frames[0].stances[i]) }];
    groups.push({ name: `Round ${round}`, color: SERIES[view], values: honest.map((i) => frame.stances[i]) });
    return histogramOption(groups);
  }, [run, frame, round, view]);

  const m = frame?.metrics;
  const base = runs.baseline?.frames[Math.min(round, (runs.baseline?.frames.length ?? 1) - 1)]?.metrics;
  const target = scenario.adversary.target;

  const save = async () => {
    const b = await st.saveBundle();
    if (b) toast.success("Saved to the library", { description: b.name, action: { label: "Open", onClick: () => nav("/library") } });
  };

  return (
    <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)] xl:grid-cols-[300px_minmax(0,1fr)_380px]">
      {/* left: scenario designer */}
      <aside className="flex min-h-0 flex-col border-r border-border bg-ground lg:h-full">
        <div className="flex items-center justify-between px-4 pb-2 pt-5">
          <h2 className="text-[13px] font-semibold text-muted">Scenario designer</h2>
          <span className="num text-[11px] text-muted">seed {scenario.seed}</span>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          <ScenarioPanel />
        </div>
        <div className="border-t border-border p-3">
          {status === "running" ? (
            <Button variant="danger" className="w-full" onClick={st.stop}>
              <Square className="h-3.5 w-3.5" /> Stop · {st.progress.done}/{st.progress.total} rounds
            </Button>
          ) : (
            <Button variant="primary" className="w-full" onClick={() => st.run()}>
              <Zap className="h-3.5 w-3.5" /> Run with counterfactual twins
            </Button>
          )}
        </div>
      </aside>

      {/* centre */}
      <section className="flex min-h-0 min-w-0 flex-col gap-4 overflow-auto px-5 py-5 lg:px-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <h1 className="truncate text-[24px] font-semibold leading-tight">{scenario.name}</h1>
            <p className="mt-1 truncate text-[13px] text-muted">
              {scenario.society.n_agents} agents · {topic.question}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Tip label="Save to the library (this browser)" side="bottom">
              <Button size="icon" variant="ghost" aria-label="Save" disabled={!run} onClick={save}>
                <Save className="h-4 w-4" />
              </Button>
            </Tip>
            <Tip label="Download the runs as JSON" side="bottom">
              <Button size="icon" variant="ghost" aria-label="Download" disabled={!run} onClick={() => download(`${scenario.name.replace(/\W+/g, "_")}.narratesim.json`, { scenario, runs })}>
                <Download className="h-4 w-4" />
              </Button>
            </Tip>
            <Button size="sm" disabled={!run || status === "running"} onClick={() => nav("/compare")}>
              <GitBranch className="h-3.5 w-3.5" /> Fork and compare
            </Button>
          </div>
        </header>

        {Object.keys(runs).length > 1 && (
          <Segmented value={view} onChange={st.setView} options={(["baseline", "attacked", "defended"] as Variant[]).filter((v) => runs[v]).map((v) => ({ value: v, label: VARIANT_LABEL[v] }))} />
        )}

        {/* KPI strip */}
        <div className="card grid grid-cols-2 divide-x divide-border sm:grid-cols-3 lg:grid-cols-5">
          <Stat label="Mean stance" value={m ? fmt.signed(m.mean) : "—"} caption={base && view !== "baseline" ? `twin ${fmt.signed(base.mean)}` : `round ${round}`} />
          <Stat label="Attack effect" value={summary ? fmt.signed(summary.attack_effect) : "—"} tone={summary && summary.attack_effect > 0.3 ? "negative" : undefined} caption="final gap vs twin" />
          <Stat label="Protection" value={summary?.protection !== undefined && summary?.protection !== null ? fmt.pct(summary.protection) : "—"} tone={summary?.protection !== null && summary?.protection !== undefined ? (summary.protection < 0 ? "negative" : summary.protection > 0.5 ? "positive" : undefined) : undefined} caption={runs.defended ? "of the effect removed" : "no defense on"} />
          <Stat label="Reached" value={m ? fmt.pct(m.exposure) : "—"} caption="read an operation post" />
          <Stat label="Polarisation" value={m ? fmt.num(m.polarization, 3) : "—"} caption={`${m ? fmt.pct(m.silence) : "—"} silent`} />
        </div>

        {/* network */}
        <div className="card relative flex min-h-[440px] flex-1 flex-col overflow-hidden">
          {run ? (
            <>
              <div className="flex items-center justify-between px-4 pt-3">
                <div className="flex items-baseline gap-3">
                  <h2 className="text-[14px] font-semibold">Network</h2>
                  <span className="text-[12px] text-muted">{VARIANT_LABEL[view]} · round</span>
                  <motion.span key={round} initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="num -ml-2 text-[14px]">
                    {round}
                  </motion.span>
                  <span className="num text-[12px] text-muted">/ {scenario.society.rounds}</span>
                </div>
                <span className="hidden text-[11px] text-muted md:inline">drag to pan · scroll to zoom · double-click to fit</span>
              </div>
              <div className="relative min-h-0 flex-1">
                <NetworkCanvas run={run} round={round} selected={selected} onSelect={onAgent} className="absolute inset-0" />
                <div className="pointer-events-none absolute left-4 top-3 grid gap-1">
                  {frame?.events.map((e, i) => (
                    <motion.div key={`${round}-${i}`} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.08 }} className="w-fit rounded bg-raised px-2 py-1 text-[11px] text-soft">
                      {e.text}
                    </motion.div>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3 border-t border-rule px-3 py-2">
                <div className="flex items-center gap-0.5">
                  <Button size="iconSm" variant="ghost" aria-label="Previous round" onClick={() => st.setCursor(Math.max(0, round - 1))}>
                    <SkipBack className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="iconSm" variant="ghost" aria-label={playing ? "Pause" : "Play"} onClick={() => (round >= last && !playing ? (st.setCursor(0), st.setPlaying(true)) : st.setPlaying(!playing))}>
                    {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                  </Button>
                  <Button size="iconSm" variant="ghost" aria-label="Next round" onClick={() => st.setCursor(Math.min(last, round + 1))}>
                    <SkipForward className="h-3.5 w-3.5" />
                  </Button>
                </div>
                <Scrubber value={round} max={scenario.society.rounds} available={last} events={events.map((e) => e.round)} onChange={st.setCursor} />
                <select aria-label="Playback speed" value={speed} onChange={(e) => st.setSpeed(Number(e.target.value))} className="num h-7 rounded border border-control bg-surface px-1.5 text-[12px] text-soft">
                  {[1, 2, 3, 6, 12].map((x) => (
                    <option key={x} value={x}>
                      {x}×
                    </option>
                  ))}
                </select>
              </div>
              <div className="border-t border-rule px-4 py-2">
                <StanceLegend neg={topic.neg_label} pos={topic.pos_label} />
              </div>
            </>
          ) : (
            <EmptyLab running={status === "running"} />
          )}
        </div>

        {run && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="card px-4 pt-3">
              <h2 className="text-[14px] font-semibold">Mean stance over rounds</h2>
              <p className="text-[12px] text-muted">
                Each twin shares every random draw; only the operation and the defenses differ. Target: {target < 0 ? topic.neg_label : topic.pos_label}.
              </p>
              <EChart height={190} option={lineOption(meanLines, { yMin: -5, yMax: 5, cursor: round, legend: true, events: events.filter((e) => e.kind !== "suspension").map((e) => ({ round: e.round, label: e.text })) })} />
            </div>
            <div className="card px-4 pt-3">
              <h2 className="text-[14px] font-semibold">Stance distribution</h2>
              <p className="text-[12px] text-muted">Honest agents at round 0 and at round {round}.</p>
              {hist && <EChart height={190} option={hist} />}
            </div>
          </div>
        )}
      </section>

      {/* right rail */}
      <aside className="flex min-h-[560px] flex-col border-l border-border xl:h-full xl:min-h-0">
        <div className="px-4 pt-5">
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "feed", label: "Feed" },
              { value: "agent", label: "Agent" },
              { value: "cascade", label: "Cascade" },
              { value: "log", label: "Log" },
            ]}
          />
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {!run ? (
            <p className="px-4 py-6 text-[13px] text-muted">Run a scenario to read its feed.</p>
          ) : tab === "feed" ? (
            <Feed run={run} round={round} onAgent={onAgent} streaming={streaming} />
          ) : tab === "agent" ? (
            <AgentInspector runs={runs} view={view} id={selected} round={round} onAgent={onAgent} />
          ) : tab === "cascade" ? (
            <CascadePanel run={run} round={round} onAgent={onAgent} />
          ) : (
            <EventLog />
          )}
        </div>
      </aside>
    </div>
  );
}

function Scrubber({ value, max, available, events, onChange }: { value: number; max: number; available: number; events: number[]; onChange: (v: number) => void }) {
  const pct = (x: number) => `${(x / Math.max(1, max)) * 100}%`;
  return (
    <div className="relative mx-2 h-6 min-w-40 flex-1">
      <div className="absolute inset-x-0 top-1/2 h-[2px] -translate-y-1/2 bg-control" />
      <div className="absolute left-0 top-1/2 h-[2px] -translate-y-1/2 bg-muted" style={{ width: pct(available) }} />
      <div className="absolute left-0 top-1/2 h-[2px] -translate-y-1/2 bg-ink" style={{ width: pct(value) }} />
      {[...new Set(events)].map((r) => (
        <span key={r} className="absolute top-0 h-1.5 w-px bg-warning" style={{ left: pct(r) }} />
      ))}
      <input
        type="range"
        aria-label="Round"
        min={0}
        max={max}
        value={value}
        onChange={(e) => onChange(Math.min(available, Number(e.target.value)))}
        className="absolute inset-0 w-full cursor-pointer opacity-0"
      />
      <span className="pointer-events-none absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-ink" style={{ left: pct(value) }} />
    </div>
  );
}

function EmptyLab({ running }: { running: boolean }) {
  const { run } = useLab();
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 px-8 text-center">
      {running ? (
        <p className="shimmer text-[15px]">Building the society and its twins…</p>
      ) : (
        <>
          <p className="max-w-md text-[15px] leading-relaxed text-soft">Design a society on the left, or start from a preset. The run produces three twins that share every random draw: no operation, the operation alone, and the operation against your defenses.</p>
          <Button variant="primary" onClick={() => run()}>
            <Zap className="h-3.5 w-3.5" /> Run this scenario
          </Button>
          <p className="text-[12px] text-muted">Ctrl K opens the command menu.</p>
        </>
      )}
    </div>
  );
}

function EventLog() {
  const { runs, view, llmLog, message } = useLab();
  const run = runs[view];
  const evs = run ? run.frames.flatMap((f) => f.events) : [];
  const failed = llmLog.filter((l) => !l.ok).length;
  return (
    <div className="grid gap-4 px-4 py-4">
      {run?.meta && (
        <dl className="grid grid-cols-[110px_1fr] gap-y-1 text-[12px]">
          <dt className="text-muted">Run</dt>
          <dd className="num truncate text-soft">{run.meta.id}</dd>
          <dt className="text-muted">Engine</dt>
          <dd className="text-soft">
            {run.meta.engine} · {run.meta.mind}
            {run.meta.model ? ` · ${run.meta.model}` : ""}
          </dd>
          <dt className="text-muted">Wall time</dt>
          <dd className="num text-soft">{(run.meta.elapsed_ms / 1000).toFixed(2)} s</dd>
          {run.meta.llm_calls !== undefined && (
            <>
              <dt className="text-muted">LLM calls</dt>
              <dd className="num text-soft">
                {run.meta.llm_calls} · {failed} fell back
              </dd>
            </>
          )}
          {message && (
            <>
              <dt className="text-muted">Note</dt>
              <dd className="text-soft">{message}</dd>
            </>
          )}
        </dl>
      )}
      <ol className="grid gap-2">
        {evs.length === 0 && <li className="text-[12px] text-muted">No system events in this twin.</li>}
        {evs.map((e, i) => (
          <li key={i} className={cn("grid grid-cols-[40px_1fr] text-[12px]", e.kind === "suspension" ? "text-warning" : "text-soft")}>
            <span className="num text-muted">R{e.round}</span>
            {e.text}
          </li>
        ))}
      </ol>
    </div>
  );
}
