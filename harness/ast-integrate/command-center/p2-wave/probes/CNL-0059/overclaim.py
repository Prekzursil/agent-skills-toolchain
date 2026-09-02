#!/usr/bin/env python3
"""Artifact overclaim checks for CNL-0059."""
from __future__ import annotations

from typing import Any

import detector as D


def payload(doc: dict) -> dict:
    """Domain fields live under report on a receipt envelope."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        "threshold" in report or "false_positive_rate" in report
    ):
        return report
    return doc


def check_overclaim(doc: dict) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-an-object"
    body = payload(doc)
    fp = body.get("false_positive_rate", doc.get("false_positive_rate"))
    if type(fp) not in (int, float) or isinstance(fp, bool):
        return False, "false_positive_rate-not-a-number"
    if not 0.0 <= float(fp) <= 1.0:
        return False, "false_positive_rate-out-of-range"
    thr = body.get("threshold") or {}
    numeric = thr.get("numeric") or {}
    expected = {
        "suspicion_max_round": D.SUSPICION_MAX_ROUND,
        "pairwise_jaccard_min": D.PAIRWISE_JACCARD_MIN,
        "chair_echo_jaccard_min": D.CHAIR_ECHO_JACCARD_MIN,
        "min_brief_chars": D.MIN_BRIEF_CHARS,
    }
    for key, val in expected.items():
        if numeric.get(key) != val:
            return False, f"threshold-numeric-drift:{key}"
    rejected = " ".join(thr.get("rejected_units") or []).lower()
    if "wall-clock" not in rejected and "wall clock" not in rejected:
        return False, "rejected-units-omit-wall-clock"
    unit = str(thr.get("primary_unit") or "").lower()
    if "round" not in unit:
        return False, "primary-unit-not-rounds"
    statuses = {
        str(a.get("id")): str(a.get("status"))
        for a in (body.get("spec_anchors") or [])
        if isinstance(a, dict)
    }
    if "10944" not in statuses or "11336" not in statuses:
        return False, "spec-anchors-missing-10944-or-11336"
    # Threshold is unspecified in spec; a CONFIRMED claim that spec named
    # the number is an overclaim.
    rows = list(body.get("evidence") or []) + list(doc.get("evidence") or [])
    for row in rows:
        if not isinstance(row, dict):
            continue
        claim = str(row.get("claim") or "").lower()
        verdict = str(row.get("verdict") or "")
        if verdict == "CONFIRMED" and "spec named the numeric threshold" in claim:
            return False, "overclaimed-spec-named-threshold"
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return False, f"self-declared:{doc.get('state')}"
    if "SUCCESS:CNL-0059" not in str(doc.get("sentinel") or ""):
        return False, "sentinel-missing"
    return True, "ok"
