#!/usr/bin/env python3
"""Named probe 2 (negative control): downgrade the gate to a warning.

Same unmet-quota request that ENFORCE refuses is GRANTED under WARN, and
the council actually enters convergence. That split is the proof that
enforcement, not reporting, carries the behaviour.
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
    load_records,
    measure_corpus,
    replay_through_gate,
)

FIXTURE = HERE / "fixtures" / "recorded_councils.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0368-probe2 {msg}")
    return 1


def unmet_request(mode: GateMode) -> PhaseMachine:
    machine = PhaseMachine(
        idea_quota=3,
        objection_quota=2,
        gate_mode=mode,
        council_id=f"neg-{mode.value}",
    )
    machine.record_idea("only-one")
    return machine


def main() -> int:
    enforce_m = unmet_request(GateMode.ENFORCE)
    warn_m = unmet_request(GateMode.WARN)
    enforce = enforce_m.request_convergence()
    warn = warn_m.request_convergence()

    if enforce.granted or enforce_m.phase != PHASE_DIVERGENCE:
        return fail("ENFORCE did not refuse the unmet-quota request")
    if enforce.event.warning:
        return fail("ENFORCE recorded a warning instead of a refusal")
    if not warn.granted or warn_m.phase != PHASE_CONVERGENCE:
        return fail("WARN did not let the early transition occur")
    if not warn.event.warning:
        return fail("WARN grant did not mark warning=true")
    if not warn.event.would_have_refused:
        return fail("WARN grant did not record would_have_refused")
    if warn.event.gate_mode != "warn" or enforce.event.gate_mode != "enforce":
        return fail("gate_mode not recorded on events")

    # Identical snapshot logic; only the decision differs.
    if enforce.event.quotas.as_dict() != warn.event.quotas.as_dict():
        return fail("ENFORCE/WARN quota snapshots diverged — fork is not load-bearing")
    if enforce.event.quotas.all_met:
        return fail("control request was not actually unmet")

    records = load_records(FIXTURE)
    measured = measure_corpus(records)
    if measured["enforce_premature_successes"] != 0:
        return fail("corpus ENFORCE still allowed premature success")
    if measured["warn_premature_successes"] != measured["n_premature_historical"]:
        return fail(
            "WARN premature successes "
            f"{measured['warn_premature_successes']} != historical "
            f"{measured['n_premature_historical']}"
        )
    if not measured["gate_is_enforcing_not_reporting"]:
        return fail("enforcing-vs-reporting discriminant failed")

    fx01_e = replay_through_gate(next(r for r in records if r["id"] == "fx-01"), GateMode.ENFORCE)
    fx01_w = replay_through_gate(next(r for r in records if r["id"] == "fx-01"), GateMode.WARN)
    if fx01_e["entered_convergence"] or not fx01_w["entered_convergence"]:
        return fail("fx-01 warn/enforce split failed")

    payload = {
        "pass": True,
        "probe": "probe2-warn-downgrade",
        "unit_id": "IMP-0368",
        "enforce_granted": enforce.granted,
        "warn_granted": warn.granted,
        "warn_phase": warn_m.phase,
        "enforce_phase": enforce_m.phase,
        "early_transition_occurs_under_warn": True,
        "enforcement_is_load_bearing": True,
        "warn_premature_successes": measured["warn_premature_successes"],
        "enforce_premature_successes": measured["enforce_premature_successes"],
        "reviewer_starts_from_tests": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "enforce_refused=True warn_granted=True "
        f"warn_early={measured['warn_premature_successes']} "
        f"enforce_early={measured['enforce_premature_successes']} "
        "load_bearing=True"
    )
    print("SUCCESS:IMP-0368-probe2 warn-downgrade lets early transition occur")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
