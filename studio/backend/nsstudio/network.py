"""Graph generators and attacker placement, mirroring ``network.ts``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Set, Tuple

from .rng import Stream, js_round, rand_int, shuffled, u01


@dataclass
class Graph:
    n: int
    edges: List[Tuple[int, int]]
    adj: List[List[int]]
    communities: List[int]


def _key(a: int, b: int) -> int:
    return a * 100003 + b if a < b else b * 100003 + a


def _finalize(n: int, keys: Set[int], communities: List[int], seed: int) -> Graph:
    adj: List[List[int]] = [[] for _ in range(n)]
    for k in keys:
        a, b = divmod(k, 100003)
        adj[a].append(b)
        adj[b].append(a)
    for i in range(n):
        if not adj[i] and n > 1:
            j = rand_int(n - 1, seed, Stream.Network, 9, i)
            if j >= i:
                j += 1
            keys.add(_key(i, j))
            adj[i].append(j)
            adj[j].append(i)
    for lst in adj:
        lst.sort()
    edges = [(a, b) for a in range(n) for b in adj[a] if a < b]
    return Graph(n, edges, adj, communities)


def scale_free(n: int, m: int, seed: int) -> Graph:
    """Barabási–Albert, the same procedure as networkx.barabasi_albert_graph."""
    m = max(1, min(m, n - 1))
    keys: Set[int] = set()
    targets = list(range(m))
    repeated: List[int] = []
    for source in range(m, n):
        for t in targets:
            keys.add(_key(source, t))
        repeated.extend(targets)
        repeated.extend([source] * m)
        chosen: Set[int] = set()
        k = 0
        while len(chosen) < m:
            chosen.add(repeated[rand_int(len(repeated), seed, Stream.Network, 1, source, k)])
            k += 1
        targets = sorted(chosen)
    return _finalize(n, keys, [0] * n, seed)


def small_world(n: int, half: int, p: float, seed: int) -> Graph:
    half = max(1, min(half, (n - 1) // 2))
    keys: Set[int] = set()
    for i in range(n):
        for j in range(1, half + 1):
            keys.add(_key(i, (i + j) % n))
    for j in range(1, half + 1):
        for i in range(n):
            b = (i + j) % n
            if u01(seed, Stream.Network, 2, i, j) < p:
                for tries in range(20):
                    w = rand_int(n, seed, Stream.Network, 3, i * 64 + j, tries)
                    if w != i and _key(i, w) not in keys:
                        keys.discard(_key(i, b))
                        keys.add(_key(i, w))
                        break
    return _finalize(n, keys, [0] * n, seed)


def random_graph(n: int, degree: float, seed: int) -> Graph:
    p = min(1.0, degree / max(1, n - 1))
    keys = {_key(a, b) for a in range(n) for b in range(a + 1, n) if u01(seed, Stream.Network, 4, a, b) < p}
    return _finalize(n, keys, [0] * n, seed)


def communities(n: int, degree: float, k: int, homophily: float, seed: int) -> Graph:
    k = max(2, min(k, 8))
    order = shuffled(list(range(n)), seed, Stream.Network, 5)
    comm = [0] * n
    for idx, node in enumerate(order):
        comm[node] = idx % k
    size = n / k
    p_in = min(1.0, degree * homophily / max(1.0, size - 1))
    p_out = min(1.0, degree * (1 - homophily) / max(1.0, n - size))
    keys: Set[int] = set()
    for a in range(n):
        for b in range(a + 1, n):
            p = p_in if comm[a] == comm[b] else p_out
            if u01(seed, Stream.Network, 6, a, b) < p:
                keys.add(_key(a, b))
    return _finalize(n, keys, comm, seed)


def build_graph(s: Dict) -> Graph:
    n = s["society"]["n_agents"]
    net = s["network"]
    seed = s["seed"]
    table: Dict[str, Callable[[], Graph]] = {
        "scale_free": lambda: scale_free(n, js_round(net["degree"]), seed),
        "small_world": lambda: small_world(n, js_round(net["degree"]), net["rewire"], seed),
        "random": lambda: random_graph(n, net["degree"] * 2, seed),
        "communities": lambda: communities(n, net["degree"] * 2, net["communities"], net["homophily"], seed),
    }
    return table[net["kind"]]()


def betweenness(g: Graph) -> List[float]:
    """Brandes betweenness, unweighted."""
    n = g.n
    cb = [0.0] * n
    for s in range(n):
        stack: List[int] = []
        pred: List[List[int]] = [[] for _ in range(n)]
        sigma = [0.0] * n
        dist = [-1] * n
        sigma[s] = 1.0
        dist[s] = 0
        queue = [s]
        head = 0
        while head < len(queue):
            v = queue[head]
            head += 1
            stack.append(v)
            for w in g.adj[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    queue.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    pred[w].append(v)
        delta = [0.0] * n
        while stack:
            w = stack.pop()
            for v in pred[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    return cb


def place_attackers(g: Graph, count: int, placement: str, seed: int) -> List[int]:
    ids = list(range(g.n))
    count = max(0, min(count, g.n - 1))
    if count == 0:
        return []
    deg = [len(lst) for lst in g.adj]
    if placement == "hub":
        return sorted(ids, key=lambda i: (-deg[i], i))[:count]
    if placement == "bridge":
        bc = betweenness(g)
        return sorted(ids, key=lambda i: (-bc[i], i))[:count]
    if placement == "periphery":
        return sorted(ids, key=lambda i: (deg[i], i))[:count]
    return shuffled(ids, seed, Stream.Placement, 1)[:count]
