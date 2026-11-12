import { useMemo } from "react";
import { VALUE_LABELS } from "@/engine/topics";
import type { RunRecord } from "@/engine/types";
import type { Variant } from "@/store";
import { EChart, lineOption, SERIES } from "./charts";
import { Avatar, FRAMING_LABEL, StanceChip } from "./Feed";
import { fmt, Pill } from "./ui";

export function AgentInspector({ runs, view, id, round, onAgent }: { runs: Partial<Record<Variant, RunRecord>>; view: Variant; id: number | null; round: number; onAgent: (id: number) => void }) {
  const run = runs[view];
  const data = useMemo(() => {
    if (!run || id === null) return null;
    const a = run.agents[id];
    const posts = run.frames.flatMap((f) => f.posts.filter((p) => p.author === id));
    const movedBy = run.frames.flatMap((f) => f.influence.filter((e) => e.to === id));
    const moved = run.frames.flatMap((f) => f.influence.filter((e) => e.from === id));
    const neighbours = new Set<number>();
    for (const [x, y] of run.graph.edges) {
      if (x === id) neighbours.add(y);
      if (y === id) neighbours.add(x);
    }
    return { a, posts, movedBy, moved, neighbours: [...neighbours] };
  }, [run, id]);

  if (!run) return null;
  if (!data) return <p className="px-4 py-6 text-[13px] leading-relaxed text-muted">Click an agent in the network or a name in the feed to see their values, their stance in each counterfactual twin, and who moved them.</p>;
  const { a, posts, movedBy, moved, neighbours } = data;
  const f = run.frames[Math.min(round, run.frames.length - 1)];
  const lines = (Object.keys(runs) as Variant[]).map((v) => ({ name: v, color: SERIES[v], data: runs[v]!.frames.map((fr) => fr.stances[a.id]) }));
  const exposedAt = run.frames.findIndex((fr) => fr.posts.some((p) => p.manipulative && neighbours.includes(p.author)));

  return (
    <div className="grid gap-5 px-4 py-4">
      <div className="flex items-center gap-3">
        <Avatar id={a.id} name={a.name} attacker={a.attacker} size={40} />
        <div className="min-w-0">
          <div className="text-[16px] font-semibold">{a.name}</div>
          <div className="text-[12px] text-muted">
            @{a.handle} · {a.degree} ties{run.scenario.network.kind === "communities" ? ` · community ${a.community + 1}` : ""}
          </div>
        </div>
        <div className="ml-auto">{a.attacker ? <Pill tone="warning">operation account</Pill> : <StanceChip v={f.stances[a.id]} />}</div>
      </div>

      {!a.attacker && (
        <div>
          <h3 className="mb-1 text-[12px] text-muted">Stance in each twin</h3>
          <EChart height={150} option={lineOption(lines, { yMin: -5, yMax: 5, cursor: round, legend: true })} />
          <p className="mt-1 text-[12px] text-soft">
            Started at <span className="num">{fmt.signed(run.frames[0].stances[a.id], 1)}</span>, now <span className="num">{fmt.signed(f.stances[a.id], 1)}</span>.{" "}
            {exposedAt > 0 ? `First saw an operation post in round ${exposedAt + 1}.` : "Never followed an operation account directly."}
          </p>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-[12px] text-muted">Values</h3>
        <div className="grid gap-1.5">
          {VALUE_LABELS.map((l, k) => (
            <div key={l} className="grid grid-cols-[118px_1fr_32px] items-center gap-2 text-[12px]">
              <span className="text-soft">{l}</span>
              <span className="h-1.5 rounded-full bg-raised">
                <span className="block h-full rounded-full bg-soft" style={{ width: `${(a.values[k] / 10) * 100}%` }} />
              </span>
              <span className="num text-right text-muted">{a.values[k].toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>

      {!a.attacker && movedBy.length > 0 && (
        <div>
          <h3 className="mb-2 text-[12px] text-muted">Who moved them</h3>
          <ul className="grid gap-1">
            {movedBy.slice(-6).reverse().map((e, k) => (
              <li key={k} className="flex items-center gap-2 text-[12px]">
                <span className="num w-8 text-muted">R{e.round}</span>
                <button className="truncate text-soft hover:text-ink" onClick={() => onAgent(e.from)}>
                  {run.agents[e.from].name}
                </button>
                {e.via_attack && <Pill tone="warning">{e.generation === 1 ? "direct" : `hop ${e.generation}`}</Pill>}
                <span className="num ml-auto text-soft">{fmt.signed(e.delta, 2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {moved.length > 0 && (
        <div>
          <h3 className="mb-2 text-[12px] text-muted">They moved {new Set(moved.map((e) => e.to)).size} people</h3>
          <div className="flex flex-wrap gap-1">
            {[...new Set(moved.map((e) => e.to))].slice(0, 24).map((t) => (
              <button key={t} onClick={() => onAgent(t)} aria-label={run.agents[t].name}>
                <Avatar id={t} name={run.agents[t].name} size={22} />
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-[12px] text-muted">Posts · {posts.length}</h3>
        <ul className="grid gap-2">
          {posts.slice(-5).reverse().map((p) => (
            <li key={p.id} className="rounded bg-raised/60 px-3 py-2 text-[12px] leading-relaxed text-soft">
              <div className="mb-1 flex items-center gap-2 text-[11px] text-muted">
                <span className="num">R{p.round}</span>
                <span>{FRAMING_LABEL[p.framing]}</span>
                {p.label && <span className="text-warning">labelled</span>}
              </div>
              {p.text}
            </li>
          ))}
          {posts.length === 0 && <li className="text-[12px] text-muted">Has not posted yet.</li>}
        </ul>
      </div>
    </div>
  );
}
