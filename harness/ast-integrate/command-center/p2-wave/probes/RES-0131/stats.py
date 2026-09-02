"""Average-rank Spearman and a second Pearson-of-ranks implementation."""
from __future__ import annotations

import math
import random


def average_ranks(values: list[float]) -> list[float]:
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n != len(ys) or n < 2:
        raise ValueError("pearson needs equal series of length >= 2")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    if dx == 0.0 or dy == 0.0:
        return 0.0
    return num / (dx * dy)


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(average_ranks(xs), average_ranks(ys))


def fisher_yates(values: list[float], seed: int) -> list[float]:
    out = list(values)
    rng = random.Random(seed)
    for i in range(len(out) - 1, 0, -1):
        j = rng.randrange(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def shuffle_rhos(offline: list[float], online: list[float], seeds: list[int]) -> list[float]:
    return [spearman(offline, fisher_yates(online, s)) for s in seeds]


def median(xs: list[float]) -> float:
    ys = sorted(xs)
    n = len(ys)
    if n == 0:
        raise ValueError("empty")
    if n % 2:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])
