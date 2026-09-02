#!/usr/bin/env python3
"""Independent recompute of two pairwise differences (not ten_pairwise).

Walk membership sequentially. Used by probe 2 so the reviewer signal is not
the same set-subtraction helper as probe 1.
"""
from __future__ import annotations

from typing import Iterable


def minus(left: Iterable[str], right: Iterable[str]) -> list[str]:
    blocked = frozenset(right)
    out: list[str] = []
    seen: set[str] = set()
    for item in left:
        if item in blocked or item in seen:
            continue
        seen.add(item)
        out.append(item)
    out.sort()
    return out


def both_directions(left: Iterable[str], right: Iterable[str]) -> dict:
    lmr = minus(left, right)
    rml = minus(right, left)
    return {
        "left_minus_right": lmr,
        "right_minus_left": rml,
        "symmetric_count": len(lmr) + len(rml),
    }
