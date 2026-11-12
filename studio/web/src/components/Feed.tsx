import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronRight, ShieldAlert, MessageSquareWarning, EyeOff } from "lucide-react";
import type { Post, RunRecord } from "@/engine/types";
import { stanceColor } from "./NetworkCanvas";
import { cn, Pill, Segmented } from "./ui";

export function hueOf(id: number) {
  return (id * 137.508) % 360;
}

export function Avatar({ id, name, attacker, size = 28 }: { id: number; name: string; attacker?: boolean; size?: number }) {
  const h = hueOf(id);
  const initials = name
    .split(" ")
    .map((x) => x[0])
    .join("")
    .slice(0, 2);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 items-center justify-center rounded-full text-[11px] font-semibold"
      style={{ width: size, height: size, background: attacker ? "#2a2416" : `hsl(${h} 22% 20%)`, color: attacker ? "#d9a441" : `hsl(${h} 45% 78%)`, boxShadow: attacker ? "inset 0 0 0 1.5px #d9a441" : undefined }}
    >
      {initials}
    </span>
  );
}

export const FRAMING_LABEL: Record<string, string> = {
  reasoned: "argument",
  personal: "experience",
  pseudo_rational: "pseudo-rational",
  victim_narrative: "victim narrative",
  fear_appeal: "fear appeal",
  conspiracy: "conspiracy",
  fake_authority: "fake authority",
  bandwagon: "bandwagon",
};

export function StanceChip({ v }: { v: number }) {
  return (
    <span className="num inline-flex items-center gap-1 text-[11px] text-soft">
      <span className="inline-block h-2 w-2 rounded-full" style={{ background: stanceColor(v) }} />
      {v > 0 ? "+" : v < 0 ? "−" : ""}
      {Math.abs(v).toFixed(1)}
    </span>
  );
}

function PostCard({ p, run, onAgent, reveal }: { p: Post; run: RunRecord; onAgent: (id: number) => void; reveal: boolean }) {
  const [open, setOpen] = useState(false);
  const a = run.agents[p.author];
  const to = p.reply_to !== null ? run.agents[p.reply_to] : null;
  return (
    <motion.article layout initial={{ opacity: 0, y: 12 }} animate={{ opacity: p.removed ? 0.45 : 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.28, ease: [0.2, 0.7, 0.2, 1] }} className="border-b border-rule px-4 py-3">
      <div className="flex gap-2.5">
        <button onClick={() => onAgent(a.id)} aria-label={`Inspect ${a.name}`}>
          <Avatar id={a.id} name={a.name} attacker={reveal && a.attacker} />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1.5 text-[12px]">
            <button className="truncate font-semibold text-ink hover:underline" onClick={() => onAgent(a.id)}>
              {a.name}
            </button>
            <span className="truncate text-muted">@{a.handle}</span>
            <span className="ml-auto shrink-0">
              <StanceChip v={p.stance} />
            </span>
          </div>
          {to && (
            <div className="mt-0.5 text-[11px] text-muted">
              replying to{" "}
              <button className="hover:text-soft" onClick={() => onAgent(to.id)}>
                {to.name}
              </button>
            </div>
          )}
          {p.label && (
            <div className="mt-1.5 flex items-center gap-1.5 rounded bg-raised px-2 py-1 text-[11px] text-soft">
              {p.label === "guardian" ? <ShieldAlert className="h-3.5 w-3.5 text-warning" /> : <MessageSquareWarning className="h-3.5 w-3.5 text-accent" />}
              {p.label === "guardian" ? `Labelled by Guardian (score ${p.guardian_score?.toFixed(2)})` : "Community note: readers added context"}
              {p.downranked && <span className="text-muted">· downranked</span>}
              {p.removed && (
                <span className="inline-flex items-center gap-1 text-muted">
                  <EyeOff className="h-3 w-3" /> removed
                </span>
              )}
            </div>
          )}
          <p className={cn("mt-1.5 text-[13px] leading-[1.5] text-soft", p.removed && "line-through decoration-muted")}>{p.text}</p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {reveal && p.manipulative && <Pill tone="warning">operation</Pill>}
            <Pill>{FRAMING_LABEL[p.framing]}</Pill>
            <span className="num text-[11px] text-muted">
              intensity {p.intensity.toFixed(2)} · seen {p.seen} · {p.agree} agree
            </span>
          </div>
          {p.bdi && (
            <div className="mt-2">
              <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-[11px] text-muted hover:text-soft" aria-expanded={open}>
                <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
                Reasoning
              </button>
              <AnimatePresence initial={false}>
                {open && (
                  <motion.dl initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="mt-1.5 grid grid-cols-[64px_1fr] gap-x-2 gap-y-1 overflow-hidden border-l border-control pl-3 text-[12px]">
                    <dt className="text-muted">Belief</dt>
                    <dd className="text-soft">{p.bdi.belief}</dd>
                    <dt className="text-muted">Desire</dt>
                    <dd className="text-soft">{p.bdi.desire}</dd>
                    <dt className="text-muted">Intention</dt>
                    <dd className="text-soft">{p.bdi.intention}</dd>
                  </motion.dl>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </motion.article>
  );
}

export function Feed({ run, round, onAgent, streaming }: { run: RunRecord; round: number; onAgent: (id: number) => void; streaming?: boolean }) {
  const [filter, setFilter] = useState<"all" | "operation" | "labelled" | "replies">("all");
  const [reveal, setReveal] = useState(true);
  const f = run.frames[Math.min(round, run.frames.length - 1)];
  const posts = useMemo(() => {
    const ps = (f?.posts ?? []).slice();
    const keep = ps.filter((p) => (filter === "operation" ? p.manipulative : filter === "labelled" ? p.label !== null : filter === "replies" ? p.reply_to !== null : true));
    return keep.sort((a, b) => Number(b.manipulative) - Number(a.manipulative) || b.seen - a.seen || a.id - b.id);
  }, [f, filter]);
  return (
    <div className="flex h-full flex-col">
      <div className="px-4 pt-3">
        <Segmented
          size="sm"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: `All ${f?.posts.length ?? 0}` },
            { value: "operation", label: "Operation" },
            { value: "labelled", label: "Labelled" },
            { value: "replies", label: "Replies" },
          ]}
        />
        <label className="mt-2 flex items-center gap-2 text-[11px] text-muted">
          <input type="checkbox" checked={reveal} onChange={(e) => setReveal(e.target.checked)} className="accent-[#4a8ad6]" />
          Reveal ground truth (who is in the operation)
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {round === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted">Round 0 is the society before anyone posts. Step forward to read the first round.</p>
        ) : posts.length === 0 ? (
          <p className="px-4 py-6 text-[13px] text-muted">{streaming ? <span className="shimmer">Agents are thinking…</span> : "Nobody posted under this filter in this round."}</p>
        ) : (
          <AnimatePresence mode="popLayout">
            {posts.map((p) => (
              <PostCard key={p.id} p={p} run={run} onAgent={onAgent} reveal={reveal} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
