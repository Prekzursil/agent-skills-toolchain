#!/usr/bin/env python3
"""Probe 2: independent reviewer counterexample + both-states rerun.

Reviewer does not load the author's objection fixtures. It constructs:
  * a schema-valid non-example (known-good instance labeled counterexample)
    that MUST be refused — otherwise schema-passing is enough to hostage
  * an alternate real break (two absent seats counted) that MUST stand —
    otherwise the bar is 'reject every objection'

Signal 1: schema_ok on those constructed records.
Signal 2: evaluate()/consent_outcome (admissible / outcome), a different field.

Also re-runs the catalog both-states control and schema-checks the design note.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import admissibility as A  # noqa: E402

ART = (
    A.REPO
    / "command-center/design/council/CNL-0060-consent-no-objection-and-the-admissibility-bar-for-an-obje.md"
)
NOTE_SCHEMA = A.REPO / "command-center/schema/council-design-note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0060-probe2 {msg}")
    return 1


def main() -> int:
    proposal = A.load_proposal("proposal.json")
    vacuous = A.load_proposal("proposal-vacuous.json")

    nonexample = {
        "objector_seat": "advocate",
        "target": {
            "proposal_id": "p-consent-1",
            "claim_id": "consent-excludes-absent",
        },
        "blocking_claim": "I object; the instance still satisfies the claim.",
        "falsifier": {
            "kind": "counterexample",
            "instance": {
                "seats": ["a", "b", "c"],
                "present": ["a", "b"],
                "consent_counted": ["a", "b"],
            },
        },
    }
    alt_break = {
        "objector_seat": "advocate",
        "target": {
            "proposal_id": "p-consent-1",
            "claim_id": "consent-excludes-absent",
        },
        "blocking_claim": "Two absent seats (c and d) are folded into consent_counted.",
        "falsifier": {
            "kind": "counterexample",
            "instance": {
                "seats": ["a", "b", "c", "d"],
                "present": ["a", "b"],
                "consent_counted": ["a", "b", "c", "d"],
            },
        },
    }

    sch_n = A.schema_check(nonexample)
    sch_a = A.schema_check(alt_break)
    ev_n = A.evaluate(proposal, nonexample)
    ev_a = A.evaluate(proposal, alt_break)
    out_n = A.consent_outcome(proposal, [nonexample])
    out_a = A.consent_outcome(proposal, [alt_break])

    print("REVIEWER_COUNTEREXAMPLE_INSTANCE")
    print(json.dumps({"nonexample": nonexample, "alt_break": alt_break}, sort_keys=True))
    print(f"signal1_schema nonexample_ok={sch_n['ok']} alt_break_ok={sch_a['ok']}")
    print(
        "signal2_eval "
        f"nonexample_admissible={ev_n['admissible']} code={ev_n['code']} "
        f"alt_break_admissible={ev_a['admissible']} code={ev_a['code']}"
    )
    print(f"outcome_nonexample={out_n['outcome']} outcome_alt_break={out_a['outcome']}")

    if sch_n["ok"] is not True or sch_a["ok"] is not True:
        return fail("reviewer instances must be schema-valid (else signal 2 is untested)")
    if ev_n["admissible"] is not False:
        return fail(f"dressed non-example was admitted: {ev_n}")
    if ev_n["code"] != "COUNTEREXAMPLE_DOES_NOT_FALSIFY":
        return fail(f"non-example code={ev_n['code']} want COUNTEREXAMPLE_DOES_NOT_FALSIFY")
    if out_n["outcome"] != "CONSENTED":
        return fail("schema-valid non-example blocked consent")
    if ev_a["admissible"] is not True:
        return fail(f"reviewer real break did not stand: {ev_a}")
    if out_a["outcome"] != "BLOCKED":
        return fail("reviewer real break did not block")

    pelig = A.proposal_eligible(proposal)
    velig = A.proposal_eligible(vacuous)
    print(
        f"proposal_eligible good={pelig['eligible']} vacuous={velig['eligible']} "
        f"vacuous_reason={velig['reason']}"
    )
    if pelig["eligible"] is not True:
        return fail("good proposal not eligible")
    if velig["eligible"] is not False or velig["reason"] != "KNOWN_BAD_PASSES":
        return fail(f"vacuous proposal not refused: {velig}")

    counter = A.load_objection("objection-counterexample.json")
    unfals = A.load_objection("objection-unfalsifiable.json")
    ev_c = A.evaluate(proposal, counter)
    ev_u = A.evaluate(proposal, unfals)
    print(
        "BOTH_STATES_RERUN "
        f"fired_on_unfalsifiable_refuse={ev_u['admissible'] is False} "
        f"silent_on_counterexample_admit={ev_c['admissible'] is True}"
    )
    if ev_u["admissible"] is not False or ev_c["admissible"] is not True:
        return fail("reviewer both-states rerun did not discriminate")

    if not ART.is_file():
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"artifact self-declared {doc.get('state')}")
    if "SUCCESS:CNL-0060" not in json.dumps(doc):
        return fail("sentinel missing")
    if doc.get("unit_id") != "CNL-0060":
        return fail("unit_id mismatch")
    if not NOTE_SCHEMA.is_file():
        return fail("council-design-note schema missing")
    shim = json.loads(NOTE_SCHEMA.read_text(encoding="utf-8"))
    if shim.get("x-artifact-class") != "council-design-note":
        return fail("design-note schema class mismatch")
    # Shim $ref is a non-routable host on this image; do not fetch.
    # Domain fields below are the live constraints for this unit.

    bs = doc.get("both_states") or {}
    if bs.get("fired_on_planted_bad") is not True:
        return fail("artifact both_states.fired_on_planted_bad is not true")
    if bs.get("silent_on_known_good") is not True:
        return fail("artifact both_states.silent_on_known_good is not true")
    nc = doc.get("negative_control") or {}
    if not nc.get("verbatim"):
        return fail("artifact missing negative_control.verbatim")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer.independent is not true")
    if reviewer.get("recount_agrees") is not True:
        return fail("reviewer.recount_agrees is not true")
    det = doc.get("detector") or {}
    if det.get("pair_and_gate_rejected") is not True:
        return fail("detector.pair_and_gate_rejected is not true")

    print("reviewer_nonexample_refused=True reviewer_alt_break_stands=True")
    print("SUCCESS:CNL-0060-probe2 reviewer counterexample and both-states rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
