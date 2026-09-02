"""Refuse a SUCCESS audit that launders empty denominators or silent drops."""
from __future__ import annotations

from typing import Any


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        isinstance(report.get("survival"), dict) or isinstance(report.get("dropped"), list)
    ):
        return report
    return doc


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{state}"
    payload = domain(doc)
    survival = payload.get("survival")
    dropped = payload.get("dropped")
    ratios = payload.get("ratios")
    if not isinstance(survival, dict):
        return False, "survival-missing"
    if not isinstance(dropped, list):
        return False, "dropped-missing"
    if not isinstance(ratios, dict):
        return False, "ratios-missing"
    try:
        src = int(survival["source_count"])
        surv = int(survival["surviving_count"])
    except (KeyError, TypeError, ValueError):
        return False, "survival-counts-unreadable"
    dens = survival.get("denominators")
    if not isinstance(dens, dict):
        return False, "denominators-missing"
    if dens.get("source_negatives") != src or dens.get("surviving_negatives") != surv:
        return False, "denominators-disagree-with-counts"
    rate = survival.get("rate")
    if src == 0:
        if rate is not None:
            return False, "empty-source-must-not-publish-numeric-rate"
        if surv != 0:
            return False, "empty-source-nonzero-surviving"
    else:
        if not isinstance(rate, (int, float)):
            return False, "rate-missing-with-nonzero-source"
        expected = surv / src
        if abs(float(rate) - expected) > 1e-9:
            return False, "rate-not-surviving-over-source"
        if surv > src:
            return False, "surviving-exceeds-source"
    if len(dropped) != src - surv:
        return False, "dropped-len-not-source-minus-surviving"
    for i, row in enumerate(dropped):
        if not isinstance(row, dict):
            return False, f"dropped[{i}]-not-object"
        if not str(row.get("id") or "").strip():
            return False, f"dropped[{i}]-no-id"
        if len(str(row.get("reason") or "").strip()) < 8:
            return False, f"dropped[{i}]-reason-unstated"
    if ratios.get("unit") != "record":
        return False, "ratio-unit-not-record"
    if ratios.get("byte_weighted_refused") is not True:
        return False, "byte-weighted-not-refused"
    live = survival.get("live")
    if not isinstance(live, dict):
        return False, "live-survival-missing"
    if int(live.get("source_count") or 0) == 0 and live.get("rate") is not None:
        return False, "live-empty-numeric-rate"
    fixture = survival.get("fixture")
    if not isinstance(fixture, dict):
        return False, "fixture-survival-missing"
    if int(fixture.get("source_count") or 0) < 1:
        return False, "fixture-source-empty"
    verdict = str(payload.get("question_verdict") or "")
    if verdict == "CONFIRMED" and dropped:
        return False, "confirmed-despite-drops"
    if src == 0 and verdict == "CONFIRMED":
        return False, "confirmed-over-empty-source"
    return True, "ok"
