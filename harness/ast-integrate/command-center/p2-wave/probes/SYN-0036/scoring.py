#!/usr/bin/env python3
"""Score producers by refutation survival. Volume is never a score input."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from wilson import wilson_interval

HERE = Path(__file__).resolve().parent
PREREG_PATH = HERE / "prereg.json"
FRAME_PATH = HERE / "fixtures" / "frozen_claims.json"
FORBIDDEN_PREREG = frozenset({
    "weight",
    "weights",
    "survival_rate",
    "point_estimate",
    "producers_scored",
    "computed_weights",
})
VOLUME_KEYS = frozenset({
    "volume_bytes",
    "volume_tokens",
    "bytes",
    "tokens",
    "kilobytes",
    "output_bytes",
    "token_count",
})
SCORE_INPUTS = ("claims_filed", "refuted", "survived", "n")


def load_prereg():
    doc = json.loads(PREREG_PATH.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("prereg.json is not an object")
    hit = sorted(FORBIDDEN_PREREG.intersection(doc))
    if hit:
        raise ValueError("prereg contaminated with computed fields %s" % (hit,))
    if doc.get("recorded_before_any_weight_computation") is not True:
        raise ValueError("prereg missing recorded_before_any_weight_computation")
    if doc.get("volume_not_a_score_input") is not True:
        raise ValueError("prereg must declare volume_not_a_score_input")
    if int(doc["min_n"]) < 2:
        raise ValueError("min_n must be >= 2")
    declared = tuple(doc.get("score_inputs") or ())
    if declared != SCORE_INPUTS:
        raise ValueError("score_inputs %s != %s" % (declared, SCORE_INPUTS))
    return doc


def load_frame():
    return json.loads(FRAME_PATH.read_text(encoding="utf-8"))


def score_from_claims(claims, producers_meta, min_n):
    meta = {p["producer_id"]: p for p in producers_meta}
    counts = {}
    for claim in claims:
        pid = str(claim["producer_id"])
        verdict = str(claim["verdict"])
        if verdict not in {"SURVIVED", "REFUTED"}:
            raise ValueError("unknown verdict %s" % verdict)
        counts.setdefault(pid, Counter())
        counts[pid][verdict] += 1
        counts[pid]["n"] += 1

    rows = []
    for pid in sorted(counts):
        n = int(counts[pid]["n"])
        survived = int(counts[pid]["SURVIVED"])
        refuted = int(counts[pid]["REFUTED"])
        if survived + refuted != n:
            raise ValueError("%s survived+refuted != n" % pid)
        info = meta.get(pid) or {}
        row = {
            "producer_id": pid,
            "role": str(info.get("role") or "unknown"),
            "vendor": str(info.get("vendor") or "unknown"),
            "substrate": str(info.get("substrate") or "unknown"),
            "claims_filed": n,
            "refuted": refuted,
            "survived": survived,
            "n": n,
        }
        if n < min_n:
            row["label"] = "INSUFFICIENT-N"
            row["weight"] = None
            row["survival_rate"] = (survived / n) if n else None
            row["confidence_interval"] = None
        else:
            rate = survived / n
            ci = wilson_interval(survived, n)
            row["label"] = "SCORED"
            row["weight"] = rate
            row["survival_rate"] = rate
            row["confidence_interval"] = ci
        rows.append(row)
    return rows


def score_frame(frame=None, prereg=None):
    prereg = load_prereg() if prereg is None else prereg
    frame = load_frame() if frame is None else frame
    min_n = int(prereg["min_n"])
    claims = list(frame["claims"])
    producers = score_from_claims(claims, list(frame["producers"]), min_n)
    weights = {
        r["producer_id"]: r["weight"] for r in producers if r["label"] == "SCORED"
    }
    return {
        "claims": [
            {
                "claim_id": c["claim_id"],
                "producer_id": c["producer_id"],
                "verdict": c["verdict"],
            }
            for c in claims
        ],
        "findings": list(frame.get("findings") or []),
        "min_n": min_n,
        "n": len(claims),
        "producers": producers,
        "score_inputs": list(SCORE_INPUTS),
        "volume_excluded_from_score": True,
        "weights": weights,
    }


def recompute_weights_from_raw(claims, min_n):
    seen = {}
    for c in claims:
        pid = c["producer_id"]
        seen[pid] = {
            "producer_id": pid,
            "role": "recompute",
            "vendor": "recompute",
            "substrate": "recompute",
        }
    rows = score_from_claims(claims, list(seen.values()), min_n)
    return {r["producer_id"]: r["weight"] for r in rows}
