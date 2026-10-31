#!/usr/bin/env python3
"""Probe 1: required-field validation per kind + pipeline identity.

Unit tests from the catalog:
  - required-field validation per outcome kind
  - each kind survives to the final artifact unmodified
A pipeline stage that rewrites NO-DECISION into DECISION must fail the
identity check (sensitivity control).
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools"))

from council.outcomes.kinds import (  # noqa: E402
    KIND_CONDITIONAL,
    KIND_NO_DECISION,
    KIND_PROOF_OF_IMPOSSIBILITY,
    CollapseForbidden,
    OutcomeValidationError,
    parse_outcome,
    required_fields_for,
)
from council.outcomes.pipeline import (  # noqa: E402
    outcome_unmodified,
    run_pipeline,
)

FIXTURES = {
    KIND_NO_DECISION: HERE / "fixtures" / "no_decision.json",
    KIND_CONDITIONAL: HERE / "fixtures" / "conditional.json",
    KIND_PROOF_OF_IMPOSSIBILITY: HERE / "fixtures" / "proof_of_impossibility.json",
}


def load(kind: str) -> dict:
    return json.loads(FIXTURES[kind].read_text(encoding="utf-8"))


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0311-probe1 {msg}")
    return 1


def main() -> int:
    parsed = {}
    for kind, path in FIXTURES.items():
        raw = load(kind)
        got = parse_outcome(raw)
        if got["kind"] != kind:
            return fail(f"parse remapped {kind} -> {got['kind']}")
        parsed[kind] = got
        print(f"parsed kind={kind} id={got['outcome_id']} fields={len(got)}")

    # Drop each required field; validation must fail.
    drops = 0
    for kind, raw in ((k, load(k)) for k in FIXTURES):
        for field in required_fields_for(kind):
            if field == "kind":
                continue
            mutant = deepcopy(raw)
            mutant.pop(field, None)
            try:
                parse_outcome(mutant)
            except OutcomeValidationError:
                drops += 1
                continue
            return fail(f"{kind} accepted missing {field}")
    print(f"required-field-drops-rejected={drops}")

    # Empty required strings must fail.
    empties = 0
    for kind, raw in ((k, load(k)) for k in FIXTURES):
        mutant = deepcopy(raw)
        if kind == KIND_NO_DECISION:
            mutant["reason"] = "   "
        elif kind == KIND_CONDITIONAL:
            mutant["conditions"] = []
        else:
            mutant["proof_sketch"] = ""
        try:
            parse_outcome(mutant)
        except OutcomeValidationError:
            empties += 1
            continue
        return fail(f"{kind} accepted empty required value")
    print(f"empty-required-rejected={empties}")

    # Binary alias is not a kind.
    try:
        parse_outcome({"kind": "FAIL", "outcome_id": "x"})
        return fail("kind=FAIL was accepted")
    except (CollapseForbidden, OutcomeValidationError):
        print("binary-alias-kind-rejected=True")

    # Proof flagged as equivalent to FAIL is a collapse.
    poi = load(KIND_PROOF_OF_IMPOSSIBILITY)
    poi["not_equivalent_to_fail"] = False
    try:
        parse_outcome(poi)
        return fail("proof with not_equivalent_to_fail=false accepted")
    except CollapseForbidden:
        print("proof-as-fail-rejected=True")

    # CONDITIONAL.if_unmet=apply-anyway would coerce into a decision.
    cond = load(KIND_CONDITIONAL)
    cond["if_unmet"] = "apply-anyway"
    try:
        parse_outcome(cond)
        return fail("conditional apply-anyway accepted")
    except OutcomeValidationError:
        print("conditional-apply-anyway-rejected=True")

    # Pipeline: each kind survives unmodified.
    artifacts = {}
    for kind in FIXTURES:
        raw = load(kind)
        art = run_pipeline(raw)
        if not outcome_unmodified(raw, art):
            return fail(f"pipeline mutated {kind}")
        if art["outcome"]["kind"] != kind:
            return fail(f"pipeline kind {art['outcome']['kind']} != {kind}")
        artifacts[kind] = art
        print(f"pipeline kind={kind} unmodified=True stages={art['stages']}")

    # Sensitivity: a stage that rewrites NO-DECISION -> DECISION must be caught.
    def coerce_stage(envelope: dict) -> dict:
        envelope = deepcopy(envelope)
        envelope["outcome"]["kind"] = "DECISION"
        envelope["outcome"]["decision_text"] = "coerced"
        envelope["outcome"]["evidence_ids"] = ["planted"]
        return envelope

    caught = False
    try:
        run_pipeline(load(KIND_NO_DECISION), extra_stages=[coerce_stage])
    except (ValueError, OutcomeValidationError, CollapseForbidden):
        caught = True
    if not caught:
        return fail("pipeline did not catch NO-DECISION -> DECISION rewrite")
    print("pipeline-coercion-caught=True")

    print(
        json.dumps(
            {
                "probe": "probe1-required-fields-and-pipeline",
                "unit_id": "IMP-0311",
                "kinds": sorted(parsed),
                "drops_rejected": drops,
                "pipeline_unmodified": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0311-probe1 required-field validation and pipeline identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
