#!/usr/bin/env python3
"""Probe 1: known-broken mis-register + both-states listing.

A directory listing cannot tell installed-and-loaded from installed-and-unloaded.
The runtime probe must fire when one contracted hook is mis-registered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from drill import run_broken_drill, run_clean_drill  # noqa: E402
from package_spec import MISREGISTER_EVENT  # noqa: E402


def main() -> int:
    clean = run_clean_drill()
    broken = run_broken_drill()
    listing_clean = clean["listing"]["pass"]
    listing_broken = broken["listing"]["pass"]
    paths_equal = clean["listing"]["paths"] == broken["listing"]["paths"]
    runtime_silent = clean["runtime"]["silent"]
    runtime_fired = broken["runtime"]["fired"]
    missing = broken["runtime"]["missing"]
    ok = (
        listing_clean
        and listing_broken
        and paths_equal
        and runtime_silent
        and runtime_fired
        and MISREGISTER_EVENT in missing
    )
    summary = {
        "listing_paths_identical": paths_equal,
        "listing_passes_broken": listing_broken,
        "listing_passes_clean": listing_clean,
        "misregister_event": MISREGISTER_EVENT,
        "missing_on_broken": missing,
        "pass": ok,
        "probe": "probe1-known-broken-both-states",
        "runtime_fired_on_broken": runtime_fired,
        "runtime_silent_on_clean": runtime_silent,
        "unit_id": "REL-0004",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"listing_clean={listing_clean} listing_broken={listing_broken} "
        f"paths_equal={paths_equal} silent_clean={runtime_silent} "
        f"fired_broken={runtime_fired} missing={missing}"
    )
    if not ok:
        print("FAILED:REL-0004-probe1 known-broken control or both-states listing")
        return 1
    print("SUCCESS:REL-0004-probe1 known-broken control and both-states listing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
