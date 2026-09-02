#!/usr/bin/env python3
"""Named probe 2 (reviewer): scanner fires on a known-shared token and a leak.

Starts from the scanner contract, not from an author summary.

Detector control: a blue canary planted into a red prompt by construction
is found. Negative control: a clean red prompt is silent; after one token
is spliced in, the same scanner FIRES. Silence is trusted only after the
detector finds the planted shared token.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.topology.redblue import (  # noqa: E402
    deliberate_leak_fixture,
    known_shared_fixture,
    scan_cross_team_tokens,
    token_owner,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0284-probe2 {msg}")
    return 1


def main() -> int:
    blue_prompt, red_shared, shared = known_shared_fixture()
    if token_owner(shared) != "blue":
        return fail(f"known-shared token owner drifted: {shared}")
    if shared not in blue_prompt.text:
        return fail("known-shared token missing from blue huddle prompt")
    if shared not in red_shared.text:
        return fail("known-shared token missing from constructed red prompt")

    shared_hits = scan_cross_team_tokens([blue_prompt, red_shared])
    if not shared_hits:
        return fail("scanner silent on known-shared token")
    if not any(
        f.token == shared and f.prompt_team == "red" and f.owner_team == "blue"
        for f in shared_hits
    ):
        return fail(f"known-shared findings drifted: {[f.as_dict() for f in shared_hits]}")
    same_team = [f for f in shared_hits if f.prompt_team == "blue"]
    if same_team:
        return fail(f"scanner fired on same-team prompt: {same_team}")

    clean, leaked, leak_token = deliberate_leak_fixture()
    if leak_token in clean.text:
        return fail("clean twin already contained the leak token")
    silent = scan_cross_team_tokens([clean])
    if silent:
        return fail(f"clean twin fired: {[f.as_dict() for f in silent]}")
    if leak_token not in leaked.text:
        return fail("leak splice did not land")
    fired = scan_cross_team_tokens([leaked])
    if not fired:
        return fail("scanner silent after deliberate leak")
    if fired[0].token != leak_token or fired[0].prompt_team != "red":
        return fail(f"leak finding drifted: {fired[0].as_dict()}")
    if scan_cross_team_tokens([clean]):
        return fail("clean twin flipped after the leak check")

    payload = {
        "probe": "probe2-scanner-controls",
        "unit_id": "IMP-0284",
        "independent": True,
        "starts_from_tests": True,
        "detector_found_known_shared_token": True,
        "known_shared_token": shared,
        "known_shared_finding_count": len(shared_hits),
        "clean_twin_fired": False,
        "deliberate_leak_fired": True,
        "leaked_token": leak_token,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "known_shared_fired=True leak_fired=True clean_silent=True "
        f"shared_hits={len(shared_hits)}"
    )
    print(
        "SUCCESS:IMP-0284-probe2 scanner fires on known-shared token and "
        "deliberate leak"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
