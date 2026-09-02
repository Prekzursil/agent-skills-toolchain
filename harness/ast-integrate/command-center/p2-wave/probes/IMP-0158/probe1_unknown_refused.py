#!/usr/bin/env python3
"""Probe 1: unknown-tier fixture is refused; first-party twin can auto-adopt.

Both-states on the SAME candidate document (including first-party self-labels).
Only the evidence record changes. Labels are not admission inputs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from load_lib import ensure_import  # noqa: E402
from fixtures import load_json, twin_pair  # noqa: E402

ensure_import()
from workflow_foundry.trust_tier import (  # noqa: E402
    REASON_UNKNOWN_REFUSED,
    STATUS_AUTO_ADOPTED,
    STATUS_REFUSED,
    admit_candidate,
    assign_trust_tier,
    classify_by_candidate_label,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0158-probe1 {msg}")
    return 1


def main() -> int:
    candidate, unknown, first_party = twin_pair()
    vendor_c = load_json("candidate-vendor.json")
    vendor_e = load_json("evidence-vendor.json")

    if candidate["candidate_id"] != first_party["candidate_id"]:
        return fail("twin pair does not share candidate_id")
    if classify_by_candidate_label(candidate) != "first-party":
        return fail("label-control classifier did not see first-party self-label")

    unknown_tier = assign_trust_tier(candidate, unknown)
    first_tier = assign_trust_tier(candidate, first_party)
    refused = admit_candidate(candidate, unknown)
    adopted = admit_candidate(candidate, first_party)
    vendor = admit_candidate(vendor_c, vendor_e)

    report = {
        "probe": "probe1-unknown-refused",
        "unit_id": "IMP-0158",
        "candidate_id": candidate["candidate_id"],
        "label_classifier": classify_by_candidate_label(candidate),
        "unknown": {
            "tier": unknown_tier.tier,
            "reason": unknown_tier.reason,
            "admission": refused.as_dict(),
        },
        "first_party_twin": {
            "tier": first_tier.tier,
            "reason": first_tier.reason,
            "admission": adopted.as_dict(),
        },
        "label_would_auto_adopt": classify_by_candidate_label(candidate)
        == "first-party",
        "production_refused_labeled_unknown": refused.status == STATUS_REFUSED,
        "twin_auto_adopted": adopted.status == STATUS_AUTO_ADOPTED,
        "vendor_not_promoted_by_label": vendor.tier == "vendor",
        "both_states": True,
        "pass": False,
    }

    if unknown_tier.tier != "unknown":
        print(json.dumps(report, indent=2))
        return fail(f"unknown fixture assigned {unknown_tier.tier}")
    if refused.status != STATUS_REFUSED or refused.admitted or refused.auto_adopted:
        print(json.dumps(report, indent=2))
        return fail(f"unknown fixture not refused: {refused.as_dict()}")
    if refused.reason != REASON_UNKNOWN_REFUSED:
        return fail(f"refuse reason {refused.reason}")
    if refused.required_fix is None:
        return fail("refused unknown did not name required_fix")
    if first_tier.tier != "first-party":
        print(json.dumps(report, indent=2))
        return fail(f"first-party twin assigned {first_tier.tier}")
    if adopted.status != STATUS_AUTO_ADOPTED or not adopted.auto_adopted:
        print(json.dumps(report, indent=2))
        return fail(f"first-party twin not auto-adopted: {adopted.as_dict()}")
    if adopted.tier != "first-party":
        return fail("admission did not take first-party as input")
    if refused.method != "tier-as-admission-input":
        return fail("admission method was not tier-as-admission-input")
    if vendor.tier != "vendor" or vendor.status != STATUS_AUTO_ADOPTED:
        return fail("vendor evidence was not assigned vendor / auto-adopted")

    report["pass"] = True
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        "both-states: unknown REFUSED (labels ignored); "
        "first-party twin AUTO_ADOPTED"
    )
    print("SUCCESS:IMP-0158-probe1 unknown-tier refused; first-party twin auto-adopted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
