#!/usr/bin/env python3
"""Shared live checks for IMP-0371 named probes.

These functions talk to tools/selfimprove/intake.py. They do not write the
catalog receipt, so they can re-run after delivery without changing hashes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from selfimprove.intake import (  # noqa: E402
    GateBlocked,
    Intake,
    candidate_schema_errors,
    classify_repeat,
    scripted_trials,
)

INTAKE_REL = "tools/selfimprove/intake.py"
SCHEMA_REL = "tools/selfimprove/candidate.schema.json"
FLAKY_3_OF_10 = [True, True, True] + [False] * 7
CONFIRMED_10_OF_10 = [True] * 10
UNREPRODUCED_0_OF_10 = [False] * 10


def _load_schema() -> dict[str, Any]:
    return json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))


def schema_and_stage_gates() -> dict[str, Any]:
    """Catalog test: unit candidate schema and stage gates."""
    intake_path = REPO / INTAKE_REL
    schema_path = REPO / SCHEMA_REL
    if not intake_path.is_file() or intake_path.stat().st_size < 200:
        return {"pass": False, "reason": "intake.py missing"}
    if not schema_path.is_file():
        return {"pass": False, "reason": "candidate.schema.json missing"}

    schema = _load_schema()
    required = set(schema.get("required") or [])
    want_required = {
        "schema_version",
        "candidate_id",
        "kind",
        "observation",
        "stage",
        "repeat_count",
        "classification",
        "baseline_accepted",
    }
    if not want_required.issubset(required):
        return {
            "pass": False,
            "reason": f"schema required fields {sorted(required)} missing {sorted(want_required - required)}",
        }

    engine = Intake(enforce_reproduction_gate=True)
    engine.observe(
        candidate_id="cand-schema-ok",
        kind="failure",
        summary="timeout on probe X",
        source="fixture",
    )
    good = engine.snapshot("cand-schema-ok")
    good_errs = candidate_schema_errors(good)

    missing = dict(good)
    missing.pop("repeat_count")
    missing_errs = candidate_schema_errors(missing)

    bad_kind = dict(good)
    bad_kind["kind"] = "hypothesis"
    kind_errs = candidate_schema_errors(bad_kind)

    # Stage skip: observed -> implementation without reproduce.
    skipped = False
    skip_reason = ""
    try:
        engine.advance_to_implementation("cand-schema-ok")
    except GateBlocked as exc:
        skipped = True
        skip_reason = exc.reason
    still = engine.snapshot("cand-schema-ok")

    checks = {
        "intake_present": intake_path.is_file(),
        "schema_present": schema_path.is_file(),
        "valid_candidate_errors": good_errs,
        "missing_repeat_count_rejected": bool(missing_errs),
        "bad_kind_rejected": bool(kind_errs),
        "observed_cannot_skip_to_implementation": skipped,
        "skip_reason": skip_reason,
        "stage_unchanged_after_block": still["stage"] == "observed",
        "repeat_count_field_present": "repeat_count" in good
        and good["repeat_count"]["observed"] == "0/0",
    }
    ok = (
        not good_errs
        and bool(missing_errs)
        and bool(kind_errs)
        and skipped
        and skip_reason == "missing-reproduction-receipt"
        and still["stage"] == "observed"
    )
    return {"pass": ok, "checks": checks}


def flaky_control() -> dict[str, Any]:
    """Catalog control: 3 of 10 labelled flaky, not accepted as a baseline."""
    engine = Intake(enforce_reproduction_gate=True)
    engine.observe(
        candidate_id="cand-flaky-3-of-10",
        kind="failure",
        summary="intermittent assertion in suite",
        source="fixture:3-of-10",
    )
    engine.reproduce(
        "cand-flaky-3-of-10",
        scripted_trials(FLAKY_3_OF_10),
        attempts=10,
        command="PYTHONDONTWRITEBYTECODE=1 python3 -B fixture_failing_test.py",
    )
    flaky = engine.snapshot("cand-flaky-3-of-10")
    blocked = False
    block_reason = ""
    try:
        engine.advance_to_implementation("cand-flaky-3-of-10")
    except GateBlocked as exc:
        blocked = True
        block_reason = exc.reason

    engine.observe(
        candidate_id="cand-confirmed-10-of-10",
        kind="failure",
        summary="deterministic assertion in suite",
        source="fixture:10-of-10",
    )
    engine.reproduce(
        "cand-confirmed-10-of-10",
        scripted_trials(CONFIRMED_10_OF_10),
        attempts=10,
        command="PYTHONDONTWRITEBYTECODE=1 python3 -B fixture_failing_test.py",
    )
    confirmed = engine.snapshot("cand-confirmed-10-of-10")
    engine.advance_to_implementation("cand-confirmed-10-of-10")
    after = engine.snapshot("cand-confirmed-10-of-10")
    proof = engine.stage_gate_audit()

    checks = {
        "classify_3_of_10": classify_repeat(3, 10),
        "flaky_classification": flaky["classification"],
        "flaky_repeat_count": flaky["repeat_count"],
        "flaky_stage": flaky["stage"],
        "flaky_baseline_accepted": flaky["baseline_accepted"],
        "flaky_advance_blocked": blocked,
        "flaky_block_reason": block_reason,
        "confirmed_classification": confirmed["classification"],
        "confirmed_repeat_count": confirmed["repeat_count"],
        "confirmed_reached_implementation": after["stage"] == "implementation",
        "audit_held": proof["held"],
        "audit_without_receipt": proof["advanced_without_confirmed_receipt"],
    }
    ok = (
        classify_repeat(3, 10) == "flaky"
        and flaky["classification"] == "flaky"
        and flaky["repeat_count"] == {"n": 3, "m": 10, "observed": "3/10"}
        and flaky["baseline_accepted"] is False
        and flaky["stage"] == "flaky"
        and blocked
        and block_reason == "flaky-not-accepted-as-baseline"
        and confirmed["classification"] == "confirmed"
        and confirmed["repeat_count"]["observed"] == "10/10"
        and after["stage"] == "implementation"
        and proof["held"] is True
        and proof["advanced_without_confirmed_receipt"] == []
    )
    return {"pass": ok, "checks": checks, "stage_gate_audit": proof}


def negative_control() -> dict[str, Any]:
    """Catalog negative control: remove the gate, unreproduced candidate advances.

    Also: a spoofed receipt on the gated engine does not satisfy the issued
    register, so field mutation is not a way around the gate.
    """
    gated = Intake(enforce_reproduction_gate=True)
    gated.observe(
        candidate_id="cand-unreproduced",
        kind="opportunity",
        summary="maybe a faster path exists",
        source="fixture:0-of-10",
    )
    gated.reproduce(
        "cand-unreproduced",
        scripted_trials(UNREPRODUCED_0_OF_10),
        attempts=10,
        command="PYTHONDONTWRITEBYTECODE=1 python3 -B fixture_opportunity.py",
    )
    unrep = gated.snapshot("cand-unreproduced")
    gated_blocked = False
    gated_reason = ""
    try:
        gated.advance_to_implementation("cand-unreproduced")
    except GateBlocked as exc:
        gated_blocked = True
        gated_reason = exc.reason

    # Spoof: copy confirmed-looking fields onto the candidate without issuance
    # of a confirmed receipt. The issued register still holds the unreproduced
    # receipt, so advance must still refuse.
    spoof = gated.candidates["cand-unreproduced"]
    spoof["classification"] = "confirmed"
    spoof["baseline_accepted"] = True
    spoof_blocked = False
    spoof_reason = ""
    try:
        gated.advance_to_implementation("cand-unreproduced")
    except GateBlocked as exc:
        spoof_blocked = True
        spoof_reason = exc.reason
    spoof["classification"] = unrep["classification"]
    spoof["baseline_accepted"] = unrep["baseline_accepted"]

    ungated = Intake(enforce_reproduction_gate=False)
    ungated.observe(
        candidate_id="cand-unreproduced-ungated",
        kind="failure",
        summary="never reproduced",
        source="fixture:negative-control",
    )
    ungated.reproduce(
        "cand-unreproduced-ungated",
        scripted_trials(UNREPRODUCED_0_OF_10),
        attempts=10,
        command="PYTHONDONTWRITEBYTECODE=1 python3 -B fixture_never.py",
    )
    ungated.advance_to_implementation("cand-unreproduced-ungated")
    advanced = ungated.snapshot("cand-unreproduced-ungated")
    ungated_proof = ungated.stage_gate_audit()
    gated_proof = gated.stage_gate_audit()

    checks = {
        "unreproduced_classification": unrep["classification"],
        "unreproduced_repeat_count": unrep["repeat_count"],
        "gated_blocked": gated_blocked,
        "gated_reason": gated_reason,
        "spoof_blocked": spoof_blocked,
        "spoof_reason": spoof_reason,
        "ungated_stage": advanced["stage"],
        "ungated_baseline_accepted": advanced["baseline_accepted"],
        "ungated_classification": advanced["classification"],
        "ungated_audit_held": ungated_proof["held"],
        "ungated_without_receipt_count": len(
            ungated_proof["advanced_without_confirmed_receipt"]
        ),
        "gated_audit_held": gated_proof["held"],
    }
    ok = (
        unrep["classification"] == "unreproduced"
        and unrep["repeat_count"]["observed"] == "0/10"
        and gated_blocked
        and gated_reason == "unreproduced-not-accepted-as-baseline"
        and spoof_blocked
        and advanced["stage"] == "implementation"
        and advanced["baseline_accepted"] is False
        and advanced["classification"] == "unreproduced"
        and ungated_proof["held"] is False
        and len(ungated_proof["advanced_without_confirmed_receipt"]) == 1
        and gated_proof["held"] is True
    )
    return {
        "pass": ok,
        "checks": checks,
        "gated_audit": gated_proof,
        "ungated_audit": ungated_proof,
    }
