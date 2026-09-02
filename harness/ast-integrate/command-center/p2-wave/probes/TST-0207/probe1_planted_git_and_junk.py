#!/usr/bin/env python3
"""Probe 1: plant .git and a 200MiB junk file; allowlist packer must fail the build.

Both-states: the same allowlist packs a clean tree. A denylist mutant would
select junk.bin (denylist is FAIL by construction). Denylist configs are refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
sys.path.insert(0, str(HERE))

import pack as packer  # noqa: E402
from staging import (  # noqa: E402
    FIXTURE_ALLOWLIST,
    denylist_would_select,
    plant_git,
    plant_junk,
    write_clean,
)


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0207-probe1 {msg}")
    return 1


def main() -> int:
    try:
        packer.pack(
            Path("."),
            allowlist={
                "mode": "denylist",
                "globs": [".git/**", "*.log"],
                "size_ceiling_bytes": 1000,
                "on_ceiling_exceeded": "fail",
            },
        )
        return _fail("denylist mode was not refused")
    except packer.PackError as exc:
        denylist_refused = "denylist" in str(exc).lower()
        if not denylist_refused:
            return _fail(f"unexpected PackError for denylist: {exc}")

    with tempfile.TemporaryDirectory(prefix="tst0207-p1-") as tmp:
        tmp_path = Path(tmp)
        clean = tmp_path / "clean"
        dirty = tmp_path / "dirty"
        clean.mkdir()
        dirty.mkdir()
        write_clean(clean)
        write_clean(dirty)
        git_paths = plant_git(dirty)
        junk = plant_junk(dirty)

        clean_zip = tmp_path / "clean.zip"
        dirty_zip = tmp_path / "dirty.zip"
        good = packer.pack(clean, dest=clean_zip, allowlist=FIXTURE_ALLOWLIST)
        bad = packer.pack(dirty, dest=dirty_zip, allowlist=FIXTURE_ALLOWLIST)

        extra_names = {row["path"] for row in bad.extra_paths}
        git_named = all(p in extra_names for p in git_paths)
        junk_row = next((r for r in bad.extra_paths if r["path"] == junk["path"]), None)
        denylist_selects_junk = denylist_would_select(junk["path"])
        denylist_drops_git = not denylist_would_select(".git/HEAD")
        allowlist_selects_junk = packer.allowlisted(junk["path"], FIXTURE_ALLOWLIST["globs"])

        payload = {
            "probe": "probe1-planted-git-and-junk",
            "unit_id": "TST-0207",
            "pass": False,
            "denylist_config_refused": True,
            "clean": good.as_dict(),
            "dirty": bad.as_dict(),
            "git_paths_named": git_named,
            "junk_named": junk_row is not None,
            "junk_bytes": junk["bytes"],
            "dirty_archive_absent": not dirty_zip.exists(),
            "clean_archive_present": clean_zip.is_file(),
            "denylist_mutant_would_select_junk": denylist_selects_junk,
            "denylist_mutant_would_drop_git": denylist_drops_git,
            "allowlist_does_not_match_junk": allowlist_selects_junk is False,
            "policy": "allowlist",
        }

        if not good.ok:
            return _fail(f"clean tree failed pack: {good.reasons}")
        if not clean_zip.is_file():
            return _fail("clean pack did not emit an archive")
        if bad.ok:
            return _fail("dirty tree pack succeeded; detector silent")
        if dirty_zip.exists():
            return _fail("dirty pack emitted an archive")
        if not git_named:
            return _fail(f".git paths not named in extras: {sorted(extra_names)}")
        if junk_row is None:
            return _fail(f"junk.bin not named in extras: {sorted(extra_names)}")
        if int(junk_row["bytes"]) != junk["bytes"]:
            return _fail("junk.bin size mismatch")
        if junk["bytes"] < 200 * 1024 * 1024:
            return _fail("junk.bin is under 200MiB")
        if not denylist_selects_junk:
            return _fail("denylist mutant would not select junk.bin; control is vacuous")
        if not denylist_drops_git:
            return _fail("denylist mutant did not drop .git; control is vacuous")
        if allowlist_selects_junk:
            return _fail("allowlist matched junk.bin")
        if "non-allowlisted paths" not in " ".join(bad.reasons):
            return _fail(f"reasons missing extra-path clause: {bad.reasons}")

        payload["pass"] = True
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            "clean=PASS dirty=FAIL git_named=1 junk_named=1 "
            f"junk_bytes={junk['bytes']} denylist_would_ship_junk=1"
        )
        print("SUCCESS:TST-0207-probe1 planted .git and 200MiB junk fail allowlist pack")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
