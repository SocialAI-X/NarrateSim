import { randInt, shuffled, Stream, u01 } from "./rng";
import type { NetworkKind, Placement, Scenario } from "./types";

export interface Graph {
  n: number;
  edges: [number, number][];
  adj: number[][];
  communities: number[];
}

function finalize(n: number, set: Set<number>, communities: number[], seed: number): Graph {
  const adj: number[][] = Array.from({ length: n }, () => []);
  const key = (a: number, b: number) => (a < b ? a * 100003 + b : b * 100003 + a);
  for (const k of set) {
    const a = Math.floor(k / 100003);
    const b = k % 100003;
    adj[a].push(b);
    adj[b].push(a);
  }
  // No isolated agents: tie each one to a deterministic partner.
  for (let i = 0; i < n; i++) {
    if (adj[i].length === 0 && n > 1) {
      let j = randInt(n - 1, seed, Stream.Network, 9, i);
      if (j >= i) j += 1;
      set.add(key(i, j));
      adj[i].push(j);
      adj[j].push(i);
    }
  }
  adj.forEach((l) => l.sort((x, y) => x - y));
  const edges: [number, number][] = [];
  for (let a = 0; a < n; a++) for (const b of adj[a]) if (a < b) edges.push([a, b]);
  return { n, edges, adj, communities };
}

const pairKey = (a: number, b: number) => (a < b ? a * 100003 + b : b * 100003 + a);

/** Barabási–Albert preferential attachment, same procedure as networkx.barabasi_albert_graph. */
function scaleFree(n: number, m: number, seed: number): Graph {
  m = Math.max(1, Math.min(m, n - 1));
  const set = new Set<number>();
  let targets = Array.from({ length: m }, (_, i) => i);
  const repeated: number[] = [];
  for (let source = m; source < n; source++) {
    for (const t of targets) set.add(pairKey(source, t));
    repeated.push(...targets);
    for (let k = 0; k < m; k++) repeated.push(source);
    const chosen = new Set<number>();
    let k = 0;
    while (chosen.size < m) {
      chosen.add(repeated[randInt(repeated.length, seed, Stream.Network, 1, source, k)]);
      k++;
    }
    targets = Array.from(chosen).sort((a, b) => a - b);
  }
  return finalize(n, set, new Array(n).fill(0), seed);
}

/** Watts–Strogatz ring lattice with rewiring. */
function smallWorld(n: number, half: number, p: number, seed: number): Graph {
  half = Math.max(1, Math.min(half, Math.floor((n - 1) / 2)));
  const set = new Set<number>();
  for (let i = 0; i < n; i++) for (let j = 1; j <= half; j++) set.add(pairKey(i, (i + j) % n));
  for (let j = 1; j <= half; j++) {
    for (let i = 0; i < n; i++) {
      const b = (i + j) % n;
      if (u01(seed, Stream.Network, 2, i, j) < p) {
        let tries = 0;
        while (tries < 20) {
          const w = randInt(n, seed, Stream.Network, 3, i * 64 + j, tries);
          if (w !== i && !set.has(pairKey(i, w))) {
            set.delete(pairKey(i, b));
            set.add(pairKey(i, w));
            break;
          }
          tries++;
        }
      }
    }
  }
  return finalize(n, set, new Array(n).fill(0), seed);
}

/** Erdős–Rényi with the requested mean degree. */
function random(n: number, degree: number, seed: number): Graph {
  const p = Math.min(1, degree / Math.max(1, n - 1));
  const set = new Set<number>();
  for (let a = 0; a < n; a++) for (let b = a + 1; b < n; b++) if (u01(seed, Stream.Network, 4, a, b) < p) set.add(pairKey(a, b));
  return finalize(n, set, new Array(n).fill(0), seed);
}

/** Stochastic block model: echo chambers with a set share of ties inside each group. */
function communities(n: number, degree: number, k: number, homophily: number, seed: number): Graph {
  k = Math.max(2, Math.min(k, 8));
  const order = shuffled(Array.from({ length: n }, (_, i) => i), seed, Stream.Network, 5);
  const comm = new Array(n).fill(0);
  order.forEach((node, idx) => (comm[node] = idx % k));
  const size = n / k;
  const pIn = Math.min(1, (degree * homophily) / Math.max(1, size - 1));
  const pOut = Math.min(1, (degree * (1 - homophily)) / Math.max(1, n - size));
  const set = new Set<number>();
  for (let a = 0; a < n; a++)
    for (let b = a + 1; b < n; b++) {
      const p = comm[a] === comm[b] ? pIn : pOut;
      if (u01(seed, Stream.Network, 6, a, b) < p) set.add(pairKey(a, b));
    }
  return finalize(n, set, comm, seed);
}

export function buildGraph(s: Scenario): Graph {
  const n = s.society.n_agents;
  const { kind, degree, rewire, communities: k, homophily } = s.network;
  const seed = s.seed;
  const table: Record<NetworkKind, () => Graph> = {
    scale_free: () => scaleFree(n, Math.round(degree), seed),
    small_world: () => smallWorld(n, Math.round(degree), rewire, seed),
    random: () => random(n, degree * 2, seed),
    communities: () => communities(n, degree * 2, k, homophily, seed),
  };
  return table[kind]();
}

/** Brandes betweenness (unweighted). O(V·E), fine up to a few thousand agents. */
export function betweenness(g: Graph): number[] {
  const n = g.n;
  const cb = new Array(n).fill(0);
  for (let s = 0; s < n; s++) {
    const stack: number[] = [];
    const pred: number[][] = Array.from({ length: n }, () => []);
    const sigma = new Array(n).fill(0);
    const dist = new Array(n).fill(-1);
    sigma[s] = 1;
    dist[s] = 0;
    const queue = [s];
    let head = 0;
    while (head < queue.length) {
      const v = queue[head++];
      stack.push(v);
      for (const w of g.adj[v]) {
        if (dist[w] < 0) {
          dist[w] = dist[v] + 1;
          queue.push(w);
        }
        if (dist[w] === dist[v] + 1) {
          sigma[w] += sigma[v];
          pred[w].push(v);
        }
      }
    }
    const delta = new Array(n).fill(0);
    while (stack.length) {
      const w = stack.pop()!;
      for (const v of pred[w]) delta[v] += (sigma[v] / sigma[w]) * (1 + delta[w]);
      if (w !== s) cb[w] += delta[w];
    }
  }
  return cb;
}

/** Choose the accounts the operation controls. */
export function placeAttackers(g: Graph, count: number, placement: Placement, seed: number): number[] {
  const ids = Array.from({ length: g.n }, (_, i) => i);
  count = Math.max(0, Math.min(count, g.n - 1));
  if (count === 0) return [];
  const byDesc = (score: number[]) => ids.slice().sort((a, b) => score[b] - score[a] || a - b);
  const deg = g.adj.map((l) => l.length);
  switch (placement) {
    case "hub":
      return byDesc(deg).slice(0, count);
    case "bridge":
      return byDesc(betweenness(g)).slice(0, count);
    case "periphery":
      return ids.slice().sort((a, b) => deg[a] - deg[b] || a - b).slice(0, count);
    case "random":
    default:
      return shuffled(ids, seed, Stream.Placement, 1).slice(0, count);
  }
}
