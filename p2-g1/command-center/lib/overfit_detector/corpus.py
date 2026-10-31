"""Synthetic labeled corpus whose true rule is independent of the visible slice."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    id: str
    x: int
    label: int


def true_label(x: int) -> int:
    return int(x) % 2


def build_corpus(n: int = 80, *, seed: int = 206) -> list[Case]:
    cases: list[Case] = []
    for i in range(int(n)):
        x = (seed * 1103515245 + i * 12345) & 0x7FFFFFFF
        cid = f"case-{i:04d}-{x:08x}"
        cases.append(Case(id=cid, x=x, label=true_label(x)))
    return cases
