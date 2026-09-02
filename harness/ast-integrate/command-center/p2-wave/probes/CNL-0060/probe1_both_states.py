#!/usr/bin/env python3
"""Probe 1: both directions of the admissibility bar.

Catalog test: an unfalsifiable objection is INADMISSIBLE; a concrete
counterexample STANDS.

Signal 1: jsonschema Draft-07 over the objection record (schema_ok).
Signal 2: evaluate() predicate field (admissible / predicate_false).

Negative control, verbatim: on the unfalsifiable fixture the check REFUSES
the block (consent_outcome CONSENTED). That is the state it is meant to reject.
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


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0060-probe1 {msg}")
    return 1


def main() -> int:
    proposal = A.load_proposal("proposal.json")
    counter = A.load_objection("objection-counterexample.json")
    unfals = A.load_objection("objection-unfalsifiable.json")

    elig = A.proposal_eligible(proposal)
    print(f"proposal_eligible={elig['eligible']} reason={elig['reason']}")
    if elig["eligible"] is not True:
        return fail(f"fixture proposal not eligible: {elig}")

    sch_c = A.schema_check(counter)
    sch_u = A.schema_check(unfals)
    ev_c = A.evaluate(proposal, counter)
    ev_u = A.evaluate(proposal, unfals)
    out_c = A.consent_outcome(proposal, [counter])
    out_u = A.consent_outcome(proposal, [unfals])
    out_host = A.consent_outcome(proposal, [unfals, unfals, unfals])

    print("SIGNAL1_SCHEMA")
    print(f"verbatim_schema_counterexample ok={sch_c['ok']} errors={sch_c['errors']}")
    print(f"verbatim_schema_unfalsifiable ok={sch_u['ok']} errors={sch_u['errors']}")
    print("SIGNAL2_EVAL")
    print(
        "verbatim_eval_counterexample "
        f"admissible={ev_c['admissible']} code={ev_c['code']} "
        f"predicate_false={ev_c.get('predicate_false')} schema_ok={ev_c['schema_ok']}"
    )
    print(
        "verbatim_eval_unfalsifiable "
        f"admissible={ev_u['admissible']} code={ev_u['code']} "
        f"schema_ok={ev_u['schema_ok']} eval_code={ev_u.get('eval_code')}"
    )
    print(
        "NEGATIVE_CONTROL_CHECK=evaluate+consent_outcome "
        "REJECT_STATE=unfalsifiable concern (kind=concern, no instance)"
    )
    print(
        "verbatim_negative_control "
        f"admissible={ev_u['admissible']} outcome={out_u['outcome']} "
        f"blocker_count={out_u['blocker_count']}"
    )
    print(
        f"outcome_counterexample={out_c['outcome']} "
        f"outcome_unfalsifiable={out_u['outcome']} "
        f"outcome_triple_unfalsifiable={out_host['outcome']}"
    )

    if sch_c["ok"] is not True:
        return fail("counterexample failed schema (signal 1 should pass)")
    if sch_u["ok"] is not False:
        return fail("unfalsifiable passed schema (signal 1 must fail)")
    if ev_c["admissible"] is not True or ev_c["code"] != "ADMISSIBLE":
        return fail(f"concrete counterexample did not stand: {ev_c}")
    if ev_c.get("predicate_false") is not True:
        return fail("counterexample was not a predicate-False instance")
    if ev_u["admissible"] is not False:
        return fail(f"unfalsifiable was admitted: {ev_u}")
    if ev_u["code"] not in {
        "UNFALSIFIABLE",
        "UNKNOWN_KIND",
        "NO_DISCRIMINATOR",
        "SCHEMA_INVALID",
    }:
        return fail(f"unfalsifiable code not a refuse-block code: {ev_u['code']}")
    if out_c["outcome"] != "BLOCKED":
        return fail("admissible objection did not block consent")
    if out_u["outcome"] != "CONSENTED":
        return fail("unfalsifiable concern blocked consent — hostage")
    if out_host["outcome"] != "CONSENTED" or out_host["blocker_count"] != 0:
        return fail("repeated unfalsifiable filings blocked consent")

    stripped = json.loads(json.dumps(counter))
    stripped["falsifier"] = {"kind": "counterexample", "instance": {}}
    ev_s = A.evaluate(proposal, stripped)
    print(f"mutation_empty_instance admissible={ev_s['admissible']} code={ev_s['code']}")
    if ev_s["admissible"] is not False:
        return fail("empty-instance mutant still admissible")

    mutants = A.mutant_battery(proposal)
    print("mutant_battery " + json.dumps(mutants, sort_keys=True))
    if any(int(m["caught"]) != 1 for m in mutants) or len(mutants) < 4:
        return fail(f"mutant battery incomplete or missed: {mutants}")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            return fail(f"artifact self-declared {doc.get('state')}")
        if "SUCCESS:CNL-0060" not in json.dumps(doc):
            return fail("sentinel missing from artifact")

    print(
        "unfalsifiable_inadmissible=True counterexample_stands=True "
        "schema_separates=True eval_separates=True hostage_consented=True"
    )
    print("SUCCESS:CNL-0060-probe1 both-states admissibility bar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
