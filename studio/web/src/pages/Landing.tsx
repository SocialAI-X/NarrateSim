import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchExamples, loadExample, type ExampleEntry } from "@/pages/Library";
import { motion } from "motion/react";
import { ArrowRight, Github } from "lucide-react";
import { Simulation, triadSummary, variantOf } from "@/engine/engine";
import { PRESETS } from "@/engine/presets";
import { topicById } from "@/engine/topics";
import type { RunRecord, Scenario } from "@/engine/types";
import { Mark, REPO_URL } from "@/App";
import { NetworkCanvas, StanceLegend } from "@/components/NetworkCanvas";
import { EChart, lineOption, SERIES } from "@/components/charts";
import { cn, fmt } from "@/components/ui";
import { useLab } from "@/store";

type Choice = "none" | "early" | "late" | "guardian";
const CHOICES: { id: Choice; label: string }[] = [
  { id: "none", label: "No defense" },
  { id: "early", label: "Prebunk at round 1" },
  { id: "late", label: "Prebunk at round 6" },
  { id: "guardian", label: "Guardian classifier" },
];

function scenarioFor(c: Choice): Scenario {
  const s = structuredClone(PRESETS[0].scenario);
  s.society.n_agents = 150;
  const on = (kind: string, patch: object) => (s.defenses = s.defenses.map((d) => (d.kind === kind ? { ...d, enabled: true, ...patch } : d)));
  if (c === "early") on("prebunking", { start: 1 });
  if (c === "late") on("prebunking", { start: 6 });
  if (c === "guardian") on("guardian", { start: 2, action: "downrank" });
  return s;
}

function useHeroRuns() {
  return useMemo(() => {
    const base = scenarioFor("none");
    const baseline = new Simulation(variantOf(base, "baseline"), "baseline").runSync().record();
    const attacked = new Simulation(variantOf(base, "attacked"), "attacked").runSync().record();
    const out: Record<Choice, RunRecord> = { none: attacked } as Record<Choice, RunRecord>;
    for (const c of ["early", "late", "guardian"] as Choice[]) out[c] = new Simulation(variantOf(scenarioFor(c), "defended"), "defended").runSync().record();
    return { baseline, attacked, out };
  }, []);
}

export default function Landing() {
  const { baseline, attacked, out } = useHeroRuns();
  const [choice, setChoice] = useState<Choice>("none");
  const [round, setRound] = useState(0);
  const run = out[choice];
  const R = run.frames.length - 1;
  const topic = topicById(run.scenario.topic);
  const loadScenario = useLab((s) => s.loadScenario);
  const openBundle = useLab((s) => s.openBundle);
  const nav = useNavigate();
  const [examples, setExamples] = useState<ExampleEntry[]>([]);
  useEffect(() => void fetchExamples().then(setExamples), []);
  const replay = async () => {
    openBundle(await loadExample(examples[0].file));
    nav("/lab");
  };

  useEffect(() => {
    const t = setTimeout(() => setRound((r) => (r >= R ? 0 : r + 1)), round >= R ? 2600 : 700);
    return () => clearTimeout(t);
  }, [round, R]);

  const sum = choice === "none" ? triadSummary(baseline, attacked) : triadSummary(baseline, attacked, run);
  const f = run.frames[round];

  return (
    <div className="min-h-full bg-ground text-ink">
      {/* bar */}
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-4 py-4 sm:px-8">
        <Link to="/" className="flex items-center gap-2.5 whitespace-nowrap text-[15px] font-semibold">
          <Mark size={24} /> NarrateSim Studio
        </Link>
        <nav className="flex items-center gap-5 text-[13px] text-soft">
          <Link to="/method" className="hidden hover:text-ink sm:inline">
            Method
          </Link>
          <a href={REPO_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-ink">
            <Github className="h-4 w-4" /> <span className="hidden sm:inline">Source</span>
          </a>
          <Link to="/lab" className="inline-flex h-9 items-center gap-1.5 whitespace-nowrap rounded-full bg-ink px-4 font-medium text-surface transition-colors hover:bg-soft">
            Open the Lab <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </nav>
      </div>

      {/* hero: the product performs */}
      <section className="mx-auto grid max-w-[1440px] gap-8 px-4 pb-20 pt-10 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12 lg:pt-16">
        <div className="flex flex-col justify-center">
          <motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: [0.2, 0.7, 0.2, 1] }} className="text-[44px] font-semibold leading-[1.02] tracking-[-0.03em] sm:text-[64px] xl:text-[76px]">
            Watch a narrative take over a network.
          </motion.h1>
          <motion.p initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08, duration: 0.5 }} className="mt-6 max-w-[34rem] text-[17px] leading-relaxed text-soft">
            NarrateSim Studio is an open simulator of LLM-agent social networks. Plant a coordinated operation, switch on a defense, and measure what it changed against a twin world without it.
          </motion.p>
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16, duration: 0.5 }} className="mt-8 flex flex-wrap items-center gap-4">
            <Link to="/lab" className="inline-flex h-11 items-center gap-2 rounded-full bg-ink px-6 text-[14px] font-medium text-surface transition-[background,transform] hover:bg-soft active:scale-[0.97]">
              Open the Lab <ArrowRight className="h-4 w-4" />
            </Link>
            {examples.length > 0 && <button onClick={replay} className="inline-flex h-11 items-center rounded-full border border-control px-5 text-[14px] text-soft transition-colors hover:border-muted hover:text-ink">
              Replay a recorded LLM society
            </button>}
          </motion.div>
          <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }} className="mt-4 text-[13px] text-muted">
            Runs in your browser. No install, no key.
          </motion.p>
        </div>

        <motion.div data-ui initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.1, duration: 0.7 }} className="card flex min-h-[520px] flex-col overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-3">
            <div className="text-[13px]">
              <span className="font-semibold">{topic.title}</span>
              <span className="text-muted"> · 150 agents · 4 operation accounts on the hubs</span>
            </div>
            <span className="num text-[12px] text-muted">
              round {round} / {R}
            </span>
          </div>
          <div role="tablist" aria-label="Defense" className="mx-4 mt-3 flex flex-wrap gap-x-5 gap-y-1 border-b border-border">
            {CHOICES.map((c) => (
              <button key={c.id} role="tab" aria-selected={choice === c.id} data-active={choice === c.id} onClick={() => (setChoice(c.id), setRound(0))} className={cn("sel-line pb-2 text-[13px] transition-colors", choice === c.id ? "text-ink" : "text-muted hover:text-soft")}>
                {c.label}
              </button>
            ))}
          </div>
          <div className="relative min-h-[320px] flex-1">
            <NetworkCanvas run={run} round={round} selected={null} className="absolute inset-0" />
          </div>
          <div className="grid grid-cols-3 divide-x divide-border border-t border-border">
            <div className="px-4 py-3">
              <div className="text-[12px] text-muted">Mean stance now</div>
              <div className="num text-[20px]">{fmt.signed(f.metrics.mean)}</div>
            </div>
            <div className="px-4 py-3">
              <div className="text-[12px] text-muted">Pulled toward "{topic.neg_label.toLowerCase()}"</div>
              <div className="num text-[20px] text-negative">{fmt.signed(sum.attack_effect)}</div>
            </div>
            <div className="px-4 py-3">
              <div className="text-[12px] text-muted">Protection</div>
              <div className="num text-[20px]">{choice === "none" ? "—" : fmt.pct(sum.protection_auc)}</div>
            </div>
          </div>
          <div className="border-t border-rule px-4 py-2">
            <StanceLegend neg={topic.neg_label} pos={topic.pos_label} />
          </div>
        </motion.div>
      </section>

      {/* twins */}
      <section className="bg-surface py-24">
        <div className="mx-auto grid max-w-[1440px] gap-10 px-4 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-12">
          <div>
            <h2 className="text-[36px] font-semibold leading-[1.05] tracking-[-0.02em] sm:text-[44px]">Every run comes with its twin.</h2>
            <p className="mt-5 max-w-[34rem] text-[16px] leading-relaxed text-soft">
              The simulator draws all randomness from a hash of seed, round and agent. A world without the operation, a world with it, and a world with it and a defense make the same choices wherever the treatment does not reach. The gap between the curves is the effect; nothing else moves them.
            </p>
            <p className="mt-4 max-w-[34rem] text-[16px] leading-relaxed text-soft">The same property lets you fork any run after any round, change one thing, and continue.</p>
          </div>
          <div data-ui className="card p-4">
            <h3 className="text-[14px] font-semibold">Mean stance on "{topic.question}"</h3>
            <p className="text-[12px] text-muted">The four worlds of the panel above, all rounds.</p>
            <EChart
              height={300}
              option={lineOption(
                [
                  { name: "No operation", color: SERIES.baseline, data: baseline.frames.map((x) => x.metrics.mean) },
                  { name: "Operation, no defense", color: SERIES.attacked, data: attacked.frames.map((x) => x.metrics.mean) },
                  { name: "Prebunk at round 1", color: SERIES.defended, data: out.early.frames.map((x) => x.metrics.mean) },
                  { name: "Prebunk at round 6", color: SERIES.fork, data: out.late.frames.map((x) => x.metrics.mean), dashed: true },
                ],
                { legend: true, yMin: -2, yMax: 3 },
              )}
            />
          </div>
        </div>
      </section>

      {/* what's inside */}
      <section className="mx-auto max-w-[1440px] px-4 py-24 sm:px-8">
        <h2 className="max-w-3xl text-[36px] font-semibold leading-[1.05] tracking-[-0.02em] sm:text-[44px]">An experiment platform, not a demo.</h2>
        <div className="mt-12 grid gap-x-16 gap-y-10 md:grid-cols-2">
          {[
            ["Two minds, one protocol", "LLM agents write a belief–desire–intention trace and a JSON decision on any OpenAI-compatible model. A calibrated heuristic mind fills the same fields in milliseconds, so a 120-agent run takes about 40 ms in the browser."],
            ["Six framings, four coordination modes", "Victim narratives, fear appeals, pseudo-rational doubt, conspiracy, fake authority and bandwagon, run by independent, echoing, complementary or escalating cells placed on hubs, bridges, at random or on the periphery."],
            ["Seven defenses with real errors", "Prebunking, fact-check notices, community notes, a Guardian classifier that labels, downranks or removes, suspensions, reflection prompts and climate reports. Detectors flag honest people too, and the studio counts it."],
            ["Cascades you can trace", "Every stance change is attributed to the post that caused it. The cascade view separates people the operation moved directly from those moved second-hand by honest neighbours."],
            ["Sweeps with intervals", "Cross any two factors, replicate each cell over seeds in a background worker, read effects with 95% intervals, export CSV, and open any cell in the Lab."],
            ["Server and CLI for long runs", "A FastAPI service streams runs over WebSocket, holds the model key as a gateway, and runs LLM experiments headless. Python and browser engines share one RNG and one run format."],
          ].map(([h, p], i) => (
            <motion.div key={h} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} transition={{ delay: (i % 2) * 0.08, duration: 0.5 }}>
              <h3 className="text-[20px] font-semibold">{h}</h3>
              <p className="mt-2 max-w-[36rem] text-[15px] leading-relaxed text-soft">{p}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* run it */}
      <section className="bg-surface py-24">
        <div className="mx-auto grid max-w-[1440px] gap-10 px-4 sm:px-8 lg:grid-cols-2">
          <div>
            <h2 className="text-[36px] font-semibold leading-[1.05] tracking-[-0.02em] sm:text-[44px]">Run LLM societies on your machine.</h2>
            <p className="mt-5 max-w-[34rem] text-[16px] leading-relaxed text-soft">Point the service at DeepSeek, OpenAI or a local vLLM server. The console connects to it from this page or from its own address.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              {PRESETS.slice(0, 4).map((p) => (
                <Link key={p.id} to="/lab" onClick={() => loadScenario(p.scenario)} className="rounded-full border border-control px-4 py-2 text-[13px] text-soft transition-colors hover:border-muted hover:text-ink">
                  {p.title}
                </Link>
              ))}
            </div>
          </div>
          <pre className="num overflow-auto rounded-md bg-ground p-5 text-[13px] leading-[1.8] text-soft">
            {`# code: ${REPO_URL}
cd NarrateSim/studio/backend
pip install -e .

export NARRATESIM_LLM_BASE_URL=https://api.deepseek.com/v1
export NARRATESIM_LLM_MODEL=deepseek-chat
export NARRATESIM_LLM_API_KEY=sk-…

narratesim serve                # API + console on :8765
narratesim run examples/hub_victim.json --mind llm
narratesim sweep examples/hub_victim.json \\
    --x strategy --y population --seeds 5`}
          </pre>
        </div>
      </section>

      <footer className="mx-auto max-w-[1440px] px-4 pb-10 pt-20 sm:px-8">
        <div className="text-[13vw] font-semibold leading-none tracking-[-0.05em] text-raised lg:text-[150px]">NarrateSim</div>
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4 text-[13px] text-muted">
          <span>A research sandbox for narrative attacks and defenses. Nothing here posts to a real platform.</span>
          <span className="flex gap-5">
            <Link to="/method" className="hover:text-ink">
              Method
            </Link>
            <a href={REPO_URL} className="hover:text-ink">
              Code
            </a>
            <a href="../" className="hover:text-ink">
              Project page
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}
