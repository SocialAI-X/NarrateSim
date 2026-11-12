import { useEffect, useMemo, useRef, useState } from "react";
import { forceCenter, forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import type { RunRecord } from "@/engine/types";

/* Stance colour: the negative pole, undecided grey, the positive pole. Eleven fixed steps. */
const NEG = [229, 86, 111];
const MID = [92, 92, 98];
const POS = [74, 138, 214];
export function stanceRGB(s: number): [number, number, number] {
  const t = Math.max(-1, Math.min(1, s / 5));
  const [a, b] = t < 0 ? [MID, NEG] : [MID, POS];
  const k = Math.pow(Math.abs(t), 0.8);
  return [0, 1, 2].map((i) => Math.round(a[i] + (b[i] - a[i]) * k)) as [number, number, number];
}
export const stanceColor = (s: number) => `rgb(${stanceRGB(s).join(",")})`;

interface Node extends SimulationNodeDatum {
  id: number;
}

const layoutCache = new Map<string, { x: number; y: number }[]>();

function layout(rec: RunRecord): { x: number; y: number }[] {
  const key = `${rec.scenario.seed}:${rec.graph.n}:${rec.graph.edges.length}:${rec.scenario.network.kind}:${rec.graph.edges.slice(0, 6).join(";")}`;
  const hit = layoutCache.get(key);
  if (hit) return hit;
  const n = rec.graph.n;
  const nodes: Node[] = Array.from({ length: n }, (_, i) => ({ id: i, x: Math.cos(i * 2.399) * Math.sqrt(i) * 12, y: Math.sin(i * 2.399) * Math.sqrt(i) * 12 }));
  const links = rec.graph.edges.map(([s, t]) => ({ source: s, target: t }));
  const k = Math.max(...rec.graph.communities) + 1;
  const sim = forceSimulation(nodes)
    .force("link", forceLink(links).distance(18).strength(0.35))
    .force("charge", forceManyBody().strength(-38).distanceMax(260))
    .force("collide", forceCollide(5))
    .force("center", forceCenter(0, 0))
    .stop();
  if (k > 1) {
    const cx = (c: number) => Math.cos((c / k) * Math.PI * 2) * 150;
    const cy = (c: number) => Math.sin((c / k) * Math.PI * 2) * 150;
    sim.force("cx", forceX<Node>((d) => cx(rec.graph.communities[d.id])).strength(0.08));
    sim.force("cy", forceY<Node>((d) => cy(rec.graph.communities[d.id])).strength(0.08));
  } else {
    sim.force("x", forceX(0).strength(0.04)).force("y", forceY(0).strength(0.04));
  }
  for (let i = 0; i < 320; i++) sim.tick();
  const out = nodes.map((d) => ({ x: d.x ?? 0, y: d.y ?? 0 }));
  layoutCache.set(key, out);
  return out;
}

export function NetworkCanvas({
  run,
  round,
  selected,
  onSelect,
  showPulses = true,
  className,
}: {
  run: RunRecord;
  round: number;
  selected: number | null;
  onSelect?: (id: number | null) => void;
  showPulses?: boolean;
  className?: string;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const pos = useMemo(() => layout(run), [run.graph]);
  const adj = useMemo(() => {
    const a: number[][] = Array.from({ length: run.graph.n }, () => []);
    for (const [x, y] of run.graph.edges) a[x].push(y), a[y].push(x);
    return a;
  }, [run.graph]);
  const [hover, setHover] = useState<{ id: number; x: number; y: number } | null>(null);
  const view = useRef({ k: 1, x: 0, y: 0 });
  const colors = useRef<number[][]>([]);
  const anim = useRef({ t0: performance.now(), from: [] as number[][], to: [] as number[][] });
  const frameRef = useRef(run.frames[Math.min(round, run.frames.length - 1)]);
  const attackers = useMemo(() => new Set(run.agents.filter((a) => a.attacker).map((a) => a.id)), [run]);
  const reduced = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Fit the layout into the box.
  const fit = () => {
    const el = wrap.current;
    if (!el) return;
    if (!el.clientWidth || !el.clientHeight) return;
    // Fit the central 98% of nodes so a few stragglers do not shrink the whole picture.
    const q = (v: number[], p: number) => v.slice().sort((a, b) => a - b)[Math.floor(p * (v.length - 1))];
    const xs = pos.map((p) => p.x);
    const ys = pos.map((p) => p.y);
    const [x0, x1, y0, y1] = [q(xs, 0.01), q(xs, 0.99), q(ys, 0.01), q(ys, 0.99)];
    const k = Math.min(el.clientWidth / (x1 - x0 + 40), el.clientHeight / (y1 - y0 + 40));
    view.current = { k, x: el.clientWidth / 2 - ((x0 + x1) / 2) * k, y: el.clientHeight / 2 - ((y0 + y1) / 2) * k };
  };
  useEffect(fit, [pos]);

  // New round: start a colour transition and new pulses.
  useEffect(() => {
    const f = run.frames[Math.min(round, run.frames.length - 1)];
    frameRef.current = f;
    if (!f) return;
    const to = f.stances.map(stanceRGB);
    anim.current = { t0: performance.now(), from: colors.current.length === to.length ? colors.current.map((c) => c.slice()) : to, to };
  }, [run, round]);

  useEffect(() => {
    const el = wrap.current;
    const cv = canvas.current;
    if (!el || !cv) return;
    const ctx = cv.getContext("2d")!;
    let raf = 0;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const resize = () => {
      cv.width = el.clientWidth * dpr;
      cv.height = el.clientHeight * dpr;
      cv.style.width = `${el.clientWidth}px`;
      cv.style.height = `${el.clientHeight}px`;
    };
    resize();
    const ro = new ResizeObserver(() => {
      resize();
      fit();
      paint(performance.now());
    });
    ro.observe(el);

    const draw = (now: number) => {
      paint(now);
      raf = requestAnimationFrame(draw);
    };
    const paint = (now: number) => {
      const f = frameRef.current;
      const { k, x: ox, y: oy } = view.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
      if (!f) return;
      const P = (i: number) => [pos[i].x * k + ox, pos[i].y * k + oy];
      const a = anim.current;
      const tt = reduced ? 1 : Math.min(1, (now - a.t0) / 520);
      const ease = 1 - Math.pow(1 - tt, 3);
      colors.current = a.to.map((c, i) => (a.from[i] ? c.map((v, j) => a.from[i][j] + (v - a.from[i][j]) * ease) : c));

      const sel = selected;
      const neigh = sel !== null ? new Set(adj[sel]) : null;

      // edges
      ctx.lineWidth = 1;
      ctx.strokeStyle = sel !== null ? "rgba(255,255,255,0.035)" : "rgba(255,255,255,0.07)";
      ctx.beginPath();
      for (const [s, t] of run.graph.edges) {
        const [x1, y1] = P(s);
        const [x2, y2] = P(t);
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
      }
      ctx.stroke();
      if (sel !== null) {
        ctx.strokeStyle = "rgba(74,138,214,0.55)";
        ctx.beginPath();
        for (const t of adj[sel]) {
          const [x1, y1] = P(sel);
          const [x2, y2] = P(t);
          ctx.moveTo(x1, y1);
          ctx.lineTo(x2, y2);
        }
        ctx.stroke();
      }

      // influence edges of this round: who moved whom
      for (const e of f.influence) {
        const [x1, y1] = P(e.from);
        const [x2, y2] = P(e.to);
        ctx.strokeStyle = e.via_attack ? "rgba(217,164,65,0.75)" : "rgba(242,242,243,0.28)";
        ctx.lineWidth = e.via_attack ? 1.4 : 1;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }

      // pulses: each post travels from its author to the neighbours who will read it
      if (showPulses && !reduced) {
        const cycle = ((now - a.t0) % 1800) / 1800;
        for (const p of f.posts) {
          if (p.removed) continue;
          const [x1, y1] = P(p.author);
          const targets = p.reply_to !== null ? [p.reply_to] : adj[p.author];
          ctx.fillStyle = p.manipulative ? "rgba(217,164,65,0.95)" : "rgba(242,242,243,0.5)";
          const r = p.manipulative ? 2 : 1.3;
          for (const t of targets) {
            const [x2, y2] = P(t);
            const u = cycle;
            ctx.beginPath();
            ctx.arc(x1 + (x2 - x1) * u, y1 + (y2 - y1) * u, r, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      // nodes
      const scale = Math.max(0.7, Math.min(1.6, k));
      const speaking = new Set(f.posts.map((p) => p.author));
      for (let i = 0; i < run.graph.n; i++) {
        const [x, y] = P(i);
        const deg = adj[i].length;
        const r = (2.2 + Math.sqrt(deg) * 0.9) * scale;
        const dim = neigh && i !== sel && !neigh.has(i);
        const c = colors.current[i] ?? MID;
        ctx.globalAlpha = dim ? 0.25 : 1;
        if (attackers.has(i) && !run.scenario.adversary.enabled) {
          // dormant operation account in a twin without the operation
          ctx.strokeStyle = "#5a5a60";
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.stroke();
        } else if (attackers.has(i)) {
          ctx.fillStyle = "#2a2416";
          ctx.beginPath();
          ctx.arc(x, y, r + 1, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#d9a441";
          ctx.lineWidth = 1.6;
          ctx.stroke();
        } else {
          ctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();
          if (speaking.has(i)) {
            ctx.strokeStyle = "rgba(255,255,255,0.65)";
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
        ctx.globalAlpha = 1;
        if (i === sel) {
          ctx.strokeStyle = "#4a8ad6";
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(x, y, r + 4, 0, Math.PI * 2);
          ctx.stroke();
        }
      }
      // suspended accounts get a cross
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.2;
      const lastSusp = new Set<number>();
      for (const fr of run.frames.slice(0, round + 1)) for (const ev of fr.events) if (ev.kind === "suspension" && ev.agent !== undefined) lastSusp.add(ev.agent);
      for (const i of lastSusp) {
        const [x, y] = P(i);
        ctx.beginPath();
        ctx.moveTo(x - 3, y - 3);
        ctx.lineTo(x + 3, y + 3);
        ctx.moveTo(x + 3, y - 3);
        ctx.lineTo(x - 3, y + 3);
        ctx.stroke();
      }
    };
    paint(performance.now());
    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [pos, adj, run, selected, showPulses, attackers, round]);

  const pick = (ev: React.MouseEvent) => {
    const rect = canvas.current!.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    const { k, x, y } = view.current;
    let best = -1;
    let bd = 14 * 14;
    pos.forEach((p, i) => {
      const dx = p.x * k + x - mx;
      const dy = p.y * k + y - my;
      const d = dx * dx + dy * dy;
      if (d < bd) (bd = d), (best = i);
    });
    return { id: best, x: mx, y: my };
  };

  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const f = run.frames[Math.min(round, run.frames.length - 1)];
  const hoverAgent = hover && hover.id >= 0 ? run.agents[hover.id] : null;

  return (
    <div ref={wrap} className={className ?? "relative h-full w-full"}>
      <canvas
        ref={canvas}
        role="img"
        aria-label={`Network of ${run.graph.n} agents at round ${round}. Colour shows stance.`}
        className="block cursor-crosshair"
        onMouseDown={(e) => (drag.current = { x: e.clientX, y: e.clientY, moved: false })}
        onMouseMove={(e) => {
          if (drag.current) {
            const dx = e.clientX - drag.current.x;
            const dy = e.clientY - drag.current.y;
            if (Math.abs(dx) + Math.abs(dy) > 2) drag.current.moved = true;
            view.current.x += dx;
            view.current.y += dy;
            drag.current.x = e.clientX;
            drag.current.y = e.clientY;
            setHover(null);
            return;
          }
          const h = pick(e);
          setHover(h.id >= 0 ? h : null);
        }}
        onMouseUp={(e) => {
          if (drag.current && !drag.current.moved) {
            const h = pick(e);
            onSelect?.(h.id >= 0 ? h.id : null);
          }
          drag.current = null;
        }}
        onMouseLeave={() => {
          drag.current = null;
          setHover(null);
        }}
        onWheel={(e) => {
          const rect = canvas.current!.getBoundingClientRect();
          const mx = e.clientX - rect.left;
          const my = e.clientY - rect.top;
          const v = view.current;
          const z = Math.exp(-e.deltaY * 0.0012);
          v.x = mx - (mx - v.x) * z;
          v.y = my - (my - v.y) * z;
          v.k *= z;
        }}
        onDoubleClick={fit}
      />
      {hoverAgent && f && (
        <div className="pointer-events-none absolute z-10 rounded-md bg-raised px-2.5 py-1.5 text-[12px] shadow-[0_12px_28px_rgba(0,0,0,.4)]" style={{ left: hover!.x + 12, top: hover!.y + 12 }}>
          <div className="font-medium text-ink">
            {hoverAgent.name}
            {hoverAgent.attacker && <span className="ml-1.5 text-warning">operation account</span>}
          </div>
          {!hoverAgent.attacker && (
            <div className="num text-muted">
              stance {f.stances[hoverAgent.id] > 0 ? "+" : ""}
              {f.stances[hoverAgent.id].toFixed(2)} · {hoverAgent.degree} ties
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function StanceLegend({ neg, pos }: { neg: string; pos: string }) {
  const steps = [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5];
  return (
    <div className="flex items-center gap-2 text-[11px] text-muted">
      <span className="max-w-32 truncate text-right">{neg}</span>
      <div className="flex">
        {steps.map((s) => (
          <span key={s} className="h-2 w-3" style={{ background: stanceColor(s) }} />
        ))}
      </div>
      <span className="max-w-32 truncate">{pos}</span>
      <span className="ml-2 inline-flex items-center gap-1">
        <span className="inline-block h-2.5 w-2.5 rounded-full border-[1.5px] border-warning bg-[#2a2416]" /> operation
      </span>
      <span className="inline-flex items-center gap-1">
        <span className="inline-block h-px w-3 bg-warning" /> moved by operation
      </span>
    </div>
  );
}
