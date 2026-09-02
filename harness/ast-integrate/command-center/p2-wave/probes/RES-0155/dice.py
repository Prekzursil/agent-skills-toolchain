#!/usr/bin/env python3
"""Probe-2 settling math: Dice coefficient + all-KEEP-when-redundant mutant.

Does not import overlap.py. Shares corpus + extractors only.
"""
from __future__ import annotations

from typing import Any

from corpus import SEED_A, SEED_B, load_index
from lenses import LENS_ORDER, UNIQUE_YIELD_THRESHOLD, extract_all, extract_lens


def dice(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    denom = len(a) + len(b)
    if denom == 0:
        return 1.0
    return (2.0 * len(a & b)) / float(denom)


def unique_ids(lens_id: str, sets: dict[str, set[str]]) -> list[str]:
    mine = sets[lens_id]
    others: set[str] = set()
    for lid, found in sets.items():
        if lid != lens_id:
            others |= found
    return sorted(mine - others)


def pairwise_dice(sets: dict[str, set[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(LENS_ORDER):
        for b in LENS_ORDER[i + 1 :]:
            inter = sets[a] & sets[b]
            only_a = sets[a] - sets[b]
            only_b = sets[b] - sets[a]
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "n_intersection": len(inter),
                    "n_only_a": len(only_a),
                    "n_only_b": len(only_b),
                    "dice": dice(sets[a], sets[b]),
                }
            )
    rows.sort(key=lambda r: (-r["dice"], r["a"], r["b"]))
    return rows


def self_dice(docs: list[dict] | None = None) -> dict[str, dict[str, Any]]:
    rows = docs if docs is not None else load_index()
    out: dict[str, dict[str, Any]] = {}
    for lid in LENS_ORDER:
        a = extract_lens(lid, seed=SEED_A, docs=rows)
        b = extract_lens(lid, seed=SEED_B, docs=rows)
        same = extract_lens(lid, seed=SEED_A, docs=rows)
        out[lid] = {
            "seed_a": SEED_A,
            "seed_b": SEED_B,
            "dice": dice(a, b),
            "identical_seed_dice": dice(a, same),
        }
    return out


def mutant_all_keep(sets: dict[str, set[str]]) -> dict[str, Any]:
    """Force every lens to KEEP even when unique yield is zero.

    A detector that accepts this has no redundancy gate.
    """
    recs = []
    for lid in LENS_ORDER:
        uniq = unique_ids(lid, sets)
        n = len(sets[lid])
        uy = (len(uniq) / float(n)) if n else 0.0
        recs.append(
            {
                "lens_id": lid,
                "action": "KEEP",
                "unique_yield": uy,
                "forced": True,
            }
        )
    n_zero = sum(1 for r in recs if r["unique_yield"] == 0.0 and sets[r["lens_id"]])
    accepted = all(r["action"] == "KEEP" for r in recs)
    return {
        "recommendations": recs,
        "n_zero_unique_forced_keep": n_zero,
        "accepted_all_keep": accepted,
        "should_reject": n_zero > 0 and accepted,
    }


def measure(docs: list[dict] | None = None) -> dict[str, Any]:
    rows = docs if docs is not None else load_index()
    extracted = extract_all(seed=None, docs=rows)
    sets = {k: set(v) for k, v in extracted.items()}
    noise = self_dice(rows)
    pairs = pairwise_dice(sets)
    yields = []
    for lid in LENS_ORDER:
        uniq = unique_ids(lid, sets)
        n = len(sets[lid])
        yields.append(
            {
                "lens_id": lid,
                "n_findings": n,
                "n_unique": len(uniq),
                "unique_ids": uniq,
                "unique_yield": (len(uniq) / float(n)) if n else 0.0,
            }
        )
    mutant = mutant_all_keep(sets)
    identical_ok = all(noise[lid]["identical_seed_dice"] == 1.0 for lid in LENS_ORDER)
    return {
        "derivation": "dice-coefficient-plus-all-keep-mutant",
        "unique_yield_threshold": UNIQUE_YIELD_THRESHOLD,
        "findings": extracted,
        "unique_yields": yields,
        "pairwise": pairs,
        "self_overlap": noise,
        "identical_seed_dice_all_one": identical_ok,
        "mutant": mutant,
        "mutant_rejected": bool(mutant["should_reject"]),
    }
