#!/usr/bin/env python3
"""Named probe 1: live package listing + clean-package both-states green."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import package_hygiene as ph  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0081-probe1 {msg}")
    return 1


def main() -> int:
    live = ph.pack_current_worktree(REPO)
    clean = ph.test_clean_package_passes()
    listing = live.as_dict()
    if live.file_count < 1:
        return _fail("live allowlisted payload was empty")
    if not live.ok:
        return _fail(f"live package gate red: {live.findings[:8]}")
    if live.total_uncompressed_bytes <= 0:
        return _fail("live package total bytes is zero")
    if live.headroom_bytes < 0:
        return _fail("live package already over ceiling")
    if not clean.get("pass"):
        return _fail(f"clean fixture did not pass: {clean}")
    if clean.get("gate_ok") is not True:
        return _fail("clean fixture gate_ok is not True")
    # Independent census: allowlisted files on disk must match archive members.
    cfg = ph.load_config()
    selected = ph.select_allowlisted(REPO, [str(g) for g in cfg["allowlist_globs"]])
    disk_names = sorted(rel for rel, _ in selected)
    zip_names = sorted(m.path for m in live.members if not m.is_dir)
    if disk_names != zip_names:
        return _fail(f"disk vs archive disagree disk={disk_names} zip={zip_names}")
    out = {
        "probe": "probe1-clean-listing",
        "unit_id": "TST-0081",
        "pass": True,
        "test_clean_package_passes": True,
        "live_gate_ok": True,
        "file_count": live.file_count,
        "total_uncompressed_bytes": live.total_uncompressed_bytes,
        "size_ceiling_bytes": live.size_ceiling_bytes,
        "headroom_bytes": live.headroom_bytes,
        "integrity_digest": live.integrity_digest,
        "package_id": live.package_id,
        "entries": listing["entries"],
        "top_ten_by_size": listing["top_ten_by_size"],
        "disk_archive_agree": True,
        "clean_fixture": {
            "file_count": clean["file_count"],
            "total_uncompressed_bytes": clean["total_uncompressed_bytes"],
            "headroom_bytes": clean["headroom_bytes"],
            "integrity_digest": clean["integrity_digest"],
        },
        "no_runtime_junk_workflow_present": (
            REPO / ".github" / "workflows" / "no-runtime-junk.yml"
        ).is_file(),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        f"files={live.file_count} bytes={live.total_uncompressed_bytes} "
        f"headroom={live.headroom_bytes} clean=PASS"
    )
    print("SUCCESS:TST-0081-probe1 live listing + clean package passes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
