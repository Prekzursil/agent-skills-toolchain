#!/usr/bin/env python3
"""Named probe 2: out-of-band observation + honesty of Windows limitation.

Signal 2 is process-table and filesystem (and listener-accept count) evidence
that forbidden side effects did not occur. Also grades documentation overclaim
and a symlink write escape attempt.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[3] / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

from exec_policy import WINDOWS_LIMITATION  # noqa: E402
from scenario import Scenario, oob_canary_pids, oob_path_exists  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "IMP-0064.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:IMP-0064-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0064":
        print("FAILED:IMP-0064-probe2 unit_id", doc.get("unit_id"))
        return 1
    lim = str(doc.get("windows_limitation") or "")
    if lim != WINDOWS_LIMITATION:
        print("FAILED:IMP-0064-probe2 receipt limitation != WINDOWS_LIMITATION constant")
        return 1
    if "Windows has no native OS-level process sandbox" not in lim:
        print("FAILED:IMP-0064-probe2 limitation missing Windows no-sandbox sentence")
        return 1
    c = doc.get("containment") or {}
    if c.get("os_process_sandbox") is True or c.get("windows_kernel_sandbox") is True:
        print("FAILED:IMP-0064-probe2 overclaim flags")
        return 1
    if str(c.get("mechanism") or "") != "userspace-intercept":
        print("FAILED:IMP-0064-probe2 mechanism mismatch")
        return 1
    lowered = lim.lower()
    for claim in (
        "provides an os process sandbox",
        "appcontainer isolates plugin scripts",
        "job-object containment is enabled",
    ):
        if claim in lowered:
            print("FAILED:IMP-0064-probe2 documentation overclaim:", claim)
            return 1

    sc = Scenario()
    try:
        spawn = sc.run_spawn()
        write = sc.run_write()
        net = sc.run_net()
        symlink = sc.run_symlink()
        time.sleep(0.25)
        pids = oob_canary_pids(sc.canary)
        marker = oob_path_exists(sc.marker)
        leaked = oob_path_exists(sc.forbid_file)
        via_link = oob_path_exists(sc.symlink_target)
        deny_accepts = sc.deny_l.accepted
    finally:
        sc.close()

    if not spawn.refused or pids or marker:
        print("FAILED:IMP-0064-probe2 OOB spawn side-effect", {"refused": spawn.refused, "pids": pids, "marker": marker})
        return 1
    if not write.refused or leaked:
        print("FAILED:IMP-0064-probe2 OOB write side-effect", {"refused": write.refused, "leaked": leaked})
        return 1
    if not net.refused or deny_accepts != 0:
        print("FAILED:IMP-0064-probe2 OOB network side-effect", {"refused": net.refused, "accepts": deny_accepts})
        return 1
    if not symlink.refused or via_link:
        print("FAILED:IMP-0064-probe2 symlink escape", {"refused": symlink.refused, "via_link": via_link})
        return 1

    summary = {
        "probe": "probe2-oob-honesty",
        "unit_id": "IMP-0064",
        "oob_canary_pids": pids,
        "oob_marker_exists": marker,
        "oob_forbidden_file_exists": leaked,
        "oob_deny_listener_accepts": deny_accepts,
        "symlink_escape_refused": True,
        "windows_limitation_matches_constant": True,
        "overclaim_grade": "PASS",
        "documentation_matches_tested_containment": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0064-probe2 oob observation and honesty grade")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
