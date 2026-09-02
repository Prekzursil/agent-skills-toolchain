#!/usr/bin/env python3
"""Probe 1: unmet-obligation fails; unused permission does not.

Also records the v1 conflated bag-checker on the same seats so the
discrimination is not a one-sided story, and fires on a denied right.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import role_check as RC  # noqa: E402

FIX = HERE / "fixtures"


def codes(findings: list[dict]) -> list[str]:
    return [f["code"] + ":" + f["id"] for f in findings]


def main() -> int:
    catalogue = RC.load_json(FIX / "catalogue.json")
    critic = RC.role_by_id(catalogue, "critic")
    v1 = RC.load_json(FIX / "v1_critic_conflated.json")

    unused = RC.load_json(FIX / "seat_unused_permission.json")
    unmet = RC.load_json(FIX / "seat_unmet_obligation.json")
    denied = RC.load_json(FIX / "seat_denied_right.json")
    good = RC.load_json(FIX / "seat_good.json")

    f_unused = RC.check_seat(critic, unused)
    f_unmet = RC.check_seat(critic, unmet)
    f_denied = RC.check_seat(critic, denied)
    f_good = RC.check_seat(critic, good)

    v1_unused = RC.v1_conflated_check(v1, unused)
    v1_unmet = RC.v1_conflated_check(v1, unmet)

    overlap = RC.overlapping_ids(critic)

    # Negative control, recorded verbatim.
    negative_control = (
        "NEGATIVE CONTROL: on seat_unused_permission.json the only unused grant "
        "is permission consult_web. v2 role_check must return [] (must not treat "
        "an unused permission as UNMET_OBLIGATION). On seat_unmet_obligation.json "
        "the same checker must return UNMET_OBLIGATION:emit_critique. A checker "
        "that is silent on both, or that fails both, has conflated the two."
    )

    unused_ok = f_unused == []
    unmet_ok = codes(f_unmet) == ["UNMET_OBLIGATION:emit_critique"]
    denied_ok = codes(f_denied) == ["DENIED_RIGHT:vote"]
    good_ok = f_good == []
    overlap_ok = overlap == []

    # v1 bag-checker MUST fail the unused-permission seat (the conflation).
    v1_unused_fires = any(x["code"] == "UNMET_PERMISSIONS_BAG" for x in v1_unused)
    v1_unmet_fires = any(x["id"] == "emit_critique" for x in v1_unmet)

    print(f"v2 unused_permission findings={codes(f_unused)} expect=[]")
    print(f"v2 unmet_obligation findings={codes(f_unmet)} expect=[UNMET_OBLIGATION:emit_critique]")
    print(f"v2 denied_right findings={codes(f_denied)} expect=[DENIED_RIGHT:vote]")
    print(f"v2 known_good findings={codes(f_good)} expect=[]")
    print(f"v1 unused_permission findings={codes(v1_unused)} (must FIRE: conflated bag)")
    print(f"v1 unmet_obligation findings={codes(v1_unmet)}")
    print(f"critic overlapping grant ids={overlap}")
    print(negative_control)
    print(
        json.dumps(
            {
                "probe": "probe1-unmet-obligation-vs-unused-permission",
                "unit_id": "CNL-0022",
                "unused_permission_silent": unused_ok,
                "unmet_obligation_fires": unmet_ok,
                "denied_right_fires": denied_ok,
                "known_good_silent": good_ok,
                "v1_unused_permission_fires": v1_unused_fires,
                "v1_unmet_obligation_fires": v1_unmet_fires,
                "overlap_empty": overlap_ok,
            },
            sort_keys=True,
        )
    )

    ok = (
        unused_ok
        and unmet_ok
        and denied_ok
        and good_ok
        and v1_unused_fires
        and v1_unmet_fires
        and overlap_ok
    )
    if not ok:
        print("FAILED:CNL-0022-probe1 discriminator did not split obligation from permission")
        return 1
    print("SUCCESS:CNL-0022-probe1 unmet obligation fails; unused permission does not")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
