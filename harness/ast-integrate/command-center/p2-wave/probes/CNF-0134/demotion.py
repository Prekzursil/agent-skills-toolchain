#!/usr/bin/env python3
"""Demotion rule: sub-threshold kappa turns single-confirmer CONFIRMED into PARTIAL.

Does not fire when two independent confirmers (distinct vendors) already agree.
"""
from __future__ import annotations

import copy
from typing import Any

JUDGMENT = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED"})


def _confirmers(record: dict[str, Any]) -> list[dict[str, Any]]:
    raw = record.get("confirmers") or []
    if not isinstance(raw, list):
        return []
    return [c for c in raw if isinstance(c, dict)]


def independent_confirmers_agree(record: dict[str, Any]) -> bool:
    conf = _confirmers(record)
    if len(conf) < 2:
        return False
    vendors = [str(c.get("vendor") or "") for c in conf]
    if any(v == "" for v in vendors):
        return False
    if len(set(vendors)) < 2:
        return False
    verdicts = [str(c.get("verdict") or "") for c in conf]
    if len(set(verdicts)) != 1:
        return False
    return verdicts[0] in JUDGMENT


def confirmer_count(record: dict[str, Any]) -> int:
    conf = _confirmers(record)
    if conf:
        return len(conf)
    try:
        return int(record.get("confirmer_count"))
    except (TypeError, ValueError):
        return 0


def apply_demotion(record: dict[str, Any], kappa: float, threshold: float) -> dict[str, Any]:
    """Return a deep copy with demotion applied or explicitly not applied."""
    out = copy.deepcopy(record)
    out["kappa_used"] = kappa
    out["threshold_used"] = threshold
    if independent_confirmers_agree(out):
        out["demotion_applied"] = False
        out["demotion_reason"] = "independent-confirmers-agree"
        return out
    n = confirmer_count(out)
    verdict = str(out.get("verdict") or "")
    if kappa < threshold and verdict == "CONFIRMED" and n == 1:
        out["prior_verdict"] = "CONFIRMED"
        out["verdict"] = "PARTIAL"
        out["demotion_applied"] = True
        out["demotion_reason"] = "sub-threshold-kappa-single-confirmer"
        return out
    out["demotion_applied"] = False
    out["demotion_reason"] = None
    return out
