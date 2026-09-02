#!/usr/bin/env python3
"""Trivial-fork / renamed-copy detector for the 160-candidate floor.

A candidate is EXCLUDED when it shares a structural mechanism fingerprint with
an earlier retained incumbent. Name similarity alone never excludes: that is
the false-positive control the catalog names (a distinct sibling with similar
naming must be retained).

The floor is reported twice: raw (all rows) and de-forked (one row per
fingerprint). The de-forked number is the one that counts toward the floor.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fingerprint import fingerprint
from lexical import jaccard

SIMILAR_NAME_THRESHOLD = 0.55


def _name(c: dict) -> str:
    return str(c.get("name") or c.get("id") or "")


def name_similarity(a: str, b: str) -> float:
    """Character-3gram Jaccard on lowercased names. Cheap and rename-sensitive."""
    aa, bb = a.lower(), b.lower()
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    ga = {aa[i : i + 3] for i in range(max(1, len(aa) - 2))}
    gb = {bb[i : i + 3] for i in range(max(1, len(bb) - 2))}
    if not ga or not gb:
        return 0.0
    return len(ga & gb) / len(ga | gb)


def naive_name_exclude(candidates: list[dict], threshold: float = SIMILAR_NAME_THRESHOLD) -> dict:
    """False-positive control instrument: exclude by similar naming.

    This is NOT the production detector. It is the both-states opposite: it
    wrongly drops a distinct sibling whose name looks like an incumbent.
    """
    kept: list[dict] = []
    excluded: list[dict] = []
    for cand in candidates:
        n = _name(cand)
        hit = None
        for inc in kept:
            sim = name_similarity(n, _name(inc))
            if sim >= threshold:
                hit = inc
                break
        row = dict(cand)
        if hit is not None:
            row = {
                **cand,
                "excluded": True,
                "reason": "similar-name",
                "kept_id": hit.get("id"),
                "name_similarity": round(name_similarity(n, _name(hit)), 4),
            }
            excluded.append(row)
        else:
            kept.append(cand)
    return {
        "instrument": "naive-name-similarity",
        "raw_count": len(candidates),
        "de_forked_count": len(kept),
        "excluded": excluded,
        "kept_ids": [c.get("id") for c in kept],
        "excluded_ids": [c.get("id") for c in excluded],
    }


def detect(candidates: list[dict]) -> dict[str, Any]:
    """Exclude renamed copies / trivial structural forks; keep distinct siblings."""
    order = list(candidates)
    fp_of: dict[str, str] = {}
    first_of_fp: dict[str, dict] = {}
    clusters: dict[str, list[str]] = defaultdict(list)
    kept: list[dict] = []
    excluded: list[dict] = []

    for cand in order:
        cid = str(cand.get("id"))
        fp = fingerprint(cand)
        fp_of[cid] = fp
        clusters[fp].append(cid)
        if fp not in first_of_fp:
            first_of_fp[fp] = cand
            kept.append(cand)
            continue
        inc = first_of_fp[fp]
        excluded.append(
            {
                "id": cid,
                "name": _name(cand),
                "fingerprint": fp,
                "kept_id": inc.get("id"),
                "kept_name": _name(inc),
                "reason": "structural-fingerprint-match",
                "lexical_jaccard": round(jaccard(cand, inc), 4),
                "name_similarity": round(name_similarity(_name(cand), _name(inc)), 4),
            }
        )

    kept_ids = [str(c.get("id")) for c in kept]
    excluded_ids = [str(r["id"]) for r in excluded]
    raw = len(order)
    de_forked = len(kept)
    return {
        "instrument": "structural-fingerprint-trivial-fork",
        "spec_anchor": "_USER-PROMPTS.md:10725",
        "raw_count": raw,
        "de_forked_count": de_forked,
        "floor_count": de_forked,
        "floor_counts_as": "de_forked",
        "excluded_count": len(excluded),
        "cluster_count": len(clusters),
        "kept_ids": kept_ids,
        "excluded_ids": excluded_ids,
        "excluded": excluded,
        "clusters": {fp: ids for fp, ids in clusters.items() if len(ids) > 1},
        "fingerprints": fp_of,
        "notes": (
            "raw_count is the unfiltered candidate list. de_forked_count is the "
            "floor that counts: one retained row per structural fingerprint. "
            "Renamed copies and trivial isomorphic forks are excluded. A "
            "genuinely distinct sibling that merely shares similar naming is "
            "retained because its fingerprint differs."
        ),
    }


def both_states(corpus_with_plant: list[dict], distinct_sibling_id: str, planted_id: str) -> dict:
    """Catalog evidence: plant excluded; similar-name distinct sibling retained."""
    structural = detect(corpus_with_plant)
    naive = naive_name_exclude(corpus_with_plant)
    plant_excluded = planted_id in structural["excluded_ids"]
    sibling_retained = distinct_sibling_id in structural["kept_ids"]
    naive_drops_sibling = distinct_sibling_id in naive["excluded_ids"]
    return {
        "planted_renamed_copy_excluded": plant_excluded,
        "distinct_similar_name_sibling_retained": sibling_retained,
        "naive_name_matcher_drops_sibling": naive_drops_sibling,
        "both_states_pass": plant_excluded and sibling_retained,
        "false_positive_control_pass": sibling_retained and naive_drops_sibling,
        "structural": {
            "raw_count": structural["raw_count"],
            "de_forked_count": structural["de_forked_count"],
            "excluded_ids": structural["excluded_ids"],
            "kept_ids": structural["kept_ids"],
        },
        "naive": {
            "raw_count": naive["raw_count"],
            "de_forked_count": naive["de_forked_count"],
            "excluded_ids": naive["excluded_ids"],
            "kept_ids": naive["kept_ids"],
        },
    }
