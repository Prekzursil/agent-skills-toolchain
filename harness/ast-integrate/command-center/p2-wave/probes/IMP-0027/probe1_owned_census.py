#!/usr/bin/env python3
"""Probe 1: post-uninstall directory census — zero plugin-owned paths remain.

Instrument: Path.exists() over the projection owned set. Does not hash
foreign files (that is probe 2). A scorched-earth rmtree would also empty
this census; probe 2 must fail that case.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.census import owned_remaining  # noqa: E402
from plugin.scenario import seed_home  # noqa: E402
from plugin.uninstall import uninstall  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0027-p1-") as tmp:
        seed = seed_home(Path(tmp) / "home")
        before = [rel for rel in sorted(seed.projection.owned_relpaths()) if (seed.home / rel).exists()]
        if not before:
            print("FAILED:IMP-0027-probe1 no owned files were seeded")
            return 1
        uninstall(seed.home, seed.projection, purge_user_data=False)
        leftover = owned_remaining(seed.home, seed.projection)
        user_still = {
            rel: (seed.home / rel).is_file() for rel in seed.user_files
        }
        if leftover:
            print(f"FAILED:IMP-0027-probe1 owned remaining={leftover}")
            return 1
        if not all(user_still.values()):
            print(f"FAILED:IMP-0027-probe1 default uninstall removed user data {user_still}")
            return 1
        doc = {
            "pass": True,
            "probe": "probe1-owned-census",
            "unit_id": "IMP-0027",
            "owned_seeded": before,
            "owned_remaining": leftover,
            "user_data_still_present": user_still,
            "instrument": "path.exists over projection.owned_relpaths",
        }
        print(json.dumps(doc, sort_keys=True))
        print(
            f"owned_seeded={len(before)} owned_remaining=0 "
            f"user_data_retained={all(user_still.values())}"
        )
        print("SUCCESS:IMP-0027-probe1 post-uninstall owned-path census is empty")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
