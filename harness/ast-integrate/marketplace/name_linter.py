"""Name linter: fold + Levenshtein against the installed protected set."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Iterable

HOMOGLYPH = {
    "0": "o",
    "1": "l",
    "i": "l",
    "|": "l",
    "5": "s",
    "8": "b",
    "_": "-",
    "–": "-",
    "—": "-",
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
}


def fold_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name)).casefold()
    out: list[str] = []
    for ch in text:
        mapped = HOMOGLYPH.get(ch, ch)
        if mapped == "i":
            mapped = HOMOGLYPH.get(mapped, mapped)
        out.append(mapped)
    return "".join(out)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


@dataclass(frozen=True)
class Flag:
    candidate: str
    confused_with: str
    reason: str
    folded_distance: int


def lint_candidate(candidate: str, installed: Iterable[str]) -> list[Flag]:
    cand = str(candidate)
    flags: list[Flag] = []
    folded_c = fold_name(cand)
    for name in installed:
        if cand == name:
            continue
        dist = levenshtein(folded_c, fold_name(name))
        if dist <= 1:
            flags.append(
                Flag(
                    candidate=cand,
                    confused_with=str(name),
                    reason=f"folded-distance-{dist}",
                    folded_distance=dist,
                )
            )
    return flags
