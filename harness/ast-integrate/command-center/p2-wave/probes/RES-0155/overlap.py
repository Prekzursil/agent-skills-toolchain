#!/usr/bin/env python3
"""Probe-1 settling math: Jaccard on mechanism-id sets + unique yield.

Does not import dice.py.
"""
from __future__ import annotations

from typing import Any

from corpus import SEED_A, SEED_B, load_index
from lenses import (
    LENS_ORDER,
    UNIQUE_YIELD_THRESHOLD,
    extract_all,
    extract_lens,
)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return len(a & b) / float(len(union))


def unique_yield(lens_id: str, sets: dict[str, set[str]]) -> dict[str, Any]:
    mine = sets[lens_id]
    others: set[str] = set()
    for lid, found in sets.items():
        if lid != lens_id:
            others |= found
    uniq = sorted(mine - others)
    n = len(mine)
    uy = (len(uniq) / float(n)) if n else 0.0
    return {
        "lens_id": lens_id,
        "n_findings": n,
        "n_unique": len(uniq),
        "unique_ids": uniq,
        "unique_yield": uy,
    }


def as_sets(extracted: dict[str, list[str]]) -> dict[str, set[str]]:
    return {k: set(v) for k, v in extracted.items()}


def pairwise_jaccard(sets: dict[str, set[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, a in enumerate(LENS_ORDER):
        for b in LENS_ORDER[i + 1 :]:
            ja = jaccard(sets[a], sets[b])
            rows.append(
                {
                    "a": a,
                    "b": b,
                    "intersection": sorted(sets[a] & sets[b]),
                    "union_n": len(sets[a] | sets[b]),
                    "jaccard": ja,
                }
            )
    rows.sort(key=lambda r: (-r["jaccard"], r["a"], r["b"]))
    return rows


def self_overlap(docs: list[dict] | None = None) -> dict[str, dict[str, Any]]:
    rows = docs if docs is not None else load_index()
    out: dict[str, dict[str, Any]] = {}
    for lid in LENS_ORDER:
        a = extract_lens(lid, seed=SEED_A, docs=rows)
        b = extract_lens(lid, seed=SEED_B, docs=rows)
        same = extract_lens(lid, seed=SEED_A, docs=rows)
        out[lid] = {
            "seed_a": SEED_A,
            "seed_b": SEED_B,
            "findings_a": sorted(a),
            "findings_b": sorted(b),
            "jaccard": jaccard(a, b),
            "identical_seed_jaccard": jaccard(a, same),
        }
    return out


def recommend(
    sets: dict[str, set[str]],
    noise: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    yields = {lid: unique_yield(lid, sets) for lid in LENS_ORDER}
    pairs = pairwise_jaccard(sets)
    by_lens: dict[str, list[dict[str, Any]]] = {lid: [] for lid in LENS_ORDER}
    for row in pairs:
        by_lens[row["a"]].append(row)
        by_lens[row["b"]].append(
            {
                "a": row["b"],
                "b": row["a"],
                "intersection": row["intersection"],
                "union_n": row["union_n"],
                "jaccard": row["jaccard"],
            }
        )
    recs: list[dict[str, Any]] = []
    for lid in LENS_ORDER:
        uy = yields[lid]["unique_yield"]
        partners = sorted(by_lens[lid], key=lambda r: (-r["jaccard"], r["b"]))
        best = partners[0] if partners else None
        nf = float(noise[lid]["jaccard"])
        max_j = float(best["jaccard"]) if best else 0.0
        partner = str(best["b"]) if best else None
        subset_of_partner = bool(
            best and sets[lid] and sets[lid].issubset(sets[str(best["b"])])
        )
        action = "KEEP"
        reason = (
            f"unique_yield={uy:.3f} >= threshold {UNIQUE_YIELD_THRESHOLD:.2f}"
        )
        if yields[lid]["n_findings"] == 0:
            action = "DROP"
            reason = "zero findings on the shared corpus"
        elif subset_of_partner and uy == 0.0:
            action = "MERGE"
            reason = (
                f"exact subset of {partner} (unique_yield=0); planted or measured "
                "redundancy on the canonical full corpus"
            )
        elif uy == 0.0 and max_j >= nf:
            action = "MERGE"
            reason = (
                f"unique_yield=0 and jaccard({partner})={max_j:.3f} >= "
                f"noise_floor={nf:.3f}"
            )
        elif uy == 0.0:
            action = "DROP"
            reason = (
                f"unique_yield=0 versus the union of other lenses, but max "
                f"jaccard={max_j:.3f} < noise_floor={nf:.3f} so no single merge "
                "target clears the seed-noise floor"
            )
        elif uy < UNIQUE_YIELD_THRESHOLD and max_j >= nf:
            action = "MERGE"
            reason = (
                f"unique_yield={uy:.3f} < {UNIQUE_YIELD_THRESHOLD:.2f} and "
                f"jaccard({partner})={max_j:.3f} >= noise_floor={nf:.3f}"
            )
        elif uy < UNIQUE_YIELD_THRESHOLD:
            action = "KEEP"
            reason = (
                f"unique_yield={uy:.3f} < {UNIQUE_YIELD_THRESHOLD:.2f} but max "
                f"jaccard={max_j:.3f} < noise_floor={nf:.3f}; overlap is "
                "indistinguishable from seed noise"
            )
        recs.append(
            {
                "lens_id": lid,
                "action": action,
                "partner": partner if action == "MERGE" else None,
                "unique_yield": uy,
                "max_jaccard": max_j,
                "noise_floor": nf,
                "reason": reason,
            }
        )
    return recs


def measure(docs: list[dict] | None = None) -> dict[str, Any]:
    rows = docs if docs is not None else load_index()
    extracted = extract_all(seed=None, docs=rows)
    sets = as_sets(extracted)
    noise = self_overlap(rows)
    yields = [unique_yield(lid, sets) for lid in LENS_ORDER]
    pairs = pairwise_jaccard(sets)
    recs = recommend(sets, noise)
    noise_values = [noise[lid]["jaccard"] for lid in LENS_ORDER]
    nf_mean = sum(noise_values) / float(len(noise_values))
    below_noise = [
        row
        for row in pairs
        if row["jaccard"] < nf_mean and row["jaccard"] > 0
    ]
    return {
        "derivation": "jaccard-set-overlap-on-mechanism-ids",
        "unique_yield_threshold": UNIQUE_YIELD_THRESHOLD,
        "findings": extracted,
        "unique_yields": yields,
        "pairwise": pairs,
        "self_overlap": noise,
        "noise_floor_mean": nf_mean,
        "cross_lens_overlap_below_mean_noise": below_noise,
        "recommendations": recs,
        "n_merge": sum(1 for r in recs if r["action"] == "MERGE"),
        "n_keep": sum(1 for r in recs if r["action"] == "KEEP"),
        "n_drop": sum(1 for r in recs if r["action"] == "DROP"),
    }
