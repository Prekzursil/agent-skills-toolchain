#!/usr/bin/env python3
"""Probe 1: every enumerated publishing entry point under binding PR-ONLY.

Independent signal (1): live invocation of each entry point returns
BLOCKED-NEEDS-OWNER, owner-approval request present, outbound log empty.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from pr_only_guard import (  # noqa: E402
    BLOCKED_NEEDS_OWNER,
    PUBLISHING_ENTRY_POINTS,
    outbound_log,
    reset_outbound_log,
)
from publishing import invoke, list_local, pack  # noqa: E402
from release_mode import BINDING_MODE  # noqa: E402

CFG = MKT / "fixtures" / "release-mode.pr-only.json"


def main() -> int:
    reset_outbound_log()
    rows = []
    fail = False
    for name in PUBLISHING_ENTRY_POINTS:
        result = invoke(name, {"pkg": "imp0112.probe1"}, config_path=str(CFG))
        ok = (
            result.get("status") == BLOCKED_NEEDS_OWNER
            and result.get("code") == BLOCKED_NEEDS_OWNER
            and result.get("release_mode") == BINDING_MODE
            and result.get("owner_approval_request", {}).get("required") is True
            and result.get("side_effects", {}).get("network") is False
            and result.get("side_effects", {}).get("recorded_outbound") is False
        )
        rows.append({"entry_point": name, "status": result.get("status"), "ok": ok})
        print(f"entry_point={name} status={result.get('status')} ok={ok}")
        if not ok:
            fail = True
            print(json.dumps(result, sort_keys=True)[:800])
    log_empty = outbound_log() == []
    print(f"outbound_log_empty={log_empty} n={len(outbound_log())}")
    if not log_empty:
        fail = True
    local_pack = pack("imp0112.probe1", config_path=str(CFG))
    local_list = list_local("imp0112.probe1", config_path=str(CFG))
    local_ok = (
        local_pack.get("status") == "PROCEEDED"
        and local_list.get("status") == "PROCEEDED"
        and outbound_log() == []
    )
    print(f"local_still_proceeds={local_ok}")
    if not local_ok:
        fail = True
    covered = [r["entry_point"] for r in rows]
    if covered != list(PUBLISHING_ENTRY_POINTS):
        print(f"FAILED:IMP-0112-probe1 coverage {covered}")
        return 1
    if fail or not all(r["ok"] for r in rows):
        print("FAILED:IMP-0112-probe1 entry points not all BLOCKED-NEEDS-OWNER")
        return 1
    print(
        json.dumps(
            {
                "probe": "probe1-entry-points",
                "unit_id": "IMP-0112",
                "entry_points": covered,
                "all_blocked": True,
                "outbound_log_empty": True,
                "local_still_proceeds": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0112-probe1 every publishing entry point BLOCKED-NEEDS-OWNER")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
