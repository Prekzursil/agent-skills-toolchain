#!/usr/bin/env python3
"""Probe 2: every README and quick-start command in a clean-room published prefix."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import run_live_docs  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0250-probe2 {msg}")
    return 1


def main() -> int:
    live = run_live_docs()
    if live.get("readme_count", 0) < 1:
        return fail("README contributed no extracted commands")
    if live.get("quickstart_count", 0) < 1:
        return fail("quickstart contributed no extracted commands")
    if not live.get("all_attempted"):
        return fail(
            f"not every extracted command was attempted "
            f"extracted={live.get('extracted_count')} attempted={live.get('attempted_count')}"
        )
    if not live.get("all_explained"):
        return fail(f"unexplained nonzero {live.get('unexplained_nonzero')}")
    if live.get("origin") != "wheel":
        return fail(f"origin {live.get('origin')!r}")
    if not live.get("pass"):
        return fail(json.dumps(live, sort_keys=True)[:2000])

    print(
        json.dumps(
            {
                "all_attempted": live["all_attempted"],
                "all_explained": live["all_explained"],
                "attempted_count": live["attempted_count"],
                "exit_codes": live["exit_codes"],
                "extracted_count": live["extracted_count"],
                "origin": live["origin"],
                "pass": True,
                "probe": "probe2-clean-room-published-artifact",
                "quickstart_count": live["quickstart_count"],
                "readme_count": live["readme_count"],
                "unit_id": "TST-0250",
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0250-probe2 all README and quick-start commands attempted "
        "in a clean room against the published wheel; every exit code recorded"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
