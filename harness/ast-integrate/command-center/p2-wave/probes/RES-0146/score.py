#!/usr/bin/env python3
"""Accuracy, coin-flip baseline, Wilson interval, auto-demote decision.

Classifiers are passed in; this module does not choose features.
"""
from __future__ import annotations

import hashlib
import math
from typing import Callable, Iterable


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n <= 0:
        return 0.0, 0.0, 1.0
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    adj = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n)
    lo = max(0.0, (centre - adj) / denom)
    hi = min(1.0, (centre + adj) / denom)
    return p, lo, hi


def coin_flip_label(doc_id: str) -> str:
    """Deterministic fair coin from sha256(doc_id). Not a live RNG."""
    n = int(hashlib.sha256(doc_id.encode("utf-8")).hexdigest(), 16)
    return "mill" if (n % 2 == 0) else "practitioner"


def score_predictions(
    rows: Iterable[dict],
    predict: Callable[[str], str],
) -> dict:
    items = list(rows)
    n = len(items)
    correct = 0
    tp = fp = tn = fn = 0
    per = []
    for row in items:
        pred = predict(row["text"])
        gold = row["label"]
        ok = pred == gold
        correct += int(ok)
        if gold == "mill" and pred == "mill":
            tp += 1
        elif gold == "practitioner" and pred == "mill":
            fp += 1
        elif gold == "practitioner" and pred == "practitioner":
            tn += 1
        else:
            fn += 1
        per.append({"id": row["id"], "gold": gold, "pred": pred, "ok": ok})
    acc, lo, hi = wilson_interval(correct, n)
    return {
        "n": n,
        "correct": correct,
        "accuracy": acc,
        "wilson95_lo": lo,
        "wilson95_hi": hi,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "per_doc": per,
    }


def score_coin_flip(rows: Iterable[dict]) -> dict:
    items = list(rows)
    n = len(items)
    correct = 0
    per = []
    for row in items:
        pred = coin_flip_label(row["id"])
        gold = row["label"]
        ok = pred == gold
        correct += int(ok)
        per.append({"id": row["id"], "gold": gold, "pred": pred, "ok": ok})
    acc, lo, hi = wilson_interval(correct, n)
    n_mill = sum(1 for r in items if r["label"] == "mill")
    majority = max(n_mill, n - n_mill) / n if n else 0.0
    return {
        "n": n,
        "correct": correct,
        "accuracy": acc,
        "wilson95_lo": lo,
        "wilson95_hi": hi,
        "expected_fair_p": 0.5,
        "majority_class_accuracy": majority,
        "per_doc": per,
        "derivation": "sha256(doc_id) mod 2 mapped to {mill,practitioner}",
    }


def decide(
    lexical: dict,
    stats: dict,
    margin: float,
    wilson_floor: float,
) -> dict:
    baseline = 0.5
    point_bar = baseline + margin

    def beats(block: dict) -> dict:
        point = block["accuracy"] >= point_bar
        wilson = block["wilson95_lo"] >= wilson_floor
        return {
            "point_estimate_beats_margin": point,
            "wilson_lo_clears_floor": wilson,
            "beats_for_auto_demote": point and wilson,
        }

    lex_d = beats(lexical)
    st_d = beats(stats)
    both = lex_d["beats_for_auto_demote"] and st_d["beats_for_auto_demote"]
    if both:
        outcome = "AUTO-DEMOTE-SUPPORTED-ON-THIS-SET"
        answer_kind = "DECIDABLE"
    else:
        outcome = "NOT-DECIDABLE"
        answer_kind = "NOT-DECIDABLE"
    return {
        "baseline_expected": baseline,
        "stated_margin": margin,
        "point_bar": point_bar,
        "wilson_floor": wilson_floor,
        "lexical": lex_d,
        "stats": st_d,
        "both_classifiers_clear": both,
        "outcome": outcome,
        "answer_kind": answer_kind,
        "rule": (
            "Auto-demotion is supported only if BOTH independent classifiers "
            "have accuracy >= 0.5+margin AND Wilson 95% lower bound >= 0.5+margin. "
            "Otherwise the honest deliverable is NOT-DECIDABLE."
        ),
    }
