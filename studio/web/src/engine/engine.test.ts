import { describe, expect, it } from "vitest";
import { forkAt, Simulation, triadSummary, variantOf } from "./engine";
import { parseDecision } from "./llm";
import { PRESETS } from "./presets";
import { runSweep } from "./sweep";
import type { Scenario } from "./types";

const small = (i = 0, n = 50, rounds = 8): Scenario => {
  const s = structuredClone(PRESETS[i].scenario);
  s.society.n_agents = n;
  s.society.rounds = rounds;
  return s;
};

describe("engine", () => {
  it("is deterministic", () => {
    const a = new Simulation(small()).runSync().record();
    const b = new Simulation(small()).runSync().record();
    expect(a.frames.map((f) => f.stances)).toEqual(b.frames.map((f) => f.stances));
  });

  it("keeps twins identical until the operation is first read", () => {
    const s = small(0, 50, 10);
    s.adversary.start = 5;
    const base = new Simulation(variantOf(s, "baseline")).runSync().record();
    const att = new Simulation(variantOf(s, "attacked")).runSync().record();
    for (let r = 0; r <= 5; r++) expect(att.frames[r].stances).toEqual(base.frames[r].stances);
    expect(att.frames[10].stances).not.toEqual(base.frames[10].stances);
  });

  it("forks replay the parent exactly up to the fork round", () => {
    const s = variantOf(small(0, 50, 10), "attacked");
    const parent = new Simulation(structuredClone(s)).runSync().record();
    const child = forkAt(s, 4, { adversary: { ...s.adversary, end: 4 } }, parent.meta.id).runSync().record();
    for (let r = 0; r <= 4; r++) expect(child.frames[r].stances).toEqual(parent.frames[r].stances);
    expect(child.frames[10].metrics.mean).not.toBe(parent.frames[10].metrics.mean);
  });

  it("measures an attack effect and protection", () => {
    const s = small(1, 120, 16);
    const [b, a, d] = (["baseline", "attacked", "defended"] as const).map((v) => new Simulation(variantOf(s, v)).runSync().record());
    const sum = triadSummary(b, a, d);
    expect(sum.attack_effect).toBeGreaterThan(0.5);
    expect(sum.protection!).toBeGreaterThan(0.2);
  });

  it("runs a sweep and reports intervals", () => {
    const cells = [...runSweep({ base: small(0, 40, 6), x: "placement", y: null, metric: "attack_effect", seeds: 2 })].map((s) => s.cell);
    expect(cells).toHaveLength(4);
    expect(cells.every((c) => c.n === 2 && c.mean !== null)).toBe(true);
  });
});

describe("LLM output parsing", () => {
  it("reads the BDI block and a JSON decision wrapped in chatter", () => {
    const d = parseDecision('[BDI]\nBelief: a\nDesire: b\nIntention: c\n[/BDI]\nOK: {"action":"speak","target":null,"stance":-9,"confidence":4,"message":"hi"}');
    expect(d.action).toBe("speak");
    expect(d.stance).toBe(-5);
    expect(d.bdi?.intention).toBe("c");
  });
  it("falls back to silence on garbage", () => {
    expect(parseDecision("nothing here").action).toBe("silent");
  });
});
