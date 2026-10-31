#!/usr/bin/env python3
"""TST-0197 probe 1: enumerator completes over a reserved-name tree, never a silent zero.

Detector control : a KNOWN-PRESENT ordinary file must be found before any count
                   is trusted.
Regression seed  : ntpath.relpath raises ValueError on the NUL device namespace
                   live; a swallow-all counter drops entries silently.
Subject          : enumerate_tree() never calls relpath, survives the tree,
                   reports every reserved basename present on disk.
"""
from __future__ import annotations
import json, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from enumerator import (  # noqa: E402
    dir_listing_count,
    enumerate_tree,
    nul_device_relpath_seed,
    naive_relpath_count,
)


def main() -> int:
    root = HERE / "fixtures" / "reserved-tree"
    if root.exists():
        shutil.rmtree(root)
    sys.path.insert(0, str(HERE))
    from fixture import plant_tree

    plant_tree(root)

    seed = nul_device_relpath_seed()
    result = enumerate_tree(root)
    ordinary_found = any(f["name"] == "readme.md" for f in result["files"])
    reserved_on_disk = {f["name"] for f in result["reserved_files"]}
    expected_reserved_planted = {"CON", "AUX", "PRN", "COM1", "LPT1"}
    naive = naive_relpath_count(root, swallow=False)

    checks = {
        "detector_control_ordinary_found": ordinary_found,
        "enumerator_complete_no_errors": result["errors"] == [] and result["file_count"] >= 8,
        "reserved_reported": expected_reserved_planted.issubset(reserved_on_disk),
        "no_silent_zero": result["file_count"] > 0,
        "never_relpath": result["relpath_calls"] == 0,
        "ntpath_seed_raises_live": isinstance(seed["ntpath_seed_raised"], str)
        and seed["ntpath_seed_raised"].startswith("ValueError")
        and "NUL" in seed["ntpath_seed_raised"],
        "posixpath_does_not_raise": seed["posixpath_raised"] is None,
        "naive_unswallowed_raises_on_device_seed": naive["raised"] is None or naive["count"] is not None,
    }
    out = {
        "probe": "probe1_enumerator_count",
        "unit": "TST-0197",
        "file_count": result["file_count"],
        "reserved_on_disk": sorted(reserved_on_disk),
        "ordinary_known_present_found": ordinary_found,
        "ntpath_seed_raised": seed["ntpath_seed_raised"],
        "posixpath_raised": seed["posixpath_raised"],
        "naive_relpath_result": naive,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe1_enumerator_count.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(root, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
