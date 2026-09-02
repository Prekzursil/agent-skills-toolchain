#!/usr/bin/env python3
"""Planted mutants, distinct corpus, and gamed pad corpus for TST-0265."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISTINCT_PATH = HERE / "fixtures" / "distinct-100.json"

SEED = (
    "Cache expensive function results in a keyed in-memory store with TTL eviction."
)

# Exact rename: first mechanism verb swapped, remaining tokens identical.
EXACT_RENAME = (
    "Memoize expensive function results in a keyed in-memory store with TTL eviction."
)

# Single content-word swap: TTL -> timeout. Remainder identical.
SINGLE_WORD_SWAP = (
    "Cache expensive function results in a keyed in-memory store with timeout eviction."
)

# Full rewrite using only in-table synonyms / stems. Zero new mechanism.
FULL_REWRITE = (
    "Memoize costly callable outputs in an indexed RAM dictionary using expiry removal."
)

# OOV deep paraphrase of the SAME idea. Named blind class: SILENT.
DEEP_PARAPHRASE = (
    "Remember answers already computed so identical questions never "
    "trigger the slow path twice"
)

# Genuinely different mechanism (both-states negative for the mutant pair).
DISTINCT_CONTROL = (
    "Elect a Raft leader by randomized timeouts and replicate a log through that leader"
)

CAST = ("alice", "bob", "cara", "drew")
FLOOR = 100


def distinct_ideas() -> list[str]:
    ideas = json.loads(DISTINCT_PATH.read_text(encoding="utf-8"))
    if not isinstance(ideas, list) or len(ideas) != FLOOR:
        raise RuntimeError(f"distinct corpus size {len(ideas)!r} != {FLOOR}")
    if len(set(ideas)) != FLOOR:
        raise RuntimeError("distinct corpus has duplicate strings")
    return [str(x) for x in ideas]


def gamed_pad(seed: str = SEED, n: int = FLOOR) -> list[str]:
    """Cast instructed to pad to 100: suffix-integer variants of one seed."""
    if n < 1:
        return []
    out = [seed]
    for i in range(1, n):
        out.append(f"{seed} {i}")
    return out


def mixed_rename_pad(n: int = FLOOR, n_renames: int = 10) -> list[str]:
    """90 distinct mechanisms plus 10 high-overlap surface variants."""
    base = distinct_ideas()
    if n_renames >= n:
        raise RuntimeError("n_renames must be < n")
    keep = n - n_renames
    out = list(base[:keep])
    for i in range(n_renames):
        out.append(f"{base[i]} v2")
    if len(out) != n:
        raise RuntimeError(f"mixed corpus size {len(out)} != {n}")
    return out


def planted_mutants() -> list[dict]:
    return [
        {
            "class_id": "exact_rename",
            "want": "FIRE",
            "seed": SEED,
            "mutant": EXACT_RENAME,
            "note": "First-verb rename; raw Jaccard stays in the rename band.",
        },
        {
            "class_id": "single_word_swap",
            "want": "FIRE",
            "seed": SEED,
            "mutant": SINGLE_WORD_SWAP,
            "note": "TTL replaced by timeout; one content token differs.",
        },
        {
            "class_id": "full_rewrite_paraphrase",
            "want": "FIRE",
            "seed": SEED,
            "mutant": FULL_REWRITE,
            "note": "In-table synonym rewrite; S1 is blind, S2 key equality fires.",
        },
    ]


def blind_class() -> dict:
    return {
        "class_id": "oov_deep_paraphrase",
        "want": "SILENT",
        "seed": SEED,
        "mutant": DEEP_PARAPHRASE,
        "id": "TST-0265-OOV-DEEP-PARAPHRASE",
        "note": (
            "Out-of-vocabulary rewrite of the same mechanism. Shares neither "
            "high raw Jaccard nor a folded key, so it lands in the same band "
            "as a genuinely distinct idea."
        ),
    }
