#!/usr/bin/env python3
"""Named probe 2: architecture-tournament preserves dissent (both-states).

Bad state: unanimous ballots with no minority record → REJECTED.
Good state: split ballots, or unanimous ballots plus a named minority record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from blueprints.tournament import finalize_verdict  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0239-probe2 {msg}")
    return 1


def main() -> int:
    unanimous = finalize_verdict(
        [
            {"choice": "hexagonal", "voter": "architect"},
            {"choice": "hexagonal", "voter": "pragmatist"},
            {"choice": "hexagonal", "voter": "critic"},
        ]
    )
    if unanimous.get("accepted") or unanimous.get("reason") != "unanimous-without-minority":
        return fail(f"unanimous without minority was not rejected: {unanimous}")

    split = finalize_verdict(
        [
            {"choice": "hexagonal", "voter": "architect"},
            {"choice": "hexagonal", "voter": "pragmatist"},
            {
                "choice": "event-sourced",
                "voter": "critic",
                "rationale": "write-path contention is the named failure domain",
            },
        ]
    )
    if not split.get("accepted") or not split.get("minority"):
        return fail(f"split ballots were not accepted with minority: {split}")

    recovered = finalize_verdict(
        [
            {"choice": "hexagonal", "voter": "architect"},
            {"choice": "hexagonal", "voter": "pragmatist"},
            {"choice": "hexagonal", "voter": "scribe"},
        ],
        minority_record={
            "position": "event-sourced",
            "rationale": "critic records the write-path contention counterexample",
            "voter": "critic",
        },
    )
    if not recovered.get("accepted"):
        return fail(f"unanimous with recorded dissent was rejected: {recovered}")

    echo = finalize_verdict(
        [
            {"choice": "hexagonal", "voter": "a"},
            {"choice": "hexagonal", "voter": "b"},
        ],
        minority_record={
            "position": "hexagonal",
            "rationale": "same as majority is not dissent",
            "voter": "echo",
        },
    )
    if echo.get("accepted"):
        return fail(f"majority-echo minority_record was accepted: {echo}")

    payload = {
        "probe": "probe2-tournament-dissent",
        "unit_id": "IMP-0239",
        "unanimous_rejected": True,
        "unanimous_reason": unanimous["reason"],
        "split_accepted": True,
        "split_minority": split["minority"],
        "recorded_dissent_accepted": True,
        "majority_echo_rejected": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "unanimous_rejected=True split_accepted=True "
        "recorded_dissent_accepted=True majority_echo_rejected=True"
    )
    print("SUCCESS:IMP-0239-probe2 architecture-tournament preserves dissent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
