#!/usr/bin/env python3
"""Invariants for a CNF-0066 detector-control artifact."""
from __future__ import annotations

from typing import Any


def domain_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Receipt-core domain fields live under report; older docs used top-level."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    view = dict(doc)
    for key in (
        "kind",
        "records",
        "absences",
        "summary",
        "controls",
        "recall",
        "re_ran_detector_control",
    ):
        if key in report:
            view[key] = report[key]
    reviewer = dict(view.get("reviewer") or {})
    if report.get("re_ran_detector_control") is True:
        reviewer["re_ran_detector_control"] = True
    view["reviewer"] = reviewer
    return view


def check_document(doc: dict[str, Any]) -> list[str]:
    errs: list[str] = []
    view = domain_view(doc)
    if view.get("kind") != "detector-control":
        errs.append("kind is not detector-control")
    if view.get("unit_id") != "CNF-0066":
        errs.append("unit_id is not CNF-0066")
    if str(view.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        errs.append(f"self-declared {view.get('state')}")

    records = view.get("records") or []
    if not isinstance(records, list) or len(records) < 8:
        errs.append("records missing or too few")
        return errs

    confirmed = [r for r in records if r.get("classification") == "CONFIRMED_ABSENCE"]
    absences = view.get("absences") or []
    abs_ids = {a.get("id") for a in absences if isinstance(a, dict)}
    conf_ids = {r.get("id") for r in confirmed}
    if abs_ids != conf_ids:
        errs.append(f"absences ids {sorted(abs_ids)} != confirmed {sorted(conf_ids)}")
    for row in absences:
        if row.get("control_found_known_present") is not True:
            errs.append(f"absence {row.get('id')} missing successful control")
        if not row.get("control_id"):
            errs.append(f"absence {row.get('id')} missing control_id")

    for rec in records:
        rid = rec.get("id")
        cls = rec.get("classification")
        if cls == "CONFIRMED_ABSENCE":
            if rec.get("control_found_known_present") is not True:
                errs.append(f"{rid} CONFIRMED_ABSENCE without control hit")
            if rec.get("tools_disagree") is True:
                errs.append(f"{rid} trusted absence but tools disagree")
        if cls == "NOT-CHECKED":
            if rec.get("control_found_known_present") is True:
                errs.append(f"{rid} NOT-CHECKED but control reported found")
            if rec.get("control_id") is not None:
                errs.append(f"{rid} NOT-CHECKED must not carry a control_id")
        if cls != "NOT-CHECKED" and rec.get("fingerprints_differ") is not True:
            errs.append(f"{rid} tools are not mechanically different")
        if cls in {"CONFIRMED_ABSENCE", "FALSE_ABSENCE", "RECALL_NOT_DETECTION"}:
            if rec.get("recall_ran") is not True:
                errs.append(f"{rid} declared without recall")

    classes = {r.get("classification") for r in records}
    for needed in (
        "CONFIRMED_ABSENCE",
        "FALSE_ABSENCE",
        "DETECTOR_FAILURE",
        "NOT-CHECKED",
        "RECALL_NOT_DETECTION",
    ):
        if needed not in classes:
            errs.append(f"missing classification {needed}")

    summary = view.get("summary") or {}
    if int(summary.get("not_checked") or 0) < 1:
        errs.append("summary.not_checked < 1")
    if int(summary.get("detector_failure") or 0) < 1:
        errs.append("summary.detector_failure < 1")
    if int(summary.get("confirmed_absence") or 0) != len(confirmed):
        errs.append("summary.confirmed_absence mismatch")

    tests = {t.get("id"): t for t in (view.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "T-absence-without-control-is-not-checked",
        "T-two-mechanically-different-tools",
        "T-recall-before-unbuilt",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            errs.append(f"test {tid} not PASS")

    reviewer = view.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        errs.append("reviewer not independent")
    if reviewer.get("re_ran_detector_control") is not True:
        errs.append("reviewer did not re-run detector control")
    return errs
