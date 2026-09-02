#!/usr/bin/env python3
"""IMP-0289 probe 2: negative control, spec 11342 dissent-loss class.

Both-states:
- intact meta artifact: reachability PASSES
- drop one minority report: the SAME checker FAILS

A checker that always fails would pass a drop-only test; the intact
state is required to prove discrimination.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.topology.meta import (  # noqa: E402
    aggregate,
    check_reachability,
    collect_minority_ids,
    drop_minority_report,
    three_council_fixture,
)


def main() -> int:
    councils = three_council_fixture()
    expected = collect_minority_ids(councils)
    if len(expected) < 2:
        print("FAILED:IMP-0289-probe2 fixture too small to drop one report")
        return 1
    meta = aggregate(councils)
    intact = check_reachability(meta, expected)
    dropped_id = expected[0]
    mutated = drop_minority_report(meta, dropped_id)
    broken = check_reachability(mutated, expected)
    # Vacuity guard: a checker that ignores expected_ids and reads only
    # surviving objects would still pass. The missing id must be reported.
    missing = set(broken.get("missing_ids") or [])
    print(
        json.dumps(
            {
                "dropped_id": dropped_id,
                "intact_ok": intact.get("ok"),
                "intact_missing": intact.get("missing_ids"),
                "broken_ok": broken.get("ok"),
                "broken_missing": broken.get("missing_ids"),
                "spec": "11342 dissent-loss class / FC-11340",
                "fired_on_bad": broken.get("ok") is False and dropped_id in missing,
                "silent_on_good": intact.get("ok") is True,
            },
            sort_keys=True,
        )
    )
    if not intact.get("ok"):
        print("FAILED:IMP-0289-probe2 intact artifact already unreachable (vacuous detector)")
        return 1
    if broken.get("ok"):
        print("FAILED:IMP-0289-probe2 drop did not fail reachability")
        return 1
    if dropped_id not in missing:
        print(
            f"FAILED:IMP-0289-probe2 dropped {dropped_id} not in missing "
            f"{broken.get('missing_ids')}"
        )
        return 1
    print(
        "SUCCESS:IMP-0289-probe2 negative control dissent-loss: "
        f"intact ok, drop {dropped_id} fails reachability"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
