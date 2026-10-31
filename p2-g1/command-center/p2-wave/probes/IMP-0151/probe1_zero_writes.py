#!/usr/bin/env python3
"""IMP-0151 probe1: discover() is READ-ONLY. mtime/size/ino/sha256 snapshot of
the fixture tree is byte-equal before and after discover(); no file or
directory is created anywhere under the temp root during the run."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixtures  # noqa: E402


def snapshot(root: Path) -> dict[str, tuple]:
    """path -> (mtime_ns, size, ino, sha256) for every file."""
    out: dict[str, tuple] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            st = p.stat()
            out[p.relative_to(root).as_posix()] = (
                st.st_mtime_ns, st.st_size, st.st_ino,
                __import__("hashlib").sha256(p.read_bytes()).hexdigest(),
            )
    return out


def main() -> int:
    import adapter

    root, repo, live = fixtures.build_fixture()
    before = snapshot(root)
    before_paths = {str(p.relative_to(root)) for p in root.rglob("*")}

    report = adapter.discover(repo, live)

    after = snapshot(root)
    after_paths = {str(p.relative_to(root)) for p in root.rglob("*")}

    files_equal = before == after
    no_new = after_paths == before_paths
    counts = report["counts"]
    sane = counts["repo"] == 2 and counts["live"] == 2 and counts["shared"] == 1

    result = {
        "unit_id": "IMP-0151",
        "probe": "probe1-zero-writes",
        "files": len(before),
        "live_equal": files_equal,
        "host_created": sorted(after_paths - before_paths),
        "no_writes": no_new,
        "counts": counts,
        "pass": files_equal and no_new and sane,
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0151-probe1 discover() wrote nothing; tree snapshot equal before/after"
            if result["pass"] else
            "FAILED:IMP-0151-probe1 zero-writes contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
