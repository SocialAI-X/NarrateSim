import { create } from "zustand";
import { get as idbGet, set as idbSet, del as idbDel, keys as idbKeys } from "idb-keyval";
import { forkAt, hasDefense, Simulation, triadSummary, variantOf } from "@/engine/engine";
import { BrowserLLM, type LLMSettings } from "@/engine/llm";
import { PRESETS } from "@/engine/presets";
import { topicById } from "@/engine/topics";
import type { RunRecord, Scenario } from "@/engine/types";

export type Variant = "baseline" | "attacked" | "defended";

export interface Bundle {
  id: string;
  name: string;
  created: string;
  scenario: Scenario;
  runs: Partial<Record<Variant, RunRecord>>;
  forks: RunRecord[];
  note?: string;
}

const safe = <T,>(f: () => T, fallback: T): T => {
  try {
    return f();
  } catch {
    return fallback;
  }
};

const LLM_KEY = "nss.llm.v1";
export const defaultLLM: LLMSettings = {
  transport: "gateway",
  apiBase: __PAGES__ ? "http://localhost:8765" : "",
  baseUrl: "https://api.deepseek.com/v1",
  apiKey: "",
  model: "deepseek-chat",
  concurrency: 8,
  temperature: 0.8,
};

export function primaryVariant(s: Scenario): Variant {
  if (!s.adversary.enabled) return "baseline";
  return hasDefense(s) ? "defended" : "attacked";
}

interface LabState {
  scenario: Scenario;
  runs: Partial<Record<Variant, RunRecord>>;
  forks: RunRecord[];
  bundleId: string | null;
  status: "idle" | "running" | "done" | "error";
  message: string;
  progress: { done: number; total: number };
  cursor: number;
  playing: boolean;
  speed: number; // rounds per second
  selected: number | null;
  view: Variant;
  llm: LLMSettings;
  llmLog: { agent: number; round: number; ms: number; ok: boolean }[];
  setScenario: (f: (s: Scenario) => Scenario) => void;
  loadScenario: (s: Scenario) => void;
  run: () => Promise<void>;
  stop: () => void;
  fork: (at: number, patch: Partial<Scenario>, label?: string) => RunRecord;
  setCursor: (r: number) => void;
  setPlaying: (p: boolean) => void;
  setSpeed: (s: number) => void;
  select: (id: number | null) => void;
  setView: (v: Variant) => void;
  setLLM: (p: Partial<LLMSettings>) => void;
  openBundle: (b: Bundle) => void;
  saveBundle: (name?: string) => Promise<Bundle | null>;
}

let cancel = false;

export const useLab = create<LabState>((set, get) => ({
  scenario: structuredClone(PRESETS[0].scenario),
  runs: {},
  forks: [],
  bundleId: null,
  status: "idle",
  message: "",
  progress: { done: 0, total: 0 },
  cursor: 0,
  playing: false,
  speed: 3,
  selected: null,
  view: "attacked",
  llm: { ...defaultLLM, ...safe(() => JSON.parse(localStorage.getItem(LLM_KEY) ?? "{}"), {}) },
  llmLog: [],

  setScenario: (f) => set({ scenario: f(structuredClone(get().scenario)) }),
  loadScenario: (s) => set({ scenario: structuredClone(s), runs: {}, forks: [], status: "idle", cursor: 0, selected: null, bundleId: null }),

  async run() {
    const s = get().scenario;
    const primary = primaryVariant(s);
    const variants: Variant[] = primary === "baseline" ? ["baseline"] : primary === "attacked" ? ["baseline", "attacked"] : ["baseline", "attacked", "defended"];
    cancel = false;
    set({ status: "running", runs: {}, forks: [], cursor: 0, playing: false, view: primary, message: "", llmLog: [], bundleId: null, progress: { done: 0, total: variants.length * s.society.rounds } });

    if (s.engine.mind === "heuristic") {
      const runs: Partial<Record<Variant, RunRecord>> = {};
      for (const v of variants) runs[v] = new Simulation(variantOf(s, v), v).runSync().record();
      set({ runs, status: "done", playing: true, progress: { done: variants.length * s.society.rounds, total: variants.length * s.society.rounds } });
      return;
    }

    // LLM agents: the primary variant streams first so the network fills in while it runs.
    const order = [primary, ...variants.filter((v) => v !== primary)];
    const topic = topicById(s.topic);
    const llm = new BrowserLLM(get().llm, topic, s.adversary.target);
    llm.onTrace = (t) => set({ llmLog: [...get().llmLog.slice(-400), t] });
    try {
      for (const v of order) {
        const sim = new Simulation(variantOf(s, v), v);
        const push = () => set({ runs: { ...get().runs, [v]: sim.record() } });
        push();
        while (!sim.done) {
          if (cancel) throw new Error("Stopped");
          await sim.step(llm);
          push();
          set({ progress: { done: get().progress.done + 1, total: get().progress.total }, ...(v === primary ? { cursor: sim.round } : {}) });
        }
      }
      set({ status: "done", message: `${llm.stats().calls} LLM calls, ${llm.stats().tokens.toLocaleString()} tokens` });
    } catch (e) {
      set({ status: get().runs[primary]?.frames.length ? "done" : "error", message: (e as Error).message });
    }
  },
  stop: () => {
    cancel = true;
    set({ playing: false });
  },

  fork(at, patch, label) {
    const s = get().scenario;
    const base = get().runs[get().view] ?? get().runs[primaryVariant(s)];
    if (!base) throw new Error("Run the scenario first");
    const sim = forkAt(base.scenario, at, patch, base.meta.id);
    sim.runSync();
    const rec = sim.record();
    rec.meta.variant = "fork";
    (rec.meta as any).label = label ?? `Fork at round ${at}`;
    set({ forks: [...get().forks, rec] });
    return rec;
  },

  setCursor: (r) => set({ cursor: r }),
  setPlaying: (p) => set({ playing: p }),
  setSpeed: (sp) => set({ speed: sp }),
  select: (id) => set({ selected: id }),
  setView: (v) => set({ view: v }),
  setLLM: (p) => {
    const llm = { ...get().llm, ...p };
    safe(() => localStorage.setItem(LLM_KEY, JSON.stringify(llm)), undefined);
    set({ llm });
  },
  openBundle: (b) => {
    const pv = primaryVariant(b.scenario);
    set({ scenario: structuredClone(b.scenario), runs: b.runs, forks: b.forks ?? [], bundleId: b.id, status: "done", cursor: 0, playing: false, view: b.runs[pv] ? pv : (Object.keys(b.runs)[0] as Variant), selected: null });
  },
  async saveBundle(name) {
    const { runs, scenario, forks, bundleId } = get();
    if (!Object.keys(runs).length) return null;
    const b: Bundle = { id: bundleId ?? `b-${Date.now().toString(36)}`, name: name ?? scenario.name, created: new Date().toISOString(), scenario, runs, forks };
    await library.put(b);
    set({ bundleId: b.id });
    return b;
  },
}));

export function summaryOf(runs: Partial<Record<Variant, RunRecord>>) {
  if (!runs.baseline || !runs.attacked) return null;
  return triadSummary(runs.baseline, runs.attacked, runs.defended);
}

/* ------------------------------------------------------------- library (IndexedDB) */
export const library = {
  async list(): Promise<Bundle[]> {
    try {
      const ks = (await idbKeys()).filter((k) => String(k).startsWith("bundle:"));
      const all = await Promise.all(ks.map((k) => idbGet<Bundle>(k)));
      return (all.filter(Boolean) as Bundle[]).sort((a, b) => b.created.localeCompare(a.created));
    } catch {
      return [];
    }
  },
  async put(b: Bundle) {
    try {
      await idbSet(`bundle:${b.id}`, b);
    } catch {
      /* storage unavailable: the run stays in memory */
    }
  },
  async remove(id: string) {
    try {
      await idbDel(`bundle:${id}`);
    } catch {
      /* ignore */
    }
  },
};

export function download(name: string, data: unknown, type = "application/json") {
  const blob = new Blob([typeof data === "string" ? data : JSON.stringify(data, null, 1)], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
