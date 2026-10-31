#!/usr/bin/env python3
"""IMP-0371 probe harness.

Drives the LIVE tools/selfimprove/intake.py through the four catalog
scenarios and returns the stage-gate audit structure recorded in the
unit receipt. Read-only over the module: never mutates it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
for p in (str(REPO / "tools"),):
    if p not in sys.path:
        sys.path.insert(0, p)

from selfimprove.intake import GateBlocked, Intake, candidate_schema_errors  # noqa: E402

FIXTURE = HERE / "fixtures" / "flaky-3-of-10.json"


def load_flaky_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _audit_row(cand: dict) -> dict:
    return {
        "candidate_id": cand["candidate_id"],
        "classification": cand["classification"],
        "repeat_count": cand["repeat_count"],
        "baseline_accepted": cand["baseline_accepted"],
        "stage": cand["stage"],
    }


def run_gated_confirmed_run() -> dict:
    """Flaky 3/10 + confirmed 10/10 under the gate: flaky blocked, confirmed advances."""
    fx = load_flaky_fixture()
    intake = Intake(enforce_reproduction_gate=True)
    intake.observe(fx["candidate_id"], "failure", "known flaky control", fx["command"])
    intake.observe("cand-confirmed-10-of-10", "failure", "deterministic control", "repro")
    intake.reproduce(fx["candidate_id"], fx["trials"], fx["attempts"], fx["command"])
    intake.reproduce(
        "cand-confirmed-10-of-10",
        [True] * 10,
        10,
        "python -B tools/selfimprove/tests/run_deterministic.py",
    )
    flaky_blocked_reason = None
    confirmed_blocked_reason = None
    try:
        intake.advance_to_implementation(fx["candidate_id"])
        flaky_blocked_reason = "NOT-BLOCKED"
    except GateBlocked as exc:
        flaky_blocked_reason = exc.reason
    try:
        intake.advance_to_implementation("cand-confirmed-10-of-10")
        confirmed_advanced = (
            intake.snapshot("cand-confirmed-10-of-10")["stage"] == "implementation"
        )
    except GateBlocked as exc:
        confirmed_advanced = False
        confirmed_blocked_reason = exc.reason
    audit = intake.stage_gate_audit()
    return {
        "candidates_inspected": 2,
        "allowed_advances_to_implementation": 1 if confirmed_advanced else 0,
        "advanced_without_confirmed_receipt": audit["advanced_without_confirmed_receipt"],
        "gate_enforced": audit["enforce"],
        "held": bool(audit["held"]) and flaky_blocked_reason == "flaky-not-accepted-as-baseline",
        "flaky_blocked_reason": flaky_blocked_reason,
        "confirmed_blocked_reason": confirmed_blocked_reason,
        "repeat_counts": [
            _audit_row(intake.snapshot(fx["candidate_id"])),
            _audit_row(intake.snapshot("cand-confirmed-10-of-10")),
        ],
    }


def run_gated_unreproduced_run() -> dict:
    """Unreproduced 0/10 under the gate: must NOT advance; audit holds."""
    intake = Intake(enforce_reproduction_gate=True)
    intake.observe("cand-unreproduced", "failure", "never reproduced", "repro")
    intake.reproduce("cand-unreproduced", [False] * 10, 10, "repro-cmd")
    blocked_reason = None
    try:
        intake.advance_to_implementation("cand-unreproduced")
        blocked_reason = "NOT-BLOCKED"
    except GateBlocked as exc:
        blocked_reason = exc.reason
    audit = intake.stage_gate_audit()
    return {
        "candidates_inspected": 1,
        "allowed_advances_to_implementation": 0,
        "advanced_without_confirmed_receipt": audit["advanced_without_confirmed_receipt"],
        "gate_enforced": audit["enforce"],
        "held": bool(audit["held"]),
        "blocked_reason": blocked_reason,
        "repeat_counts": [_audit_row(intake.snapshot("cand-unreproduced"))],
    }


def run_ungated_negative_control() -> dict:
    """Gate REMOVED: the same unreproduced candidate MUST advance (control fires)."""
    intake = Intake(enforce_reproduction_gate=False)
    intake.observe("cand-unreproduced-ungated", "failure", "never reproduced", "repro")
    intake.reproduce("cand-unreproduced-ungated", [False] * 10, 10, "repro-cmd")
    intake.advance_to_implementation("cand-unreproduced-ungated")
    advanced = intake.snapshot("cand-unreproduced-ungated")["stage"] == "implementation"
    audit = intake.stage_gate_audit()
    return {
        "candidates_inspected": 1,
        "allowed_advances_to_implementation": 1 if advanced else 0,
        "advanced_without_confirmed_receipt": audit["advanced_without_confirmed_receipt"],
        "gate_enforced": audit["enforce"],
        "held": bool(audit["held"]),
        "repeat_counts": [_audit_row(intake.snapshot("cand-unreproduced-ungated"))],
    }


def run_spoofed_fields_run() -> dict:
    """Spoofed confirmed fields without an issued receipt must NOT bypass the register."""
    intake = Intake(enforce_reproduction_gate=True)
    intake.observe("cand-spoofed", "failure", "field spoof, no receipt", "repro")
    cand = intake.candidates["cand-spoofed"]
    cand["classification"] = "confirmed"
    cand["baseline_accepted"] = True
    spoof_blocked_reason = None
    try:
        intake.advance_to_implementation("cand-spoofed")
        spoof_blocked_reason = "NOT-BLOCKED"
    except GateBlocked as exc:
        spoof_blocked_reason = exc.reason
    # Variant: genuinely reproduced flaky, then fields edited to confirmed.
    intake.observe("cand-flaky-spoofed", "failure", "flaky then spoofed", "repro")
    trials = [True] + [False] * 9
    intake.reproduce("cand-flaky-spoofed", trials, 10, "repro-cmd")
    cand2 = intake.candidates["cand-flaky-spoofed"]
    cand2["classification"] = "confirmed"
    cand2["baseline_accepted"] = True
    flaky_spoof_blocked = None
    try:
        intake.advance_to_implementation("cand-flaky-spoofed")
        flaky_spoof_blocked = "NOT-BLOCKED"
    except GateBlocked as exc:
        flaky_spoof_blocked = exc.reason
    audit = intake.stage_gate_audit()
    return {
        "candidates_inspected": 2,
        "advanced_without_confirmed_receipt": audit["advanced_without_confirmed_receipt"],
        "gate_enforced": audit["enforce"],
        "held": bool(audit["held"]),
        "spoof_blocked_reason": spoof_blocked_reason,
        "flaky_spoof_blocked_reason": flaky_spoof_blocked,
    }


def full_audit() -> dict:
    return {
        "gated_confirmed_run": run_gated_confirmed_run(),
        "gated_unreproduced_run": run_gated_unreproduced_run(),
        "ungated_negative_control": run_ungated_negative_control(),
        "spoofed_fields_run": run_spoofed_fields_run(),
    }


def schema_errors_probe() -> dict:
    """candidate_schema_errors: missing required fields + bad kind detected."""
    base = {
        "schema_version": 1,
        "candidate_id": "cand-x",
        "kind": "failure",
        "observation": {"summary": "s", "source": "src"},
        "stage": "observed",
        "repeat_count": {"n": 0, "m": 0, "observed": "0/0"},
        "classification": "observed",
        "baseline_accepted": False,
    }
    clean = candidate_schema_errors(dict(base))
    stripped = candidate_schema_errors(
        {k: v for k, v in base.items() if k not in ("candidate_id", "stage", "classification")}
    )
    bad_kind = candidate_schema_errors({**base, "kind": "vibe"})
    return {
        "clean_ok": clean == [],
        "stripped_errors": sorted(stripped),
        "bad_kind_detected": "bad-kind" in bad_kind,
    }
