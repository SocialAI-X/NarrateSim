import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Download, FolderOpen, Server, Trash2, Upload } from "lucide-react";
import { triadSummary } from "@/engine/engine";
import { topicById } from "@/engine/topics";
import type { RunRecord } from "@/engine/types";
import { download, library, useLab, type Bundle, type Variant } from "@/store";
import { Button, fmt, Pill } from "@/components/ui";

function bundleFrom(data: any, name = "Imported run"): Bundle {
  if (data?.runs && data?.scenario) return { id: data.id ?? `b-${Date.now().toString(36)}`, name: data.name ?? data.scenario.name ?? name, created: data.created ?? new Date().toISOString(), scenario: data.scenario, runs: data.runs, forks: data.forks ?? [] };
  if (data?.meta && data?.frames) {
    const r = data as RunRecord;
    const v = (["baseline", "attacked", "defended"].includes(r.meta.variant) ? r.meta.variant : "attacked") as Variant;
    return { id: `b-${Date.now().toString(36)}`, name: r.scenario.name ?? name, created: r.meta.created, scenario: r.scenario, runs: { [v]: r }, forks: [] };
  }
  if (Array.isArray(data?.variants)) {
    const runs: Partial<Record<Variant, RunRecord>> = {};
    for (const r of data.variants as RunRecord[]) runs[r.meta.variant as Variant] = r;
    return { id: data.id ?? `b-${Date.now().toString(36)}`, name: data.name ?? name, created: data.created ?? new Date().toISOString(), scenario: data.scenario ?? data.variants[0].scenario, runs, forks: [] };
  }
  throw new Error("Not a NarrateSim run file");
}

export interface ExampleEntry {
  file: string;
  name: string;
  description: string;
  mind: string;
  model?: string;
  agents: number;
  rounds: number;
}

export async function fetchExamples(): Promise<ExampleEntry[]> {
  try {
    const r = await fetch(`${import.meta.env.BASE_URL}examples/index.json`);
    return r.ok ? await r.json() : [];
  } catch {
    return [];
  }
}

export async function loadExample(file: string): Promise<Bundle> {
  const r = await fetch(`${import.meta.env.BASE_URL}examples/${file}`);
  return bundleFrom(await r.json(), file);
}

export default function LibraryPage() {
  const [items, setItems] = useState<Bundle[]>([]);
  const [examples, setExamples] = useState<ExampleEntry[]>([]);
  const [server, setServer] = useState<{ id: string; name: string; created: string; mind: string; model?: string; status: string }[] | null>(null);
  const { openBundle, llm } = useLab();
  const nav = useNavigate();
  const file = useRef<HTMLInputElement>(null);
  const refresh = () => library.list().then(setItems);
  useEffect(() => {
    refresh();
    fetchExamples().then(setExamples);
    fetch(`${llm.apiBase}/api/runs`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => setServer(j?.runs ?? null))
      .catch(() => setServer(null));
  }, [llm.apiBase]);

  const open = (b: Bundle) => {
    openBundle(b);
    nav("/lab");
  };
  const importFiles = async (files: FileList | null) => {
    for (const f of Array.from(files ?? [])) {
      try {
        const b = bundleFrom(JSON.parse(await f.text()), f.name);
        await library.put(b);
        toast.success(`Imported ${b.name}`);
      } catch (e) {
        toast.error(`${f.name}: ${(e as Error).message}`);
      }
    }
    refresh();
  };
  const openServer = async (id: string) => {
    try {
      const j = await (await fetch(`${llm.apiBase}/api/runs/${id}`)).json();
      open(bundleFrom(j));
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="mx-auto grid max-w-[1200px] gap-6 px-5 py-6 lg:px-8" onDragOver={(e) => e.preventDefault()} onDrop={(e) => (e.preventDefault(), importFiles(e.dataTransfer.files))}>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[24px] font-semibold">Library</h1>
          <p className="mt-1 max-w-2xl text-[14px] text-muted">Runs saved in this browser, runs from a NarrateSim server, and run files you drop here. Files written by the Python engine open the same way.</p>
        </div>
        <div className="flex gap-2">
          <input ref={file} type="file" accept=".json" multiple hidden onChange={(e) => importFiles(e.target.files)} />
          <Button onClick={() => file.current?.click()}>
            <Upload className="h-3.5 w-3.5" /> Import run files
          </Button>
        </div>
      </header>

      {examples.length > 0 && (
        <section className="card overflow-hidden">
          <h2 className="px-4 pt-4 text-[14px] font-semibold">Recorded LLM societies</h2>
          <p className="px-4 text-[12px] text-muted">Real runs of LLM agents, recorded with the Python engine and replayable here post by post, with every agent's reasoning.</p>
          <ul className="mt-2">
            {examples.map((e) => (
              <li key={e.file} className="flex flex-wrap items-center gap-3 border-t border-rule px-4 py-3 text-[13px]">
                <button
                  className="text-left font-medium hover:underline"
                  onClick={async () => {
                    try {
                      open(await loadExample(e.file));
                    } catch (err) {
                      toast.error((err as Error).message);
                    }
                  }}
                >
                  {e.name}
                </button>
                <Pill tone="accent">{e.model ?? e.mind}</Pill>
                <span className="text-[12px] text-muted">{e.description}</span>
                <span className="num ml-auto text-[12px] text-muted">
                  {e.agents} agents · {e.rounds} rounds
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card overflow-hidden">
        <h2 className="px-4 pt-4 text-[14px] font-semibold">In this browser</h2>
        {items.length === 0 ? (
          <div className="m-4 rounded border border-dashed border-control px-4 py-8 text-center text-[13px] text-muted">No saved runs. Save one from the Lab, or drop a .json run file anywhere on this page.</div>
        ) : (
          <table className="mt-2 w-full text-[13px]">
            <thead>
              <tr className="text-left text-[12px] text-muted">
                <th className="px-4 py-2 font-normal">Scenario</th>
                <th className="hidden px-4 py-2 font-normal md:table-cell">Topic</th>
                <th className="hidden px-4 py-2 font-normal md:table-cell">Mind</th>
                <th className="px-4 py-2 text-right font-normal">Attack effect</th>
                <th className="px-4 py-2 text-right font-normal">Protection</th>
                <th className="hidden px-4 py-2 text-right font-normal sm:table-cell">Saved</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {items.map((b) => {
                const s = b.runs.baseline && b.runs.attacked ? triadSummary(b.runs.baseline, b.runs.attacked, b.runs.defended) : null;
                return (
                  <tr key={b.id} className="border-t border-rule hover:bg-hover">
                    <td className="px-4 py-2.5">
                      <button className="text-left font-medium text-ink hover:underline" onClick={() => open(b)}>
                        {b.name}
                      </button>
                      <div className="text-[11px] text-muted">
                        {Object.keys(b.runs).join(" · ")}
                        {b.forks?.length ? ` · ${b.forks.length} forks` : ""}
                      </div>
                    </td>
                    <td className="hidden px-4 py-2.5 text-soft md:table-cell">{topicById(b.scenario.topic).title}</td>
                    <td className="hidden px-4 py-2.5 md:table-cell">
                      <Pill tone={b.scenario.engine.mind === "llm" ? "accent" : "neutral"}>{b.scenario.engine.mind}</Pill>
                    </td>
                    <td className="num px-4 py-2.5 text-right">{fmt.signed(s?.attack_effect)}</td>
                    <td className="num px-4 py-2.5 text-right">{fmt.pct(s?.protection ?? null)}</td>
                    <td className="num hidden px-4 py-2.5 text-right text-muted sm:table-cell">{new Date(b.created).toLocaleDateString()}</td>
                    <td className="px-4 py-2.5">
                      <div className="flex justify-end gap-1">
                        <Button size="iconSm" variant="ghost" aria-label="Open" onClick={() => open(b)}>
                          <FolderOpen className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="iconSm" variant="ghost" aria-label="Download" onClick={() => download(`${b.name.replace(/\W+/g, "_")}.narratesim.json`, b)}>
                          <Download className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="iconSm"
                          variant="ghost"
                          aria-label="Delete"
                          onClick={async () => {
                            await library.remove(b.id);
                            refresh();
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <section className="card overflow-hidden">
        <div className="flex items-center gap-2 px-4 pt-4">
          <Server className="h-4 w-4 text-muted" />
          <h2 className="text-[14px] font-semibold">On the NarrateSim server</h2>
          <span className="num ml-auto text-[12px] text-muted">{llm.apiBase || "same origin"}</span>
        </div>
        {server === null ? (
          <p className="px-4 py-5 text-[13px] text-muted">
            No server reachable. Start one with <code className="num text-soft">narratesim serve</code> to run long LLM experiments headless and browse them here.
          </p>
        ) : server.length === 0 ? (
          <p className="px-4 py-5 text-[13px] text-muted">The server has no runs yet.</p>
        ) : (
          <ul className="mt-2">
            {server.map((r) => (
              <li key={r.id} className="flex items-center gap-3 border-t border-rule px-4 py-2.5 text-[13px]">
                <button className="font-medium hover:underline" onClick={() => openServer(r.id)}>
                  {r.name}
                </button>
                <Pill tone={r.mind === "llm" ? "accent" : "neutral"}>{r.mind}</Pill>
                {r.model && <span className="text-[12px] text-muted">{r.model}</span>}
                <Pill tone={r.status === "done" ? "positive" : r.status === "error" ? "negative" : "warning"}>{r.status}</Pill>
                <span className="num ml-auto text-[12px] text-muted">{new Date(r.created).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
