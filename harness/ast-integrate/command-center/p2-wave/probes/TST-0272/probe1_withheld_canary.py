#!/usr/bin/env python3
"""Named probe 1: withheld canary is absent from the partitioned seat's readable set.

Plants a unique token in B-WITHHELD and greps every artifact seat-a can read.
Zero hits is reported with the token id and every path searched. Privileged
seat-b must still see the token (both-states). Detector control: the same
token planted in B-ALLOWED is found by the same search.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.partition import (  # noqa: E402
    DETECTOR_CONTROL,
    HONEST,
    SEAT_A,
    SEAT_B,
    require_real_search,
    run_fixture,
    search_seat,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0272-probe1 {msg}")
    return 1


def main() -> int:
    honest = run_fixture(HONEST)
    token = honest.withheld_canary
    partitioned = search_seat(SEAT_A, token, honest.artifacts)
    privileged = search_seat(SEAT_B, token, honest.artifacts)
    try:
        require_real_search(partitioned)
        require_real_search(privileged)
    except Exception as exc:  # noqa: BLE001
        return fail(f"search not attributable: {exc}")

    if partitioned.hit_count != 0:
        return fail(f"withheld token leaked to seat-a: {partitioned.as_dict()}")
    if "seat-a/prompt" not in partitioned.paths_searched:
        return fail("seat-a/prompt was not searched")
    if privileged.hit_count < 1:
        return fail("privileged seat-b did not see withheld token (search is blind)")
    if "seat-b/prompt" not in {h.path for h in privileged.hits}:
        return fail("privileged hit set missing seat-b/prompt")

    control = run_fixture(DETECTOR_CONTROL)
    if control.withheld_canary != token:
        return fail("detector-control minted a different withheld token")
    found = search_seat(SEAT_A, token, control.artifacts)
    try:
        require_real_search(found)
    except Exception as exc:  # noqa: BLE001
        return fail(f"detector-control search not attributable: {exc}")
    if found.hit_count < 1:
        return fail("detector control silent: same token in ALLOWED was not found")
    found_paths = {h.path for h in found.hits}
    if "seat-a/prompt" not in found_paths:
        return fail(f"detector control missed prompt: {found.as_dict()}")

    payload = {
        "probe": "probe1-withheld-canary",
        "unit_id": "TST-0272",
        "canary_token": token,
        "honest_paths_searched": list(partitioned.paths_searched),
        "honest_path_count": len(partitioned.paths_searched),
        "honest_hit_count": partitioned.hit_count,
        "privileged_hit_count": privileged.hit_count,
        "detector_control_hit_count": found.hit_count,
        "detector_control_hit_paths": sorted(found_paths),
        "forced_moderator_summary": bool(honest.notes.get("forced_moderator_summary")),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, indent=1))
    print(
        f"canary={token} searched={len(partitioned.paths_searched)} "
        f"honest_hits=0 privileged_hits={privileged.hit_count} "
        f"detector_hits={found.hit_count}"
    )
    print("SUCCESS:TST-0272-probe1 withheld canary zero hits; detector control found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
