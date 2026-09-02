#!/usr/bin/env python3
"""Probe 1: known-present found; known-absent sentinel returns 0 (both-states)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from discovery.local_repo import (  # noqa: E402
    discover_local,
    fetch_bytes,
    find_path,
    sha256_bytes,
)
from scenario import (  # noqa: E402
    KNOWN_PRESENT,
    LIVE_ARC_CONTROL,
    SENTINEL,
    plant_empty,
    plant_repo,
)


def fail(msg: str, payload: dict) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"FAILED:IMP-0150-probe1 {msg}")
    return 1


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="imp0150-p1-") as td:
        tmp = Path(td)
        home = tmp / "home"
        home.mkdir()
        planted = plant_repo(tmp / "repo", home, tmp / "linked")
        empty = plant_empty(tmp / "empty", home)

        found = discover_local(planted["root"])
        present_rows = find_path(found, KNOWN_PRESENT)
        sentinel_rows = find_path(found, SENTINEL)
        empty_rows = find_path(discover_local(empty["root"]), KNOWN_PRESENT)

        if len(present_rows) < 1:
            failures.append("planted known-present rtv-pdr.js not found")
        else:
            row = present_rows[0]
            independent = sha256_bytes((planted["root"] / KNOWN_PRESENT).read_bytes())
            via = sha256_bytes(fetch_bytes(planted["root"], row.access_method))
            if row.content_hash != independent or via != independent:
                failures.append(
                    f"hash mismatch planted={independent} row={row.content_hash} via={via}"
                )
            if row.access_method != KNOWN_PRESENT:
                failures.append(
                    f"worktree file must record bare path, got {row.access_method!r}"
                )
            if not (planted["root"] / KNOWN_PRESENT).is_file():
                failures.append("planted file missing from worktree")

        if sentinel_rows:
            failures.append(f"sentinel returned {len(sentinel_rows)} hits")
        if empty_rows:
            failures.append("empty-repo control found rtv-pdr.js (always-green detector)")

        live = discover_local(REPO)
        live_rtv = find_path(live, KNOWN_PRESENT)
        live_sentinel = find_path(live, SENTINEL)
        live_arc = find_path(live, LIVE_ARC_CONTROL)
        live_rtv_on_disk = (REPO / KNOWN_PRESENT).is_file()
        live_arc_on_disk = (REPO / LIVE_ARC_CONTROL).is_file()

        if live_sentinel:
            failures.append("live sentinel not zero")
        if live_rtv_on_disk and not live_rtv:
            failures.append("live rtv-pdr.js exists on disk but adapter missed it")
        if (not live_rtv_on_disk) and live_rtv:
            failures.append("adapter invented live rtv-pdr.js")
        if live_arc_on_disk and not live_arc:
            failures.append("live ARC known-present control missed")
        if (not live_arc_on_disk) and live_arc:
            failures.append("adapter invented live ARC control")

        payload = {
            "empty_known_present_hits": len(empty_rows),
            "failures": failures,
            "live_arc_control_found": bool(live_arc),
            "live_arc_on_disk": live_arc_on_disk,
            "live_rtv_pdr_found": bool(live_rtv),
            "live_rtv_pdr_on_disk": live_rtv_on_disk,
            "live_sentinel_hits": len(live_sentinel),
            "live_workflow_count": len(live),
            "pass": not failures,
            "planted_known_present_hits": len(present_rows),
            "planted_sentinel_hits": len(sentinel_rows),
            "probe": "probe1-known-present-absent",
            "unit_id": "IMP-0150",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if failures:
            print("FAILED:IMP-0150-probe1 " + "; ".join(failures))
            return 1
        print(
            "SUCCESS:IMP-0150-probe1 known-present found; "
            "sentinel=0; empty-control silent"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
