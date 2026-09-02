#!/usr/bin/env python3
"""Named probe 1: transition is blocked until divergence quotas are met.

Evidence: an attempted early transition is REFUSED (not warned), and the
granting event carries quota values frozen at transition time. Historical
rate on the fixture corpus is computed by quota attainment, not round count.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.phases import (  # noqa: E402
    GateMode,
    PHASE_CONVERGENCE,
    PHASE_DIVERGENCE,
    PhaseMachine,
    TransitionRefused,
    demo_blocked_then_granted,
    discover_production_recordings,
    historical_audit,
    load_records,
    measure_corpus,
    optional_premature_detector_present,
    optional_targets_module_present,
)

FIXTURE = HERE / "fixtures" / "recorded_councils.json"
MODULE = REPO / "tools" / "council" / "phases.py"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0368-probe1 {msg}")
    return 1


def main() -> int:
    if not MODULE.is_file() or MODULE.stat().st_size < 200:
        return fail("tools/council/phases.py missing")

    machine = PhaseMachine(idea_quota=3, objection_quota=2, gate_mode=GateMode.ENFORCE)
    early = machine.request_convergence()
    if early.granted:
        return fail("early transition was granted under ENFORCE")
    if early.event.outcome != "REFUSED":
        return fail(f"early outcome={early.event.outcome} want REFUSED")
    if early.event.warning:
        return fail("early refusal was a warning, not a refusal")
    if machine.phase != PHASE_DIVERGENCE:
        return fail(f"phase after refuse={machine.phase}")
    if early.event.quotas.ideas_attained != 0 or early.event.quotas.objections_attained != 0:
        return fail("quota snapshot at early refuse is wrong")

    try:
        machine.request_convergence_or_raise()
        return fail("request_convergence_or_raise did not raise")
    except TransitionRefused as exc:
        if exc.result.granted:
            return fail("TransitionRefused wrapped a grant")

    for i in range(3):
        machine.record_idea(f"idea-{i+1}")
    short = machine.request_convergence()
    if short.granted or machine.phase != PHASE_DIVERGENCE:
        return fail("ideas-only transition was not refused")
    if short.event.quotas.ideas_met is not True:
        return fail("snapshot should show ideas met")
    if short.event.quotas.objections_met is not False:
        return fail("snapshot should show objections unmet")

    machine.record_idea("idea-1")  # duplicate must not inflate
    if machine.snapshot_quotas().ideas_attained != 3:
        return fail("duplicate idea inflated attainment")

    for i in range(2):
        machine.record_objection(f"obj-{i+1}")
    granted = machine.request_convergence()
    if not granted.granted or machine.phase != PHASE_CONVERGENCE:
        return fail("met-quota transition was not granted")
    if granted.event.warning:
        return fail("successful grant carried a warning")
    snap = granted.event.quotas
    if snap.ideas_attained != 3 or snap.objections_attained != 2 or not snap.all_met:
        return fail(f"grant snapshot wrong {snap.as_dict()}")
    if "quotas" not in granted.event.as_dict() or "ideas_required" not in granted.event.quotas.as_dict():
        return fail("transition event missing quota values")

    demo = demo_blocked_then_granted()
    if demo["early"]["granted"] or demo["still_short"]["granted"] or not demo["granted"]["granted"]:
        return fail("canonical demo sequence broken")
    if demo["final_phase"] != PHASE_CONVERGENCE:
        return fail("canonical demo did not end in convergence")

    records = load_records(FIXTURE)
    if len(records) != 20:
        return fail(f"fixture corpus size={len(records)} want=20")

    for rec in records:
        hist = historical_audit(rec)
        expected = rec.get("expected_historical")
        if expected == "premature" and not hist["premature"]:
            return fail(f"{rec['id']} expected premature")
        if expected == "valid" and (not hist["entered_convergence"] or hist["premature"]):
            return fail(f"{rec['id']} expected valid")
        if expected == "no-convergence" and hist["entered_convergence"]:
            return fail(f"{rec['id']} expected no-convergence")

    fx07 = historical_audit(next(r for r in records if r["id"] == "fx-07"))
    if not fx07["premature"] or fx07["rounds_before_convergence"] != 10:
        return fail("fx-07 did not prove round-count is ignored")
    fx11 = historical_audit(next(r for r in records if r["id"] == "fx-11"))
    if fx11["premature"] or not fx11["entered_convergence"]:
        return fail("easy-question fx-11 was flagged premature (quota was met)")

    measured = measure_corpus(records)
    if measured["n_premature_historical"] != 9:
        return fail(f"premature count={measured['n_premature_historical']} want=9")
    if measured["n_entered_convergence_historical"] != 17:
        return fail(f"entered={measured['n_entered_convergence_historical']} want=17")
    if measured["enforce_premature_successes"] != 0:
        return fail("ENFORCE allowed a premature success")
    if not measured["gate_is_enforcing_not_reporting"]:
        return fail("gate_is_enforcing_not_reporting is false")
    rate = measured["premature_rate_among_converged"]
    if abs(rate - (9 / 17)) > 1e-12:
        return fail(f"rate={rate} want=9/17")

    production = discover_production_recordings(REPO)
    targets = optional_targets_module_present(REPO)
    premature_mod = optional_premature_detector_present(REPO)

    payload = {
        "pass": True,
        "probe": "probe1-gate-blocks",
        "unit_id": "IMP-0368",
        "early_refused": True,
        "early_was_warning": False,
        "grant_snapshot": snap.as_dict(),
        "n_recorded_fixture": measured["n_recorded"],
        "n_premature_historical": measured["n_premature_historical"],
        "premature_rate_among_converged": rate,
        "enforce_premature_successes": measured["enforce_premature_successes"],
        "gate_is_enforcing_not_reporting": True,
        "production_recordings": production,
        "imp_0301_targets_present": targets,
        "imp_0323_premature_present": premature_mod,
        "criterion": "quota-attainment-not-round-count",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "early_refused=True warning=False granted_after_quotas=True "
        f"historical_premature={measured['n_premature_historical']}/"
        f"{measured['n_entered_convergence_historical']} "
        f"enforce_early_successes={measured['enforce_premature_successes']} "
        f"production_recordings={len(production)}"
    )
    print("SUCCESS:IMP-0368-probe1 transition blocked until quotas met")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
