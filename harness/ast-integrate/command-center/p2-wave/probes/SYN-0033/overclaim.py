"""Refuse a clean-bill contradiction report with no denominator or missing probes."""
from __future__ import annotations

from typing import Any

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Contradiction payload lives under report once receipt_core is pinned."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        "examined_pair_count" in report or "contradictions" in report
    ):
        return report
    return doc


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "doc-not-object"
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return False, f"self-declared:{state}"
    payload = domain(doc)
    verdict = str(payload.get("verdict") or "")
    try:
        examined = int(payload["examined_pair_count"])
    except (KeyError, TypeError, ValueError):
        return False, "examined_pair_count-absent"
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        return False, "counts-missing"
    try:
        if int(counts["examined_pair_count"]) != examined:
            return False, "examined-count-drift"
        claims_n = int(counts["claims_loaded"])
        open_n = int(counts["open_count"])
        settled_n = int(counts["settled_count"])
    except (KeyError, TypeError, ValueError):
        return False, "required-counts-missing"
    rows = payload.get("contradictions")
    if not isinstance(rows, list):
        return False, "contradictions-missing"
    if len(rows) != open_n + settled_n:
        return False, "contradiction-count-drift"
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            return False, f"contradictions[{i}]-not-object"
        status = str(row.get("status") or "")
        probe = str(row.get("settling_probe") or "").strip()
        left = row.get("left") if isinstance(row.get("left"), dict) else {}
        right = row.get("right") if isinstance(row.get("right"), dict) else {}
        if not str(left.get("text") or "").strip() or not str(right.get("text") or "").strip():
            return False, f"contradictions[{i}]-missing-verbatim"
        if left.get("anchor") in (None, "") or right.get("anchor") in (None, ""):
            return False, f"contradictions[{i}]-missing-anchor"
        if left.get("phase") is None or right.get("phase") is None:
            return False, f"contradictions[{i}]-missing-phase"
        if left.get("phase") == right.get("phase"):
            return False, f"contradictions[{i}]-intra-phase-double-report"
        if "already_adjudicated" not in row:
            return False, f"contradictions[{i}]-adjudicated-flag-absent"
        if status == "OPEN" and len(probe) < 8:
            return False, f"contradictions[{i}]-open-without-settling-probe"
        if status == "SETTLED" and row.get("already_adjudicated") is not True:
            return False, f"contradictions[{i}]-SETTLED-not-flagged-adjudicated"
        if status == "OPEN" and row.get("already_adjudicated") is True:
            return False, f"contradictions[{i}]-OPEN-but-already-adjudicated"
    if payload.get("open_contradictions_all_named_settling_probe") is not True:
        return False, "open-probe-flag-false"
    inputs = payload.get("inputs_on_disk")
    if not isinstance(inputs, dict):
        return False, "inputs_on_disk-missing"
    registry = inputs.get("claim_registry") if isinstance(inputs.get("claim_registry"), dict) else {}
    registry_present = registry.get("present") is True
    if not registry_present:
        if verdict == "CONFIRMED":
            return False, "CONFIRMED-registry-absent"
        if examined != 0:
            return False, "examined-nonzero-without-registry"
        if claims_n != 0:
            return False, "claims-nonzero-without-registry"
    if examined == 0 and verdict == "CONFIRMED":
        return False, "CONFIRMED-zero-pairs-no-denominator-search"
    answer = str(payload.get("answer") or "").lower()
    if examined == 0 and "no contradictions" in answer and "denominator" not in answer:
        return False, "zero-without-denominator-prose"
    return True, f"verdict={verdict} examined={examined} open={open_n} settled={settled_n}"
