import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Play, Square } from "lucide-react";
import { AXES, METRICS, type MetricId, type SweepCell, type SweepSpec } from "@/engine/sweep";
import { download, useLab } from "@/store";
import { EChart, heatmapOption, lineOption, SERIES } from "@/components/charts";
import { Button, Field, fmt, Select, Slider } from "@/components/ui";

export default function Sweeps() {
  const { scenario, loadScenario } = useLab();
  const nav = useNavigate();
  const [x, setX] = useState("strategy");
  const [y, setY] = useState<string>("population");
  const [metric, setMetric] = useState<MetricId>("attack_effect");
  const [seeds, setSeeds] = useState(4);
  const [n, setN] = useState(Math.min(scenario.society.n_agents, 100));
  const [cells, setCells] = useState<SweepCell[]>([]);
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [took, setTook] = useState<number | null>(null);
  const worker = useRef<Worker | null>(null);
  const ax = AXES.find((a) => a.id === x)!;
  const ay = y === "none" ? null : AXES.find((a) => a.id === y)!;
  const met = METRICS.find((m) => m.id === metric)!;
  const running = progress !== null && progress.done < progress.total;

  const start = () => {
    worker.current?.terminate();
    const w = new Worker(new URL("../engine/sweep.worker.ts", import.meta.url), { type: "module" });
    worker.current = w;
    const base = structuredClone(scenario);
    base.society.n_agents = n;
    base.engine.mind = "heuristic";
    const spec: SweepSpec = { base, x, y: y === "none" ? null : y, metric, seeds };
    setCells([]);
    setTook(null);
    const t0 = performance.now();
    setProgress({ done: 0, total: ax.values.length * (ay?.values.length ?? 1) * seeds });
    w.onmessage = (e) => {
      if (e.data.type === "cell") {
        setCells((c) => [...c, e.data.cell]);
        setProgress({ done: e.data.done, total: e.data.total });
      } else if (e.data.type === "done") {
        setTook(performance.now() - t0);
        w.terminate();
      }
    };
    w.postMessage(spec);
  };
  const stop = () => {
    worker.current?.terminate();
    setProgress(null);
  };

  const fmtV = (v: number) => (met.pct ? fmt.pct(v) : fmt.num(v, 2));
  const option = useMemo(() => {
    if (!cells.length) return null;
    if (ay) {
      const vals = cells.map((c) => c.mean).filter((v): v is number => v !== null);
      const lim = Math.max(0.01, ...vals.map(Math.abs));
      return heatmapOption(
        ax.values.map((v) => v.label),
        ay.values.map((v) => v.label),
        cells.map((c) => ({ x: c.x, y: c.y, v: c.mean, ci: c.ci })),
        { min: met.diverging ? -lim : Math.min(0, ...vals), max: lim, diverging: met.diverging, format: fmtV },
      );
    }
    return null;
  }, [cells, ax, ay, met]);

  const csv = () => {
    const rows = [["x_axis", "x", "y_axis", "y", "metric", "mean", "ci95", "n", "values"].join(",")];
    for (const c of cells) rows.push([ax.label, ax.values[c.x].key, ay?.label ?? "", ay?.values[c.y].key ?? "", metric, c.mean ?? "", c.ci, c.n, `"${c.values.map((v) => v.toFixed(4)).join(" ")}"`].join(","));
    download(`sweep_${x}_${y}_${metric}.csv`, rows.join("\n"), "text/csv");
  };

  const openCell = (p: any) => {
    const c = cells[p.dataIndex];
    if (!c) return;
    const s = structuredClone(scenario);
    s.society.n_agents = n;
    s.adversary.enabled = true;
    ay?.values[c.y].apply(s);
    ax.values[c.x].apply(s);
    s.name = `${ax.values[c.x].label} × ${ay ? ay.values[c.y].label : ""}`.trim();
    loadScenario(s);
    nav("/lab");
  };

  return (
    <div className="mx-auto grid max-w-[1400px] gap-6 px-5 py-6 lg:px-8">
      <header>
        <h1 className="text-[24px] font-semibold">Sweeps</h1>
        <p className="mt-1 max-w-3xl text-[14px] text-muted">
          Cross two factors of the current scenario and replicate every cell over several seeds. Each replicate runs the baseline, attacked and defended twins, so every number is an effect, not a level. Runs use the heuristic mind in a background worker.
        </p>
      </header>

      <div className="card grid gap-4 p-4 md:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.4fr)] md:items-end">
        <Field label="Columns">
          <Select ariaLabel="Columns" value={x} onChange={setX} options={AXES.map((a) => ({ value: a.id, label: a.label }))} />
        </Field>
        <Field label="Rows">
          <Select ariaLabel="Rows" value={y} onChange={setY} options={[{ value: "none", label: "None (one row)" }, ...AXES.filter((a) => a.id !== x).map((a) => ({ value: a.id, label: a.label }))]} />
        </Field>
        <Field label="Measure">
          <Select ariaLabel="Measure" value={metric} onChange={setMetric} options={METRICS.map((m) => ({ value: m.id, label: m.label }))} />
        </Field>
        <div className="grid grid-cols-[1fr_1fr_auto] items-end gap-4">
          <Slider label="Seeds per cell" value={seeds} min={1} max={12} onChange={setSeeds} />
          <Slider label="Agents" value={n} min={40} max={300} step={10} onChange={setN} />
          {running ? (
            <Button variant="danger" onClick={stop}>
              <Square className="h-3.5 w-3.5" /> Stop
            </Button>
          ) : (
            <Button variant="primary" onClick={start}>
              <Play className="h-3.5 w-3.5" /> Run sweep
            </Button>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 text-[12px] text-muted">
        <span className="num">
          {progress ? `${progress.done} / ${progress.total} replicates` : `${ax.values.length * (ay?.values.length ?? 1)} cells × ${seeds} seeds = ${ax.values.length * (ay?.values.length ?? 1) * seeds * 3} runs`}
          {took !== null && ` · ${(took / 1000).toFixed(1)} s`}
        </span>
        {progress && (
          <div className="mx-4 h-[2px] flex-1 bg-control">
            <div className="h-full bg-accent transition-[width]" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
          </div>
        )}
        <Button size="sm" disabled={!cells.length} onClick={csv}>
          <Download className="h-3.5 w-3.5" /> CSV
        </Button>
      </div>

      <div className="card p-4">
        <h2 className="text-[14px] font-semibold">
          {met.label}
          {ay ? ` by ${ax.label.toLowerCase()} and ${ay.label.toLowerCase()}` : ` by ${ax.label.toLowerCase()}`}
        </h2>
        <p className="mb-3 text-[12px] text-muted">Mean over seeds; hover a cell for its 95% interval. Click a cell to open it in the Lab.</p>
        {!cells.length ? (
          <div className="flex h-[360px] items-center justify-center rounded border border-dashed border-control text-[13px] text-muted">{running ? <span className="shimmer">Running the first cell…</span> : "Choose two factors and run the sweep."}</div>
        ) : ay && option ? (
          <EChart height={Math.max(280, 54 * ay.values.length + 80)} option={option} onClick={openCell} />
        ) : (
          <EChart
            height={300}
            option={{
              ...lineOption([{ name: met.label, color: SERIES.ink, data: ax.values.map((_, i) => cells.find((c) => c.x === i)?.mean ?? null) }], { yFormat: fmtV }),
              xAxis: { type: "category", data: ax.values.map((v) => v.label), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#8a8c92", fontSize: 11 } },
            }}
          />
        )}
      </div>

      {cells.length > 0 && (
        <div className="card overflow-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-left text-[12px] text-muted">
                <th className="px-4 py-2 font-normal">{ax.label}</th>
                {ay && <th className="px-4 py-2 font-normal">{ay.label}</th>}
                <th className="px-4 py-2 text-right font-normal">Mean</th>
                <th className="px-4 py-2 text-right font-normal">± 95%</th>
                <th className="px-4 py-2 text-right font-normal">Seeds</th>
              </tr>
            </thead>
            <tbody>
              {cells
                .slice()
                .sort((a, b) => (b.mean ?? -1e9) - (a.mean ?? -1e9))
                .map((c) => (
                  <tr key={`${c.x}-${c.y}`} className="border-t border-rule">
                    <td className="px-4 py-2 text-soft">{ax.values[c.x].label}</td>
                    {ay && <td className="px-4 py-2 text-soft">{ay.values[c.y].label}</td>}
                    <td className="num px-4 py-2 text-right">{c.mean === null ? "—" : fmtV(c.mean)}</td>
                    <td className="num px-4 py-2 text-right text-muted">{fmtV(c.ci)}</td>
                    <td className="num px-4 py-2 text-right text-muted">{c.n}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
