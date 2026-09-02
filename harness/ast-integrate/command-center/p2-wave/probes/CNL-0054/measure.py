#!/usr/bin/env python3
"""Category coverage + diversity as ONE measurement (CNL-0054).

Joint score = Pielou evenness of occupancy over the DECLARED taxonomy T,
including unoccupied categories. Coverage C = support/|T| is diagnostic
only: token-coverage yields C=1.0 while the joint score stays low.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TAXONOMY_PATH = HERE / "taxonomy.json"


def load_taxonomy() -> dict[str, Any]:
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def category_ids(tax: dict[str, Any] | None = None) -> list[str]:
    doc = tax if tax is not None else load_taxonomy()
    ids = [row["id"] for row in doc["categories"]]
    if len(ids) != len(set(ids)):
        raise ValueError("taxonomy ids are not unique")
    if not doc.get("closed") is True:
        raise ValueError("taxonomy must be closed")
    return ids


def threshold(tax: dict[str, Any] | None = None) -> float:
    doc = tax if tax is not None else load_taxonomy()
    return float(doc["joint_score"]["threshold_reject_below"])


def occupancy(
    ideas: list[dict[str, Any]], ids: list[str]
) -> tuple[dict[str, int], list[str]]:
    """Count via Counter on the category field (author path)."""
    counts = {c: 0 for c in ids}
    invalid: list[str] = []
    seen = Counter(str(idea.get("category") or "") for idea in ideas)
    for cat, n in seen.items():
        if cat in counts:
            counts[cat] = n
        else:
            invalid.extend(
                str(idea.get("id") or cat)
                for idea in ideas
                if str(idea.get("category") or "") == cat
            )
    return counts, invalid


def coverage(counts: dict[str, int], ids: list[str]) -> float:
    support = sum(1 for c in ids if counts.get(c, 0) >= 1)
    return support / float(len(ids))


def pielou(counts: dict[str, int], ids: list[str]) -> float:
    """Shannon evenness over the full declared T (zeros included)."""
    n = sum(int(counts.get(c, 0)) for c in ids)
    if n <= 0:
        return 0.0
    h = 0.0
    for c in ids:
        k = int(counts.get(c, 0))
        if k <= 0:
            continue
        p = k / n
        h -= p * math.log(p)
    return h / math.log(len(ids))


def score(ideas: list[dict[str, Any]], tax: dict[str, Any] | None = None) -> dict[str, Any]:
    doc = tax if tax is not None else load_taxonomy()
    ids = category_ids(doc)
    thr = threshold(doc)
    counts, invalid = occupancy(ideas, ids)
    n = sum(counts.values())
    if invalid:
        return {
            "valid": False,
            "n": n,
            "invalid_ids": invalid,
            "occupancy": counts,
            "coverage": None,
            "joint": None,
            "fires": True,
            "reason": "out-of-taxonomy-label",
            "threshold": thr,
        }
    cov = coverage(counts, ids)
    joint = pielou(counts, ids)
    fires = joint < thr
    return {
        "valid": True,
        "n": n,
        "invalid_ids": [],
        "occupancy": counts,
        "coverage": cov,
        "joint": joint,
        "fires": fires,
        "reason": "below-threshold" if fires else "at-or-above-threshold",
        "threshold": thr,
    }


def check_fires(ideas: list[dict[str, Any]], tax: dict[str, Any] | None = None) -> bool:
    """True = insufficiency detector FIRES (the state it is meant to reject)."""
    return bool(score(ideas, tax)["fires"])
