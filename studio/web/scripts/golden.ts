/**
 * Writes the data the Python engine shares with this one, and golden runs for the parity test.
 *   npm run golden
 */
import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { Simulation, variantOf } from "../src/engine/engine";
import { PRESETS } from "../src/engine/presets";
import { FIRST, LAST, POPULATIONS, TOPICS } from "../src/engine/topics";
import { hash32, normal, u01 } from "../src/engine/rng";

const __dirname = import.meta.dirname;
const backend = resolve(__dirname, "../../backend");
writeFileSync(resolve(backend, "nsstudio/data/shared.json"), JSON.stringify({ topics: TOPICS, populations: POPULATIONS, first: FIRST, last: LAST }, null, 1));
writeFileSync(resolve(backend, "nsstudio/data/presets.json"), JSON.stringify(PRESETS, null, 1));
for (const p of PRESETS) writeFileSync(resolve(__dirname, `../../examples/${p.id}.json`), JSON.stringify(p.scenario, null, 2));

// RNG vectors
const rng = { hash: [] as number[][], u01: [] as number[][], normal: [] as number[][] };
for (let i = 0; i < 64; i++) {
  const args = [i * 7919, i % 11, i * 3, 5 - (i % 5), i * i, 1];
  rng.hash.push([...args, hash32(args[0], args[1], args[2], args[3], args[4], args[5])]);
  rng.u01.push([...args, u01(args[0], args[1], args[2], args[3], args[4], args[5])]);
  rng.normal.push([...args.slice(0, 5), normal(args[0], args[1], args[2], args[3], args[4])]);
}
writeFileSync(resolve(backend, "tests/fixtures/rng.json"), JSON.stringify(rng));

// Golden runs: small societies, every preset, all three variants.
const golden = PRESETS.map((p) => {
  const s = structuredClone(p.scenario);
  s.society.n_agents = 60;
  s.society.rounds = 8;
  return {
    id: p.id,
    scenario: s,
    variants: (["baseline", "attacked", "defended"] as const).map((v) => {
      const r = new Simulation(variantOf(s, v), v).runSync().record();
      return { variant: v, edges: r.graph.edges, frames: r.frames.map((f) => ({ stances: f.stances, metrics: f.metrics, posts: f.posts.map((x) => [x.author, x.reply_to, x.stance, x.framing, x.label, x.text]) })) };
    }),
  };
});
writeFileSync(resolve(backend, "tests/fixtures/golden.json"), JSON.stringify(golden));
console.log(`wrote shared data, ${PRESETS.length} presets, rng vectors and ${golden.length} golden scenarios`);
