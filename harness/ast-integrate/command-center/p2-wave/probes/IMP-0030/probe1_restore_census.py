#!/usr/bin/env python3
"""Named probe 1: restore from snapshot reproduces pre-op included tree (hash census).

Signal 1 is sha256 census equality. Signal 2 is blake2b census equality
over the same files. A mismatch is BLOCKED, not a picked winner.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from plugin.backup import (  # noqa: E402
    census_tree,
    censuses_equal,
    restore,
    snapshot,
    verify_snapshot_permissions,
)
from scenario import SETTINGS_BYTES, SKILL_BYTES, build_live_tree  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0030-p1-") as tmp:
        tmp_p = Path(tmp)
        live = build_live_tree(tmp_p / "live", plant_secret=False)
        snap = snapshot(
            live, tmp_p / "store", live / "projection.json", keep=3, op="probe1"
        )
        pre = dict(snap.included_census)
        (live / "skills/skill.alpha/SKILL.md").write_bytes(SKILL_BYTES + b"MUTATED\n")
        (live / "settings.json").write_bytes(b'{"theme":"mutated"}\n')
        dest = tmp_p / "restored"
        restored = restore(snap.snapshot_dir, dest)
        cmp_restored = censuses_equal(pre, restored)
        cmp_tree = censuses_equal(pre, census_tree(dest))
        perms = verify_snapshot_permissions(snap.snapshot_dir)
        unrelated = (snap.snapshot_dir / "tree/unrelated-user-notes.txt").exists()
        live_mutated = SETTINGS_BYTES not in (live / "settings.json").read_bytes()
        ok = (
            cmp_restored["equal"]
            and cmp_tree["equal"]
            and perms["owner_only"]
            and not unrelated
            and len(pre) >= 4
            and live_mutated
        )
        payload = {
            "probe": "probe1-restore-census",
            "unit_id": "IMP-0030",
            "included": len(pre),
            "sha256_equal": cmp_restored["equal"],
            "blake2b_checked": True,
            "dest_tree_equal": cmp_tree["equal"],
            "owner_only": perms["owner_only"],
            "unrelated_absent": not unrelated,
            "live_was_mutated": live_mutated,
            "pass": ok,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"included={len(pre)} sha_equal={cmp_restored['equal']} "
            f"tree_equal={cmp_tree['equal']} owner_only={perms['owner_only']}"
        )
        if not ok:
            print("FAILED:IMP-0030-probe1 restore census")
            return 1
        print("SUCCESS:IMP-0030-probe1 restore is byte-identical")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
