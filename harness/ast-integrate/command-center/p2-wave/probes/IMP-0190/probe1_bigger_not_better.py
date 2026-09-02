#!/usr/bin/env python3
"""Probe 1: bigger-but-not-better REJECTED; a better fusion PASSES (both-states).

Also: a fusion using stage_count as the declared metric is refused, and a
rejected candidate does not enter FusionLibrary.
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
    ADMIT_OUTPERFORM,
    REJECT_BIGGER_NOT_BETTER,
    REJECT_FORBIDDEN_METRIC,
    FusionLibrary,
    decision_fingerprint,
    evaluate,
)

ART = REPO / "command-center/receipts/IMP-0190.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0190-probe1 {msg}")
    return 1


def main() -> int:
    lib = FusionLibrary()
    bad = F.bigger_not_better()
    good = F.better_on_metric()
    vanity = F.stage_count_as_metric()

    d_bad = lib.try_admit(bad)
    d_good = lib.try_admit(good)
    d_vanity = evaluate(vanity)

    print(
        json.dumps(
            {
                "bigger_not_better": d_bad.to_dict(),
                "better_on_metric": d_good.to_dict(),
                "stage_count_metric": d_vanity.to_dict(),
                "library_ids": list(lib.admitted_ids()),
            },
            sort_keys=True,
        )
    )

    if d_bad.admitted:
        return fail("bigger-not-better was admitted")
    if d_bad.reason != REJECT_BIGGER_NOT_BETTER:
        return fail(f"bigger-not-better reason={d_bad.reason}")
    if d_bad.outperform or d_bad.complement:
        return fail("bigger-not-better flagged outperform or complement")
    if d_bad.fusion_stage_count <= max(n for _, n in d_bad.source_stage_counts):
        return fail("fixture is not actually larger than sources")
    if lib.contains(bad.fusion_id):
        return fail("rejected fusion entered the library")
    if d_bad.stage_count_used_as_criterion:
        return fail("stage_count_used_as_criterion leaked true on reject")
    if d_bad.prose_consulted:
        return fail("gate consulted prose_claim")

    # Prose claiming more-stages-is-better must not change the reject.
    swapped = F.prose_swap(bad, "utterly different marketing copy")
    d_swap = evaluate(swapped)
    if decision_fingerprint(d_swap) != decision_fingerprint(d_bad):
        return fail("prose_claim mutated the bigger-not-better decision")

    if not d_good.admitted:
        return fail("better-on-metric was rejected")
    if d_good.reason != ADMIT_OUTPERFORM:
        return fail(f"better-on-metric reason={d_good.reason}")
    if not d_good.outperform:
        return fail("better-on-metric outperform flag false")
    if d_good.complement:
        return fail("better-on-metric unexpectedly complementary")
    if d_good.fusion_stage_count != d_bad.fusion_stage_count:
        return fail("both-states size mismatch (better must share padded size)")
    if not lib.contains(good.fusion_id):
        return fail("admitted outperform fusion missing from library")
    if d_good.stage_count_used_as_criterion:
        return fail("stage count used as outperform criterion")

    if d_vanity.admitted:
        return fail("stage_count metric fusion was admitted")
    if d_vanity.reason != REJECT_FORBIDDEN_METRIC:
        return fail(f"stage_count metric reason={d_vanity.reason}")

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
    recorded = (doc.get("fusion_admission_gate") or {}).get("bigger_not_better") or {}
    if recorded.get("reason") != REJECT_BIGGER_NOT_BETTER:
        return fail("receipt did not record bigger-not-better reject")
    if recorded.get("admitted") is not False:
        return fail("receipt did not record bigger-not-better admitted=false")
    rec_good = (doc.get("fusion_admission_gate") or {}).get("better_on_metric") or {}
    if rec_good.get("admitted") is not True:
        return fail("receipt did not record outperform admit")
    if rec_good.get("reason") != ADMIT_OUTPERFORM:
        return fail("receipt outperform reason drift")

    print(
        "bigger_rejected=True outperform_admitted=True "
        f"library={list(lib.admitted_ids())} vanity_rejected=True"
    )
    print("SUCCESS:IMP-0190-probe1 bigger-not-better rejected; better admitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
