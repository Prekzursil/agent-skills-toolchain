#!/usr/bin/env python3
"""Probe 1: sentinel FIREs on today's line 175 before the fix and is SILENT after.

Also proves the live collision probe is not a constant: 31 on the pre-fix
architecture slice, 0 on the post-fix slice (CC-0021 live_shared_bare=0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))
sys.path.insert(0, str(HERE))

import build_fixtures  # noqa: E402
from decision_log_sentinel import scan  # noqa: E402
from option_id_collision_probe import collision_count, live_snapshot  # noqa: E402

BEFORE = HERE / "fixtures" / "decision-log-before.md"
AFTER = HERE / "fixtures" / "decision-log-after.md"
LIVE = REPO / "17-DECISION-LOG.md"
OPT = REPO / "command-center/option-id/07-OPTION-UNIVERSE.family-M-slice.md"
PRE = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.pre-fix-slice.md"
POST = REPO / "command-center/option-id/13-ARCHITECTURE-CANDIDATES.post-fix-slice.md"
OUT = HERE / "probe1-both-states.json"


def main() -> int:
    rc = build_fixtures.main()
    if rc != 0:
        print("FAILED:CC-0022-probe1 fixture build")
        return 1
    opt = OPT.read_text(encoding="utf-8")
    pre_n = collision_count(opt, PRE.read_text(encoding="utf-8"))
    post_n = collision_count(opt, POST.read_text(encoding="utf-8"))
    print(f"detector_control pre_collision={pre_n} post_collision={post_n}")
    if pre_n != 31:
        print(f"FAILED:CC-0022-probe1 expected pre-fix collision 31, got {pre_n}")
        return 1
    if post_n != 0:
        print(f"FAILED:CC-0022-probe1 expected post-fix collision 0, got {post_n}")
        return 1

    snap = live_snapshot(repo=REPO, option_path=OPT, arch_path=POST)
    if snap["collision_count"] != 0:
        print(f"FAILED:CC-0022-probe1 live collision_count={snap['collision_count']}")
        return 1
    if snap["option_family_m_count"] != 33:
        print(
            f"FAILED:CC-0022-probe1 option_family_m_count={snap['option_family_m_count']}"
        )
        return 1

    before = BEFORE.read_text(encoding="utf-8")
    after = AFTER.read_text(encoding="utf-8")
    before_lines = before.splitlines()
    line175 = before_lines[174]
    print(f"before_line_175={line175}")
    if "31-way option-id collision" not in line175 or "Queued as P2-09" not in line175:
        print("FAILED:CC-0022-probe1 line 175 is not the catalog collision claim")
        return 1
    if "MECH" in before:
        print("FAILED:CC-0022-probe1 before-log contains MECH")
        return 1
    if "MECH" not in after:
        print("FAILED:CC-0022-probe1 after-log missing MECH (namespace not reconciled)")
        return 1

    rb = scan(before, snapshot=snap, log_path=str(BEFORE))
    ra = scan(after, snapshot=snap, log_path=str(AFTER))
    fire_ids = [f.entry_id for f in rb.fires]
    print(
        f"before_fired={rb.fired} fire_ids={fire_ids} "
        f"skipped_superseded={rb.skipped_superseded}"
    )
    print(
        f"after_fired={ra.fired} after_fires={[f.entry_id for f in ra.fires]} "
        f"skipped_superseded={ra.skipped_superseded}"
    )
    if not rb.fired:
        print("FAILED:CC-0022-probe1 sentinel silent on before-log (measures nothing)")
        return 1
    if "DL-0042" not in fire_ids:
        print("FAILED:CC-0022-probe1 DL-0042 did not fire")
        return 1
    if "DL-0001" in fire_ids:
        print("FAILED:CC-0022-probe1 currently-true DL-0001 fired")
        return 1
    if ra.fired:
        print("FAILED:CC-0022-probe1 sentinel fired after reconcile")
        return 1
    if ra.skipped_superseded < 1:
        print("FAILED:CC-0022-probe1 after-log did not skip a SUPERSEDED entry")
        return 1

    live = LIVE.read_text(encoding="utf-8")
    rl = scan(live, snapshot=snap, log_path=str(LIVE))
    print(f"live_fired={rl.fired} live_skipped_superseded={rl.skipped_superseded}")
    if rl.fired:
        print("FAILED:CC-0022-probe1 live 17-DECISION-LOG.md still stale")
        return 1
    doc = {
        "ok": True,
        "pre_collision": pre_n,
        "post_collision": post_n,
        "before_fired": True,
        "after_fired": False,
        "before_fire_ids": fire_ids,
        "after_skipped_superseded": ra.skipped_superseded,
        "before_line_175": line175,
        "before_bytes": len(before.encode("utf-8")),
        "before_mech": False,
        "after_mech": True,
        "live_snapshot": snap,
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print("SUCCESS:CC-0022-probe1 both-states line-175 sentinel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
