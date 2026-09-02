#!/usr/bin/env python3
"""Probe 1: six archetypes + missing-expertise seating + visible owner override.

Membership check: expected role is present in the auto roster. Mechanically
this is set inclusion on compose().roles, not a reason-string inspection
(that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.participants.select_auto import (  # noqa: E402
    apply_owner_override,
    compose,
    roles_of,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0267-probe1 {msg}")
    return 1


def load_fixtures() -> dict:
    return json.loads((HERE / "fixtures.json").read_text(encoding="utf-8"))


def main() -> int:
    fx = load_fixtures()
    archetypes = fx["archetypes"]
    if len(archetypes) != 6:
        return fail(f"archetype-count={len(archetypes)} want=6")

    rows = []
    for item in archetypes:
        comp = compose(item["task"])
        roles = roles_of(comp)
        expected = item["expected_role"]
        present = expected in roles
        rows.append(
            {
                "id": item["id"],
                "expected_role": expected,
                "present": present,
                "roles": sorted(roles),
                "seat_count": comp["seat_count"],
            }
        )
        print(
            f"archetype {item['id']} expected={expected} present={present} "
            f"roles={sorted(roles)} seats={comp['seat_count']}"
        )
        if not present:
            return fail(f"{item['id']} missing {expected}")
        if comp["seat_count"] != len(comp["seats"]):
            return fail(f"{item['id']} seat_count mismatch")

    missing = fx["missing_expertise"]
    miss_comp = compose(missing["task"])
    miss_roles = roles_of(miss_comp)
    if missing["expected_role"] not in miss_roles:
        return fail(
            f"missing-expertise did not seat {missing['expected_role']}: {sorted(miss_roles)}"
        )
    print(
        f"missing_expertise {missing['id']} seated={missing['expected_role']} "
        f"roles={sorted(miss_roles)}"
    )

    overridden = apply_owner_override(
        miss_comp,
        [
            {
                "action": "remove",
                "role": "legal",
                "owner_reason": "outside counsel already retained for the subpoena",
            }
        ],
    )
    over_roles = roles_of(overridden)
    if "legal" in over_roles:
        return fail("owner-remove legal left legal seated (silent ignore)")
    log = overridden.get("owner_overrides") or []
    if not log:
        return fail("owner override produced no log")
    entry = log[0]
    if entry.get("auto_had_role") is not True:
        return fail("override log did not record that auto had seated legal")
    if entry.get("result") != "removed":
        return fail(f"override result={entry.get('result')}")
    if entry.get("visible") is not True:
        return fail("override not marked visible")
    if not entry.get("auto_reason"):
        return fail("override dropped the auto reason")
    # No silent substitute: legal gone, nothing new pretending to be legal.
    if any("legal" in r for r in over_roles):
        return fail(f"legal substitute appeared: {sorted(over_roles)}")
    print(
        f"owner_override removed legal auto_had_role=True remaining={sorted(over_roles)}"
    )

    summary = {
        "archetypes": rows,
        "missing_expertise_seated": True,
        "owner_override_visible": True,
        "owner_remove_no_substitute": True,
        "pass": True,
        "probe": "probe1-archetypes",
        "unit_id": "IMP-0267",
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0267-probe1 six archetypes and missing-expertise legal seat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
