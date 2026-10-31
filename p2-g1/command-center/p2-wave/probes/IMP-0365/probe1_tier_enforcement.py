#!/usr/bin/env python3
"""IMP-0365 probe1: tier enforcement at the admission point.

For every declared floor the classifier admits exactly the at-or-above-tier
claims of the labelled set and refuses the under-tier ones; an under-tier
fixture claim (blog source under executable-proof-only) is refused and cannot
be attached to a binding decision (UnderTierError).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.standard import (  # noqa: E402
    UnderTierError,
    admit_claim,
    bind_decision,
    expected_admitted_ids,
    load_labelled_claims,
    preset_for,
)

RECEIPT = REPO / "command-center/receipts/IMP-0365.json"
FLOORS = ("anecdote", "cited-source", "replicated-study",
          "peer-reviewed-only", "executable-proof-only")


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0365-probe1 {msg}")
    return 1


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    claims = load_labelled_claims()
    if len(claims) < 5:
        return fail(f"fixture-too-small:{len(claims)}")
    matrix = {}
    for floor in FLOORS:
        preset = preset_for(floor)
        decision = bind_decision(preset, claims)
        want = expected_admitted_ids(floor, claims)
        if decision["supporting_claim_ids"] != want:
            return fail(f"{floor}:admitted-set-diverged")
        for cid in decision["refused_claim_ids"]:
            row = admit_claim(preset, next(c for c in claims if c["id"] == cid))
            if row["admitted"] is not False:
                return fail(f"{floor}:{cid}:admitted-anyway")
        matrix[floor] = {
            "admitted": decision["supporting_claim_ids"],
            "refused": decision["refused_claim_ids"],
        }

    # Under-tier negative control: blog claim under executable-proof-only.
    preset = preset_for("executable-proof-only")
    under = next(c for c in claims if c["id"] == "C-CITED")
    row = admit_claim(preset, under)
    if row["admitted"] is not False:
        return fail("under-tier-C-CITED-admitted")
    decision = bind_decision(preset, claims)
    try:
        from council.evidence.standard import attach_claim
        attach_claim(decision, "C-CITED")
        return fail("under-tier-bound-anyway")
    except UnderTierError:
        pass
    if decision["binding"] is not True:
        return fail("top-floor-decision-not-binding")

    # At-tier decision binds.
    if "C-EXEC" not in decision["supporting_claim_ids"]:
        return fail("executable-claim-missing-from-top-floor")

    print(json.dumps({
        "probe": "probe1-tier-enforcement", "unit_id": "IMP-0365", "pass": True,
        "classifier_input_field": "source.type",
        "floors": sorted(matrix), "under_tier_refused": "C-CITED",
    }, sort_keys=True))
    print("SUCCESS:IMP-0365-probe1 every floor enforced; under-tier refused and unbound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
