#!/usr/bin/env python3
"""Named probe 2 (reviewer): strip a required anchor; retention check must FIRE.

Starts from the retention check's contract, not from an author summary.
Positive control: the detector finds ANCHOR_COST in the unstripped twin
before its silence is trusted. Negative control: after the required
EVIDENCE block is removed, the check fires even if the id remains in prose.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.context import (  # noqa: E402
    assemble_seat,
    present_required_ids,
    retention_check,
    seat_from_mapping,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0338-probe2 {msg}")
    return 1


def strip_required_block(prompt: str, anchor_id: str) -> str:
    pattern = (
        r"\[EVIDENCE\b[^\]]*required=true[^\]]*id="
        + re.escape(anchor_id)
        + r"[^\]]*\].*?\[/EVIDENCE\]\n?"
    )
    stripped, n = re.subn(pattern, "", prompt, flags=re.DOTALL)
    if n != 1:
        raise AssertionError(f"expected to strip 1 block for {anchor_id}, stripped {n}")
    return stripped


def main() -> int:
    seat = seat_from_mapping(
        {
            "seat_id": "reviewer-fixture",
            "role": {
                "id": "analyst",
                "identity": "You are the cost analyst.",
                "elaboration": "Be terse.",
            },
            "partition": {
                "id": "P-A",
                "body": "Partition body CANARY_A",
            },
            "task": "Weigh ANCHOR_COST and ANCHOR_RISK.",
            "filler": "optional color text here",
            "history": [
                {"turn_index": 0, "text": "old history turn"},
                {"turn_index": 1, "text": "newer history turn"},
            ],
            "evidence": [
                {
                    "id": "ANCHOR_COST",
                    "required": True,
                    "body": "Cost figure forty two.",
                },
                {
                    "id": "ANCHOR_RISK",
                    "required": True,
                    "body": "Risk row seven.",
                },
                {
                    "id": "OPT_NOTE",
                    "required": False,
                    "body": "skippable aside",
                },
            ],
            "budget_tokens": 10**6,
        }
    )
    required = list(seat.required_anchor_ids())
    good = assemble_seat(seat)

    # Detector positive control: the check must find a known-present token
    # before silence is treated as retention.
    present = present_required_ids(good.prompt)
    if "ANCHOR_COST" not in present or "ANCHOR_RISK" not in present:
        return fail(f"detector missed a planted required block: {sorted(present)}")
    silent = retention_check(good.prompt, required)
    if silent.fired:
        return fail(f"retention fired on the good twin: {silent.missing}")

    stripped = strip_required_block(good.prompt, "ANCHOR_COST")
    # Leave a prose mention so a naive substring search could be fooled.
    poisoned = stripped + "\nPlease still weigh ANCHOR_COST in this paragraph."
    if "ANCHOR_COST" not in poisoned:
        return fail("prose mention missing; negative control would be vacuous")
    if "[EVIDENCE required=true id=ANCHOR_COST" in poisoned:
        return fail("required block still present after strip")

    fired = retention_check(poisoned, required)
    if not fired.fired:
        return fail("retention check silent after required anchor eviction")
    if "ANCHOR_COST" not in fired.missing:
        return fail(f"missing did not name ANCHOR_COST: {fired.missing}")
    if "ANCHOR_RISK" not in fired.survived:
        return fail("unstripped sibling anchor did not survive")

    # Twin control in the same run: the unstripped prompt stays silent.
    if retention_check(good.prompt, required).fired:
        return fail("good twin flipped after the stripped check")

    payload = {
        "probe": "probe2-anchor-retention",
        "unit_id": "IMP-0338",
        "independent": True,
        "starts_from_tests": True,
        "detector_found_planted_anchor": True,
        "good_twin_fired": False,
        "stripped_anchor": "ANCHOR_COST",
        "stripped_fired": True,
        "prose_mention_does_not_satisfy": True,
        "survived_sibling": list(fired.survived),
        "missing": list(fired.missing),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "retention_fired=True stripped=ANCHOR_COST "
        f"survived={list(fired.survived)} detector_positive=True"
    )
    print(
        "SUCCESS:IMP-0338-probe2 retention check fires when a required "
        "anchor is evicted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
