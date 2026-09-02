#!/usr/bin/env python3
"""Frozen dual-confirmer subsample for CNF-0134.

Stand-in for the missing CNF-0137 sampling frame and CNF-0133 calibration
corpus: claim ids are drawn from WORK-UNIT-CATALOG.json; dual-vendor verdicts
are synthetic under the protocol frozen in threshold_prereg.json.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

sys.path.insert(0, str(HERE))
import kappa as K  # noqa: E402

PREFIX_RE = re.compile(r"^([A-Z]+)-")
CONF_A = "anthropic"
CONF_B = "openai"


def catalog_sha256() -> str | None:
    if not CATALOG.is_file():
        return None
    digest, _ = K.sha256_file(CATALOG)
    return digest


def _prefixes(units: list[dict]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {}
    for u in units:
        uid = str(u.get("id") or "")
        m = PREFIX_RE.match(uid)
        if not m:
            continue
        buckets.setdefault(m.group(1), []).append(uid)
    for p in buckets:
        buckets[p] = sorted(set(buckets[p]))
    return buckets


def hamilton(counts: dict[str, int], n: int, min_each: int = 1) -> dict[str, int]:
    prefixes = sorted(counts)
    k = len(prefixes)
    if k == 0:
        raise ValueError("no prefixes")
    if min_each * k > n:
        min_each = 0
    remaining = n - min_each * k
    total = sum(counts[p] for p in prefixes)
    if total <= 0:
        raise ValueError("empty counts")
    quotas = {p: remaining * counts[p] / total for p in prefixes}
    floors = {p: int(quotas[p]) for p in prefixes}
    leftover = remaining - sum(floors.values())
    order = sorted(prefixes, key=lambda p: (-(quotas[p] - floors[p]), p))
    alloc = {p: min_each + floors[p] for p in prefixes}
    for i in range(leftover):
        alloc[order[i]] += 1
    # Cap at available ids.
    overflow = 0
    for p in prefixes:
        if alloc[p] > counts[p]:
            overflow += alloc[p] - counts[p]
            alloc[p] = counts[p]
    if overflow:
        donors = sorted(
            prefixes,
            key=lambda p: (-(counts[p] - alloc[p]), p),
        )
        for p in donors:
            room = counts[p] - alloc[p]
            take = min(room, overflow)
            alloc[p] += take
            overflow -= take
            if overflow == 0:
                break
    if sum(alloc.values()) != n:
        raise ValueError(f"allocation sum {sum(alloc.values())} != {n}")
    return alloc


def _h_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)


def assign_verdicts(claim_id: str, seed: int, labels: list[str]) -> tuple[str, str, bool]:
    a = labels[_h_int(f"{seed}|{claim_id}|A") % len(labels)]
    disagree = _h_int(f"{seed}|{claim_id}|DISAGREE") % 5 == 0
    if disagree:
        b = labels[(labels.index(a) + 1) % len(labels)]
    else:
        b = a
    return a, b, disagree


def draw(prereg: dict | None = None) -> dict:
    doc = prereg if prereg is not None else K.load_prereg()
    labels = K.labels_from_prereg(doc)
    n = int(doc["n_subsample"])
    seed = int(doc["frame_seed"])
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = [u for u in (catalog.get("work_units") or []) if isinstance(u, dict)]
    buckets = _prefixes(units)
    counts = {p: len(ids) for p, ids in buckets.items()}
    alloc = hamilton(counts, n, min_each=1)
    rng = random.Random(seed)
    sampled: list[str] = []
    strata_rows = []
    for prefix in sorted(alloc):
        ids = list(buckets[prefix])
        rng.shuffle(ids)
        take = ids[: alloc[prefix]]
        sampled.extend(take)
        strata_rows.append(
            {
                "available": counts[prefix],
                "prefix": prefix,
                "sampled": len(take),
            }
        )
    if len(sampled) != n:
        raise ValueError(f"sampled {len(sampled)} != {n}")
    if len(set(sampled)) != n:
        raise ValueError("duplicate claim ids in subsample")
    pairs = []
    for cid in sampled:
        a, b, disagree = assign_verdicts(cid, seed, labels)
        pairs.append(
            {
                "claim_id": cid,
                "disagree": disagree,
                CONF_A: a,
                CONF_B: b,
            }
        )
    rater_a = [p[CONF_A] for p in pairs]
    rater_b = [p[CONF_B] for p in pairs]
    stat = K.cohen_kappa(rater_a, rater_b, labels)
    partition_ok = sum(r["sampled"] for r in strata_rows) == n
    intersections_empty = True
    seen: set[str] = set()
    for prefix in sorted(alloc):
        chunk = {p["claim_id"] for p in pairs if p["claim_id"].startswith(prefix + "-")}
        if seen & chunk:
            intersections_empty = False
        seen |= chunk
    return {
        "allocation": alloc,
        "catalog_sha256": catalog_sha256(),
        "labels": labels,
        "n": n,
        "pairs": pairs,
        "partition": {
            "intersections_empty": intersections_empty,
            "ok": partition_ok and intersections_empty and len(seen) == n,
            "sum_stratum_counts": sum(r["sampled"] for r in strata_rows),
        },
        "rater_a": rater_a,
        "rater_b": rater_b,
        "seed": seed,
        "stat": stat,
        "strata": strata_rows,
        "synthetic": True,
        "vendors": [CONF_A, CONF_B],
    }
