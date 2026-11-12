/**
 * Counter-based randomness.
 *
 * Every random draw in the engine is a pure function of (seed, stream, round, agent, k).
 * Nothing carries hidden generator state, which gives three properties the studio relies on:
 *
 *  1. Common random numbers. A baseline twin, an attacked run and a defended run of the same
 *     scenario draw identical noise for the same agent decision, so their difference measures
 *     the treatment rather than luck.
 *  2. Forks are free. Restoring a round snapshot is enough to continue a run; there is no
 *     generator state to save or replay.
 *  3. Cross-language parity. The mixing uses only 32-bit integer operations, mirrored in
 *     `studio/backend/nsstudio/rng.py`, so the browser and Python engines agree.
 */

export const enum Stream {
  Network = 1,
  Society = 2,
  Placement = 3,
  Feed = 4,
  Mind = 5,
  Action = 6,
  Text = 7,
  Adversary = 8,
  Defense = 9,
  Guardian = 10,
  Notes = 11,
}

function fmix(h: number): number {
  h ^= h >>> 16;
  h = Math.imul(h, 0x85ebca6b);
  h ^= h >>> 13;
  h = Math.imul(h, 0xc2b2ae35);
  h ^= h >>> 16;
  return h >>> 0;
}

/** 32-bit hash of the seed and up to five integer coordinates. */
export function hash32(seed: number, a = 0, b = 0, c = 0, d = 0, e = 0): number {
  let h = fmix((seed >>> 0) ^ 0x9e3779b9);
  for (const x of [a, b, c, d, e]) {
    h = fmix((h ^ Math.imul((x | 0) + 0x632be5ab, 0x9e3779b1)) >>> 0);
  }
  return h;
}

/** Uniform in [0, 1). */
export function u01(seed: number, a = 0, b = 0, c = 0, d = 0, e = 0): number {
  return hash32(seed, a, b, c, d, e) / 4294967296;
}

/** Standard normal via Box–Muller on two independent coordinates. */
export function normal(seed: number, a = 0, b = 0, c = 0, d = 0): number {
  const u1 = Math.max(u01(seed, a, b, c, d, 1), 1e-12);
  const u2 = u01(seed, a, b, c, d, 2);
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/** Integer in [0, n). */
export function randInt(n: number, seed: number, a = 0, b = 0, c = 0, d = 0, e = 0): number {
  return Math.floor(u01(seed, a, b, c, d, e) * n);
}

/** Deterministic Fisher–Yates shuffle (returns a new array). */
export function shuffled<T>(items: readonly T[], seed: number, a = 0, b = 0, c = 0): T[] {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = randInt(i + 1, seed, a, b, c, i);
    const t = out[i];
    out[i] = out[j];
    out[j] = t;
  }
  return out;
}

export const clamp = (x: number, lo: number, hi: number) => (x < lo ? lo : x > hi ? hi : x);
export const sigmoid = (x: number) => 1 / (1 + Math.exp(-x));
export const round2 = (x: number) => Math.round(x * 100) / 100;
