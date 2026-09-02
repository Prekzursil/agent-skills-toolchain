#!/usr/bin/env python3
"""Overclaim guard for the CNF-0117 permission report."""
from __future__ import annotations

LOUD = {"loud-failure", "degraded-artifact"}
SENTINEL_PREFIX = "SUCCESS:CNF-0117"
_DOMAIN_KEYS = (
    "denials",
    "control",
    "credential_safety",
    "silent_degradation_probe",
    "all_denials_loud_or_degraded",
    "inventory",
)


def payload(doc: dict) -> dict:
    """Domain fields live under report for permission-report additionalProperties=false."""
    report = doc.get("report")
    if not isinstance(report, dict):
        return doc
    if "denials" not in report and report.get("kind") != "permission-report":
        return doc
    merged = dict(doc)
    for key in _DOMAIN_KEYS:
        if key in report:
            merged[key] = report[key]
    return merged


def denials_of(doc: dict) -> list:
    body = payload(doc)
    rows = body.get("denials")
    return rows if isinstance(rows, list) else []


def check(doc: dict) -> tuple[bool, str]:
    body = payload(doc)
    if doc.get("unit_id") != "CNF-0117":
        return False, "unit_id"
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return False, f"self-declared:{doc.get('state')}"
    if SENTINEL_PREFIX not in str(doc.get("sentinel") or ""):
        return False, "sentinel"
    if body.get("all_denials_loud_or_degraded") is not True:
        return False, "all_denials_loud_or_degraded"
    denials = denials_of(doc)
    if len(denials) < 3:
        return False, "denials-short"
    for row in denials:
        cls = row.get("classification")
        if cls not in LOUD:
            return False, f"denial-{row.get('dependency_id')}:{cls}"
        if cls == "degraded-artifact" and row.get("artifact_marked_degraded") is not True:
            return False, f"unmarked-degraded-artifact:{row.get('dependency_id')}"
        if cls == "loud-failure" and row.get("names_missing_capability") is not True:
            return False, f"unnamed-loud-failure:{row.get('dependency_id')}"
        if row.get("kind") == "credential" and row.get("deny_method") != "unset-variable-in-subprocess":
            return False, f"credential-deny-method:{row.get('dependency_id')}"
    ctrl = body.get("control") or {}
    if not (
        ctrl.get("ran") is True
        and ctrl.get("success") is True
        and ctrl.get("artifact_degraded") is False
        and ctrl.get("exit_code") == 0
    ):
        return False, "control"
    safety = body.get("credential_safety") or {}
    if safety.get("no_real_credential_modified") is not True:
        return False, "credential-modified"
    if safety.get("credential_denials_used_unset_variable") is not True:
        return False, "credential-not-unset"
    if safety.get("no_credential_value_in_artifact") is not True:
        return False, "credential-leaked"
    probe = body.get("silent_degradation_probe") or {}
    if probe.get("fired_on_bad_state") is not True:
        return False, "mutant-detector-did-not-fire"
    if probe.get("silent_on_good_state") is not True:
        return False, "good-consumer-classified-silent"
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in ("T1-degraded-in-artifact", "T2-credential-unset", "T3-granted-control"):
        if tests.get(tid, {}).get("result") != "PASS":
            return False, f"test-{tid}"
    return True, "ok"
