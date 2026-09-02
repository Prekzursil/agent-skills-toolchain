#!/usr/bin/env python3
"""Probe 1: seed is recorded in the receipt; missing-seed gate fires (both-states).

Also: planted AST census distinguishes a recording suite from a discarding one,
and a live census lists which existing RNG sites currently discard their seed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from testinfra.test_seed_replay import (  # noqa: E402
    live_census,
    test_seed_is_recorded_in_the_receipt,
)


def main() -> int:
    recorded = test_seed_is_recorded_in_the_receipt()
    census = live_census(REPO)
    payload = {
        "probe": "probe1-seed-recorded",
        "unit_id": "TST-0027",
        "test_seed_is_recorded_in_the_receipt": recorded,
        "census": {
            "live_count": census["live_count"],
            "live_records_seed": census["live_records_seed"],
            "live_discards_seed": census["live_discards_seed"],
            "live_seed_in_api_not_in_result": census["live_seed_in_api_not_in_result"],
            "named_property_fuzz_chaos_suites_on_tree": census[
                "named_property_fuzz_chaos_suites_on_tree"
            ],
            "planted": census["planted"],
        },
        "pass": recorded["pass"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not recorded["pass"]:
        print("FAILED:TST-0027-probe1 seed is not recorded in the receipt")
        return 1
    print(
        "SUCCESS:TST-0027-probe1 seed recorded; missing-seed gate fires; "
        f"live discards={len(census['live_discards_seed'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
