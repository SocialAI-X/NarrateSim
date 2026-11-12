"""Counter-based randomness, bit-for-bit identical to ``studio/web/src/engine/rng.ts``.

Every draw is a pure function of (seed, stream, round, agent, k). There is no generator state, so
counterfactual twins share their noise and forks need nothing but a state snapshot.
"""

from __future__ import annotations

import math
from typing import List, Sequence, TypeVar

T = TypeVar("T")
M32 = 0xFFFFFFFF


class Stream:
    Network = 1
    Society = 2
    Placement = 3
    Feed = 4
    Mind = 5
    Action = 6
    Text = 7
    Adversary = 8
    Defense = 9
    Guardian = 10
    Notes = 11


def _imul(a: int, b: int) -> int:
    return ((a & M32) * (b & M32)) & M32


def _fmix(h: int) -> int:
    h &= M32
    h ^= h >> 16
    h = _imul(h, 0x85EBCA6B)
    h ^= h >> 13
    h = _imul(h, 0xC2B2AE35)
    h ^= h >> 16
    return h & M32


def hash32(seed: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, e: int = 0) -> int:
    h = _fmix((seed & M32) ^ 0x9E3779B9)
    for x in (a, b, c, d, e):
        h = _fmix(h ^ _imul((int(x) & M32) + 0x632BE5AB, 0x9E3779B1))
    return h


def u01(seed: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, e: int = 0) -> float:
    return hash32(seed, a, b, c, d, e) / 4294967296.0


def normal(seed: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0) -> float:
    u1 = max(u01(seed, a, b, c, d, 1), 1e-12)
    u2 = u01(seed, a, b, c, d, 2)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def rand_int(n: int, seed: int, a: int = 0, b: int = 0, c: int = 0, d: int = 0, e: int = 0) -> int:
    return math.floor(u01(seed, a, b, c, d, e) * n)


def shuffled(items: Sequence[T], seed: int, a: int = 0, b: int = 0, c: int = 0) -> List[T]:
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = rand_int(i + 1, seed, a, b, c, i)
        out[i], out[j] = out[j], out[i]
    return out


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def js_round(x: float) -> int:
    """JavaScript's Math.round: halves go toward +infinity."""
    return math.floor(x + 0.5)


def round2(x: float) -> float:
    return js_round(x * 100) / 100


def sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0
