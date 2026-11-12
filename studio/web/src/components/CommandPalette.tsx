import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { PRESETS } from "@/engine/presets";
import { useLab } from "@/store";

/** ⌘K / Ctrl+K: jump anywhere, load a preset, run. */
export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const { loadScenario, run } = useLab();
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  const go = (f: () => void) => {
    f();
    setOpen(false);
  };
  const item = "flex cursor-default items-center justify-between rounded px-3 py-2 text-[13px] text-soft data-[selected=true]:bg-hover data-[selected=true]:text-ink";
  return (
    <Command.Dialog open={open} onOpenChange={setOpen} label="Command menu" className="fixed left-1/2 top-[18vh] z-50 w-[min(560px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-lg border border-border bg-raised shadow-[0_12px_28px_rgba(0,0,0,.45)]">
      <Command.Input placeholder="Jump to a page, load a scenario…" className="h-12 w-full border-b border-border bg-transparent px-4 text-[14px] text-ink placeholder:text-muted focus:outline-none" />
      <Command.List className="max-h-[50vh] overflow-auto p-1.5">
        <Command.Empty className="px-3 py-6 text-[13px] text-muted">Nothing matches.</Command.Empty>
        <Command.Group heading="Go to" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:text-muted">
          {[
            ["Lab", "/lab"],
            ["Counterfactuals", "/compare"],
            ["Sweeps", "/sweeps"],
            ["Library", "/library"],
            ["Method", "/method"],
            ["Settings", "/settings"],
            ["Home", "/"],
          ].map(([l, to]) => (
            <Command.Item key={to} className={item} onSelect={() => go(() => nav(to))}>
              {l}
            </Command.Item>
          ))}
        </Command.Group>
        <Command.Group heading="Run a scenario" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:text-muted">
          {PRESETS.map((p) => (
            <Command.Item
              key={p.id}
              value={p.title}
              className={item}
              onSelect={() =>
                go(() => {
                  loadScenario(p.scenario);
                  nav("/lab");
                  setTimeout(() => run(), 30);
                })
              }
            >
              <span>{p.title}</span>
              <span className="text-[11px] text-muted">run</span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
