#!/usr/bin/env python3
"""Probe 2: complementarity is a capability-vector set difference, not prose.

A genuinely complementary fusion is admitted and the new capability is named.
A planted prose-only complement (empty set difference) is rejected.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from fusion.admission_gate import (  # noqa: E402
    ADMIT_COMPLEMENT,
    REJECT_BIGGER_NOT_BETTER,
    FusionLibrary,
    decision_fingerprint,
    evaluate,
)

ART = REPO / "command-center/receipts/IMP-0190.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0190-probe2 {msg}")
    return 1


def main() -> int:
    lib = FusionLibrary()
    comp = F.complementary()
    prose = F.prose_only_complement()

    d_comp = lib.try_admit(comp)
    d_prose = lib.try_admit(prose)

    # Independent construction: frozenset arithmetic in this file, not the gate helper.
    live_delta = F.independent_capability_delta(comp)
    prose_delta = F.independent_capability_delta(prose)

    print(
        json.dumps(
            {
                "complement": d_comp.to_dict(),
                "prose_only": d_prose.to_dict(),
                "independent_delta": list(live_delta),
                "prose_independent_delta": list(prose_delta),
                "library_ids": list(lib.admitted_ids()),
                "named_new_capability": F.NEW_CAP,
            },
            sort_keys=True,
        )
    )

    if live_delta != (F.NEW_CAP,):
        return fail(f"independent delta {live_delta} != ({F.NEW_CAP!r},)")
    if tuple(d_comp.named_new_capabilities) != live_delta:
        return fail("gate named_new_capabilities != independent set difference")
    if tuple(d_comp.capability_vector_delta) != live_delta:
        return fail("gate capability_vector_delta != independent set difference")
    if not d_comp.admitted:
        return fail("complementary fusion rejected")
    if d_comp.reason != ADMIT_COMPLEMENT:
        return fail(f"complement reason={d_comp.reason}")
    if d_comp.outperform:
        return fail("complement fixture must not outperform on the metric")
    if not d_comp.complement:
        return fail("complement flag false")
    if F.NEW_CAP not in d_comp.named_new_capabilities:
        return fail("new capability not named")
    if not lib.contains(comp.fusion_id):
        return fail("complementary fusion missing from library")
    if d_comp.prose_consulted:
        return fail("gate consulted prose on complement")

    # Same vector, different prose → identical fingerprint.
    swapped = F.prose_swap(comp, "this sentence claims a different new skill")
    if decision_fingerprint(evaluate(swapped)) != decision_fingerprint(d_comp):
        return fail("prose_claim mutated the complement decision")

    if prose_delta != ():
        return fail(f"prose-only independent delta not empty: {prose_delta}")
    if d_prose.admitted:
        return fail("prose-only complement was admitted")
    if d_prose.named_new_capabilities != ():
        return fail("prose-only named a capability")
    if d_prose.complement:
        return fail("prose-only complement flag true")
    if d_prose.reason != REJECT_BIGGER_NOT_BETTER:
        return fail(f"prose-only reason={d_prose.reason}")
    if lib.contains(prose.fusion_id):
        return fail("prose-only fusion entered the library")

    # Changing only prose on the reject fixture must not admit it.
    if evaluate(F.prose_swap(prose, "")).admitted:
        return fail("clearing prose admitted the empty-delta fusion")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0190" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    rec = (doc.get("fusion_admission_gate") or {}).get("complement") or {}
    if rec.get("admitted") is not True:
        return fail("receipt missing complement admit")
    named = rec.get("named_new_capabilities") or []
    if F.NEW_CAP not in named:
        return fail("receipt did not name the new capability")
    rec_prose = (doc.get("fusion_admission_gate") or {}).get("prose_only") or {}
    if rec_prose.get("admitted") is not False:
        return fail("receipt did not record prose-only reject")
    if rec_prose.get("named_new_capabilities"):
        return fail("receipt named a capability for empty delta")

    print(
        f"complement_admitted=True named={list(d_comp.named_new_capabilities)} "
        "prose_only_rejected=True delta_computed=True"
    )
    print("SUCCESS:IMP-0190-probe2 capability-vector complement named; prose-only rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
