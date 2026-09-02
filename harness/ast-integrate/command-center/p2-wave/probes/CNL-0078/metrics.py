#!/usr/bin/env python3
"""unique_ideas + completeness_score with an explicit shared idea-identity.

The catalog (TST-0282) names three coverage legs for completeness_score
(subquestions, categories, evidence classes) but never binds the *domain*
those numerators union over. That domain is `coverage_domain_identity`.
This module makes the expression executable by requiring both metrics to
share IDENTITY_CANONICAL.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable

IDENTITY_CANONICAL = "canonical-mechanism-v1"
IDENTITY_RAW = "raw-row-v1"

STOP = frozenset(
    "a an the of to for with via on in and or by at from into over under "
    "using apply restatement rewrite targeting addresses distinct mechanism "
    "idea variant paraphrase".split()
)

JACCARD_THRESHOLD = 0.72


def _tokens(text: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return frozenset(w for w in words if w not in STOP and len(w) > 1)


def jaccard(a: str, b: str) -> float:
    sa, sb = _tokens(a), _tokens(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def mechanism_key(idea: dict[str, Any]) -> str:
    mech = str(idea.get("mechanism") or "").strip()
    if mech:
        return f"mech:{mech}"
    toks = sorted(_tokens(str(idea.get("text") or "")))
    return "tok:" + hashlib.sha256("|".join(toks).encode("utf-8")).hexdigest()[:16]


def identity_fingerprint(name: str, cluster_keys: Iterable[str]) -> str:
    blob = name + "\n" + "\n".join(sorted(cluster_keys))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cluster(ledger: list[dict[str, Any]], identity: str) -> list[list[dict[str, Any]]]:
    if identity == IDENTITY_RAW:
        return [[idea] for idea in ledger]
    if identity != IDENTITY_CANONICAL:
        raise ValueError(f"unknown identity {identity}")
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for idea in ledger:
        buckets[mechanism_key(idea)].append(idea)
    return [buckets[k] for k in sorted(buckets)]


def unique_ideas(ledger: list[dict[str, Any]], identity: str) -> dict[str, Any]:
    clusters = cluster(ledger, identity)
    corroboration = []
    if identity == IDENTITY_CANONICAL and len(ledger) >= 2:
        # Record Jaccard as the second, mechanically different signal.
        # It does not override mechanism identity (full-rewrite class).
        by_mech: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for idea in ledger:
            by_mech[mechanism_key(idea)].append(idea)
        paraphrase_high = 0
        rewrite_low = 0
        cross_mech_high = 0
        for key, group in by_mech.items():
            if len(group) < 2:
                continue
            j = jaccard(group[0].get("text") or "", group[1].get("text") or "")
            if j >= JACCARD_THRESHOLD:
                paraphrase_high += 1
            else:
                rewrite_low += 1
        keys = list(by_mech)
        if len(keys) >= 2:
            a, b = by_mech[keys[0]][0], by_mech[keys[1]][0]
            if jaccard(a.get("text") or "", b.get("text") or "") >= JACCARD_THRESHOLD:
                cross_mech_high = 1
        corroboration = [
            {
                "signal": "token-jaccard",
                "threshold": JACCARD_THRESHOLD,
                "same_mech_paraphrase_pairs_high": paraphrase_high,
                "same_mech_rewrite_pairs_low": rewrite_low,
                "distinct_mech_jaccard_high": cross_mech_high,
                "note": (
                    "Jaccard corroborates rename/paraphrase. Full rewrites of the "
                    "same mechanism are merged by mechanism key even when Jaccard "
                    "is low. Distinct mechanisms never merge, even if Jaccard is high."
                ),
            }
        ]
    keys = [mechanism_key(c[0]) if identity == IDENTITY_CANONICAL else f"raw:{i}"
            for i, c in enumerate(clusters)]
    return {
        "identity": identity,
        "count": len(clusters),
        "n_raw": len(ledger),
        "identity_sha256": identity_fingerprint(identity, keys),
        "corroboration": corroboration,
        "clusters": clusters,
    }


def _field_set(cluster_rows: list[dict[str, Any]], field: str, gamed: bool) -> set[str]:
    out: set[str] = set()
    key = f"gamed_{field}" if gamed and any(f"gamed_{field}" in r for r in cluster_rows) else field
    for row in cluster_rows:
        val = row.get(key, row.get(field))
        if val is None:
            continue
        if isinstance(val, list):
            out.update(str(x) for x in val)
        else:
            out.add(str(val))
    return out


def completeness_score(
    ledger: list[dict[str, Any]],
    required: dict[str, list[str]],
    identity: str,
    *,
    gamed_fields: bool = False,
) -> dict[str, Any]:
    clustered = cluster(ledger, identity)
    subq: set[str] = set()
    cats: set[str] = set()
    evid: set[str] = set()
    for rows in clustered:
        subq |= _field_set(rows, "subquestions", gamed_fields)
        cats |= _field_set(rows, "category", gamed_fields)
        evid |= _field_set(rows, "evidence_class", gamed_fields)
    def ratio(got: set[str], need: list[str]) -> float:
        if not need:
            return 1.0
        return len(got & set(need)) / len(need)
    parts = {
        "subquestions": ratio(subq, required["subquestions"]),
        "categories": ratio(cats, required["categories"]),
        "evidence_classes": ratio(evid, required["evidence_classes"]),
    }
    score = min(parts.values())
    keys = [mechanism_key(c[0]) if identity == IDENTITY_CANONICAL else f"raw:{i}"
            for i, c in enumerate(clustered)]
    return {
        "identity": identity,
        "score": round(score, 6),
        "parts": {k: round(v, 6) for k, v in parts.items()},
        "n_clusters": len(clustered),
        "identity_sha256": identity_fingerprint(identity, keys),
        "gamed_fields": gamed_fields,
        "undefined_component_without_this_bind": "coverage_domain_identity",
    }
