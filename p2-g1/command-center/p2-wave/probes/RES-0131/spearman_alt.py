"""Second Spearman implementation: covariance of midranks, no import of stats.spearman."""
from __future__ import annotations

import math


def midranks(values: list[float]) -> list[float]:
    indexed = sorted((v, i) for i, v in enumerate(values))
    ranks = [0.0] * len(values)
    n = len(indexed)
    start = 0
    while start < n:
        end = start
        while end + 1 < n and indexed[end + 1][0] == indexed[start][0]:
            end += 1
        # 1-based ranks start+1 .. end+1
        avg = (start + 1 + end + 1) / 2.0
        for k in range(start, end + 1):
            ranks[indexed[k][1]] = avg
        start = end + 1
    return ranks


def spearman_alt(xs: list[float], ys: list[float]) -> float:
    rx = midranks(xs)
    ry = midranks(ys)
    n = len(rx)
    mx = sum(rx) / n
    my = sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / n
    vx = sum((a - mx) ** 2 for a in rx) / n
    vy = sum((b - my) ** 2 for b in ry) / n
    if vx <= 0.0 or vy <= 0.0:
        return 0.0
    return cov / math.sqrt(vx * vy)
