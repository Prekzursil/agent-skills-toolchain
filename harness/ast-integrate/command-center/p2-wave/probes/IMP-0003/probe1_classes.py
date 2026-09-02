#!/usr/bin/env python3
"""IMP-0003 probe 1: one finding per forbidden class + empty-tree control.

Signal 1: scanner exit code and named-path report against a fixture tree that
plants every forbidden path role. The empty-tree leg must be clean AND the
same run must report the planted-item control as FOUND.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import forbidden_scan as fs  # noqa: E402

REQUIRED_CLASSES = (
    fs.CLASS_GIT_DIR,
    fs.CLASS_GITLINK,
    fs.CLASS_NODE_MODULES,
    fs.CLASS_PYCACHE,
    fs.CLASS_LOG,
    fs.CLASS_TRANSCRIPT_JSONL,
    fs.CLASS_OS_CACHE,
    fs.CLASS_OVERSIZE,
)


def _write(root: Path, rel: str, body: bytes = b"ok\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)


def _mkdir(root: Path, rel: str) -> None:
    (root / rel).mkdir(parents=True, exist_ok=True)


def build_dirty_tree(root: Path) -> dict[str, str]:
    """Plant one path per forbidden class. Returns class -> planted relpath."""
    planted = {
        fs.CLASS_GIT_DIR: ".git/HEAD",
        fs.CLASS_GITLINK: "vendor/dep/.git",
        fs.CLASS_NODE_MODULES: "app/node_modules/leftpad/index.js",
        fs.CLASS_PYCACHE: "pkg/__pycache__/mod.cpython-312.pyc",
        fs.CLASS_LOG: "var/build.log",
        fs.CLASS_TRANSCRIPT_JSONL: "sessions/run-1.jsonl",
        fs.CLASS_OS_CACHE: "assets/.DS_Store",
        fs.CLASS_OVERSIZE: "huge.bin",
    }
    _write(root, planted[fs.CLASS_GIT_DIR], b"ref: refs/heads/main\n")
    _write(root, planted[fs.CLASS_GITLINK], b"gitdir: ../../.git/modules/dep\n")
    _write(root, planted[fs.CLASS_NODE_MODULES], b"module.exports=1\n")
    _write(root, planted[fs.CLASS_PYCACHE], b"\0pyc")
    _write(root, planted[fs.CLASS_LOG], b"logline\n")
    _write(root, planted[fs.CLASS_TRANSCRIPT_JSONL], b"{}\n")
    _write(root, planted[fs.CLASS_OS_CACHE], b"ds")
    _mkdir(root, "bundle/__MACOSX")
    _write(root, "bundle/__MACOSX/._junk", b"x")
    _write(root, planted[fs.CLASS_OVERSIZE], b"x" * 200)
    _write(root, "keep/readme.txt", b"payload\n")
    _write(root, "data/events.jsonl", b"{}\n")  # must NOT be classified as transcript
    return planted


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0003-p1-") as tmp:
        tmp_path = Path(tmp)
        empty = tmp_path / "empty"
        dirty = tmp_path / "dirty"
        empty.mkdir()
        dirty.mkdir()
        planted = build_dirty_tree(dirty)

        empty_report = fs.scan(empty, max_file_bytes=100)
        dirty_report = fs.scan(dirty, max_file_bytes=100)

    if empty_report["outcome"] != "clean" or empty_report["exit_code"] != 0:
        print("FAILED:IMP-0003-probe1 empty tree was not clean", json.dumps(empty_report["staging"]))
        return 1
    if empty_report["control"]["found"] is not True or empty_report["control"]["planted"] is not True:
        print("FAILED:IMP-0003-probe1 empty-tree control not FOUND")
        return 1
    if empty_report["trusted"] is not True:
        print("FAILED:IMP-0003-probe1 empty-tree verdict was not trusted")
        return 1
    if empty_report["staging"]["path_count"] != 0 or empty_report["staging"]["findings"]:
        print("FAILED:IMP-0003-probe1 empty tree was not empty")
        return 1

    if dirty_report["outcome"] != "blocked" or dirty_report["exit_code"] != 1:
        print("FAILED:IMP-0003-probe1 dirty tree was not blocked")
        return 1
    if dirty_report["control"]["found"] is not True:
        print("FAILED:IMP-0003-probe1 dirty-tree control not FOUND (detector failure)")
        return 1

    found_classes = {f["class"] for f in dirty_report["staging"]["findings"]}
    missing = [c for c in REQUIRED_CLASSES if c not in found_classes]
    if missing:
        print(f"FAILED:IMP-0003-probe1 missing classes {missing}")
        return 1

    named = {c: [f["path"] for f in dirty_report["staging"]["findings"] if f["class"] == c] for c in REQUIRED_CLASSES}
    if not any(p == ".git" or p.startswith(".git/") for p in named[fs.CLASS_GIT_DIR]):
        print("FAILED:IMP-0003-probe1 git_dir path not named")
        return 1
    if planted[fs.CLASS_GITLINK] not in named[fs.CLASS_GITLINK]:
        print("FAILED:IMP-0003-probe1 gitlink path not named")
        return 1
    if "app/node_modules" not in named[fs.CLASS_NODE_MODULES]:
        print("FAILED:IMP-0003-probe1 node_modules path not named")
        return 1
    if "pkg/__pycache__" not in named[fs.CLASS_PYCACHE]:
        print("FAILED:IMP-0003-probe1 pycache path not named")
        return 1
    if planted[fs.CLASS_LOG] not in named[fs.CLASS_LOG]:
        print("FAILED:IMP-0003-probe1 log path not named")
        return 1
    if planted[fs.CLASS_TRANSCRIPT_JSONL] not in named[fs.CLASS_TRANSCRIPT_JSONL]:
        print("FAILED:IMP-0003-probe1 transcript jsonl path not named")
        return 1
    if "data/events.jsonl" in named[fs.CLASS_TRANSCRIPT_JSONL]:
        print("FAILED:IMP-0003-probe1 events.jsonl falsely classified as transcript")
        return 1
    if planted[fs.CLASS_OS_CACHE] not in named[fs.CLASS_OS_CACHE] or "bundle/__MACOSX" not in named[fs.CLASS_OS_CACHE]:
        print("FAILED:IMP-0003-probe1 os_cache path not named")
        return 1
    if planted[fs.CLASS_OVERSIZE] not in named[fs.CLASS_OVERSIZE]:
        print("FAILED:IMP-0003-probe1 oversize path not named")
        return 1

    out = {
        "probe": "probe1-classes-and-control",
        "unit_id": "IMP-0003",
        "pass": True,
        "empty_clean": True,
        "empty_control_found": True,
        "dirty_blocked": True,
        "dirty_control_found": True,
        "classes_named": sorted(found_classes),
        "named_paths": named,
        "classifier": "path-role",
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0003-probe1 class coverage and empty-tree planted control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
