import { useMemo } from "react";
import type { RunRecord } from "@/engine/types";
import { EChart } from "./charts";
import { Avatar } from "./Feed";

/**
 * Where the operation's influence went: who it moved directly (hop 1), who those people moved in
 * turn (hop 2+), and which honest accounts carried it furthest.
 */
export function CascadePanel({ run, round, onAgent }: { run: RunRecord; round: number; onAgent: (id: number) => void }) {
  const data = useMemo(() => {
    const frames = run.frames.slice(1, round + 1);
    const edges = frames.flatMap((f) => f.influence).filter((e) => e.via_attack && e.delta * run.scenario.adversary.target > 0);
    const hops = [1, 2, 3, 4].map((g) => new Set(edges.filter((e) => (g < 4 ? e.generation === g : e.generation >= 4)).map((e) => e.to)).size);
    const carriers = new Map<number, Set<number>>();
    for (const e of edges)
      if (!run.agents[e.from].attacker) {
        const s = carriers.get(e.from) ?? new Set();
        s.add(e.to);
        carriers.set(e.from, s);
      }
    const top = [...carriers.entries()].sort((a, b) => b[1].size - a[1].size).slice(0, 8);
    const perAttacker = run.agents
      .filter((a) => a.attacker)
      .map((a) => ({ a, direct: new Set(edges.filter((e) => e.from === a.id).map((e) => e.to)).size }))
      .sort((x, y) => y.direct - x.direct);
    const series = run.frames.slice(1).map((f) => [f.influence.filter((e) => e.via_attack && e.generation === 1).length, f.influence.filter((e) => e.via_attack && e.generation >= 2).length]);
    return { hops, top, perAttacker, series };
  }, [run, round]);

  if (!run.scenario.adversary.enabled) return <p className="px-4 py-6 text-[13px] text-muted">This twin has no operation, so there is no cascade to trace. Switch to the attacked or defended twin.</p>;
  const total = data.hops.reduce((a, b) => a + b, 0);
  return (
    <div className="grid gap-5 px-4 py-4">
      <div>
        <h3 className="text-[13px] font-semibold">Reach by hop, up to round {round}</h3>
        <p className="mt-0.5 text-[12px] text-muted">People moved toward the target, by how many hops they were from an operation account.</p>
        <div className="mt-3 grid grid-cols-4 gap-px overflow-hidden rounded-md bg-border">
          {["Direct", "Hop 2", "Hop 3", "Hop 4+"].map((l, k) => (
            <div key={l} className="bg-surface px-3 py-2">
              <div className="text-[11px] text-muted">{l}</div>
              <div className="num text-[18px]">{data.hops[k]}</div>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[12px] text-soft">{total ? `${Math.round(((total - data.hops[0]) / total) * 100)}% of the movement happened second-hand, through honest people.` : "No one has been moved by the operation yet."}</p>
      </div>
      <div>
        <h3 className="mb-1 text-[12px] text-muted">Moves per round: direct (amber) and second-hand (white)</h3>
        <EChart
          height={120}
          option={{
            grid: { left: 28, right: 4, top: 6, bottom: 20 },
            xAxis: { type: "category", data: data.series.map((_, i) => i + 1), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#8a8c92", fontSize: 10 } },
            yAxis: { type: "value", splitNumber: 2, axisLabel: { color: "#8a8c92", fontSize: 10 }, splitLine: { lineStyle: { color: "#232327", type: "dashed" } } },
            tooltip: { trigger: "axis", backgroundColor: "#212023", borderWidth: 0, textStyle: { color: "#fff", fontSize: 12 } },
            series: [
              { name: "direct", type: "bar", stack: "a", data: data.series.map((s) => s[0]), itemStyle: { color: "#d9a441" } },
              { name: "second-hand", type: "bar", stack: "a", data: data.series.map((s) => s[1]), itemStyle: { color: "#c9c9cd" } },
            ],
          }}
        />
      </div>
      <div>
        <h3 className="mb-2 text-[12px] text-muted">Honest carriers: people who passed the narrative on</h3>
        {data.top.length === 0 ? (
          <p className="text-[12px] text-muted">None yet.</p>
        ) : (
          <ul className="grid gap-1.5">
            {data.top.map(([id, set]) => (
              <li key={id}>
                <button onClick={() => onAgent(id)} className="flex w-full items-center gap-2 text-left text-[12px] hover:text-ink">
                  <Avatar id={id} name={run.agents[id].name} size={22} />
                  <span className="truncate text-soft">{run.agents[id].name}</span>
                  <span className="num ml-auto text-soft">{set.size} moved</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-[12px] text-muted">Operation accounts</h3>
        <ul className="grid gap-1.5">
          {data.perAttacker.map(({ a, direct }) => (
            <li key={a.id}>
              <button onClick={() => onAgent(a.id)} className="flex w-full items-center gap-2 text-left text-[12px] hover:text-ink">
                <Avatar id={a.id} name={a.name} attacker size={22} />
                <span className="truncate text-soft">{a.name}</span>
                <span className="num text-muted">{a.degree} ties</span>
                <span className="num ml-auto text-soft">{direct} moved</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
