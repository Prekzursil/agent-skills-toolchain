#!/usr/bin/env python3
"""Probe 1: hostile fixture enumerates without exception; class controls fire."""
from __future__ import annotations

import json
import os
import os.path as ospath
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import enumerator as E  # noqa: E402
import fixture as F  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAIL:BLD-0003-probe1 {msg}")
    return 1


def main() -> int:
    # Historical crash: os.path.relpath on a NUL path. If the enumerator still
    # calls relpath, this patch turns it into a loud failure on Linux too.
    def boom(*_a, **_k):
        raise ValueError("path is on mount '\\\\.\\NUL'")

    ospath.relpath = boom  # type: ignore[method-assign]
    os.path.relpath = boom  # type: ignore[method-assign]

    planted = F.plant()
    root = Path(planted["root"])
    snap = E.census(root)
    if not snap.get("completed_without_exception"):
        return _fail("enumerator did not complete")

    by = snap["by_class"]
    counts = snap["counts"]

    reserved_hits = [r["path"] for r in by["WIN_RESERVED"] if r["path"] == planted["reserved"]]
    if not reserved_hits:
        return _fail(f"reserved file missing from WIN_RESERVED: {planted['reserved']}")

    long_hits = [r["path"] for r in by["LONG_PATH"] if r["path"] == planted["long_path"]]
    if not long_hits:
        return _fail("long path missing from LONG_PATH")
    if len(planted["long_path"]) <= 260:
        return _fail(f"planted long path not >260 chars: {len(planted['long_path'])}")

    bin_hits = [r["path"] for r in by["BINARY"] if r["path"] == planted["binary"]]
    if not bin_hits:
        return _fail("non-UTF8 blob missing from BINARY")

    enc_hits = [r["path"] for r in by["ENCRYPTED"] if r["path"] == planted["encrypted"]]
    if not enc_hits:
        return _fail("git-crypt fixture missing from ENCRYPTED")
    enc_also_binary = [
        r["path"] for r in by["BINARY"] if r["path"] == planted["encrypted"]
    ]
    if enc_also_binary:
        return _fail("git-crypt file classified BINARY (must be ENCRYPTED, not BINARY)")

    control = planted["control"]
    for cls, rows in by.items():
        if any(r["path"] == control for r in rows):
            return _fail(f"UTF-8 control {control} appeared in class {cls}")

    oversized = [r["path"] for r in by["OVERSIZED"] if r["path"] == planted["oversized"]]
    if not oversized:
        return _fail("oversized fixture missing from OVERSIZED")

    ignored = [r["path"] for r in by["GITIGNORED"] if r["path"] == planted["gitignored"]]
    if not ignored:
        return _fail("gitignored fixture missing from GITIGNORED")

    out = {
        "probe": "probe1-hostile-fixture",
        "unit_id": "BLD-0003",
        "completed_without_exception": True,
        "relpath_patched_to_raise": True,
        "files_seen": snap["files_seen"],
        "counts": counts,
        "reserved_hit": True,
        "long_path_hit": True,
        "binary_hit": True,
        "encrypted_not_binary": True,
        "utf8_control_absent_from_classes": True,
        "oversized_hit": True,
        "gitignored_hit": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "hostile_ok=True reserved=True long_path=True binary=True "
        "encrypted_not_binary=True utf8_control_clean=True"
    )
    print("SUCCESS:BLD-0003-probe1 hostile fixture enumerated without exception")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
