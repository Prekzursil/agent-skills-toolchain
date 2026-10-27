"""Unique-ours-line property for three-way mergers (IMP-0031).

For seeded random line triples, every line that exists only in *ours* (not in
base, not in theirs) must survive either in the merged text or inside a
conflict record. A two-way overwrite drops those lines and fails the property.
"""
from __future__ import annotations

import random
from typing import Any, Callable

WORDS = ["alpha", "beta", "gamma", "delta", "kappa", "omega", "sigma", "theta",
         "retry", "timeout", "owner", "shipped", "local", "hook", "gate", "probe"]


def make_triple(rng: random.Random) -> tuple[list[str], list[str], list[str]]:
    n = rng.randint(4, 14)
    base = [f"{rng.choice(WORDS)} {i} {rng.choice(WORDS)}\n" for i in range(n)]
    ours = list(base)
    theirs = list(base)
    # ours: insert / modify unique lines
    for _ in range(rng.randint(0, 3)):
        pos = rng.randint(0, len(ours))
        ours.insert(pos, f"ours-only {rng.randrange(10**6)} {rng.choice(WORDS)}\n")
    if ours and rng.random() < 0.5:
        idx = rng.randrange(len(ours))
        ours[idx] = f"ours-edit {rng.randrange(10**6)}\n"
    # theirs: independent edits (append / modify / delete)
    for _ in range(rng.randint(0, 3)):
        pos = rng.randint(0, len(theirs))
        theirs.insert(pos, f"theirs-only {rng.randrange(10**6)} {rng.choice(WORDS)}\n")
    if len(theirs) > 2 and rng.random() < 0.4:
        del theirs[rng.randrange(len(theirs))]
    return base, ours, theirs


def unique_ours_lines(base: list[str], ours: list[str], theirs: list[str]) -> list[str]:
    bset, tset = set(base), set(theirs)
    return [ln for ln in ours if ln not in bset and ln not in tset]


def _result_text(result: Any) -> str:
    text = getattr(result, "text", None)
    if text is None:
        data = getattr(result, "data", None)
        text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(result)
    return text or ""


def _conflict_lines(result: Any) -> set[str]:
    lines: set[str] = set()
    for c in getattr(result, "conflicts", None) or []:
        for side in ("ours", "theirs", "base"):
            for ln in getattr(c, side, None) or []:
                lines.add(ln)
    return lines


def check_triple(merge_fn: Callable[..., Any], base: list[str], ours: list[str],
                 theirs: list[str], path: str = "notes.md") -> dict[str, Any]:
    result = merge_fn("".join(base).encode("utf-8"), "".join(ours).encode("utf-8"),
                      "".join(theirs).encode("utf-8"), path)
    text = _result_text(result)
    conflict_lines = _conflict_lines(result)
    uniq = unique_ours_lines(base, ours, theirs)
    lost = [ln for ln in uniq if ln not in text and ln not in conflict_lines]
    return {"unique": len(uniq), "lost": lost, "status": getattr(result, "status", None)}


def run_property(merge_fn: Callable[..., Any], n: int = 200, seed: int = 31) -> dict[str, Any]:
    rng = random.Random(seed)
    failures = 0
    with_unique = 0
    examples: list[dict[str, Any]] = []
    for i in range(n):
        base, ours, theirs = make_triple(rng)
        row = check_triple(merge_fn, base, ours, theirs)
        if row["unique"]:
            with_unique += 1
        if row["lost"]:
            failures += 1
            if len(examples) < 3:
                examples.append({"sample": i, "lost": row["lost"][:3], "status": row["status"]})
    return {
        "samples": n,
        "seed": seed,
        "with_unique_ours_lines": with_unique,
        "failures": failures,
        "ok": failures == 0 and with_unique > 0,
        "examples": examples,
        "merge_fn": getattr(merge_fn, "__name__", str(merge_fn)),
    }


__all__ = ["check_triple", "make_triple", "run_property", "unique_ours_lines"]
