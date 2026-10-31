#!/usr/bin/env python3
"""IMP-0003 probe 2: independent census, git-rule mutation, reviewer plant.

Signal 2 is an out-of-band find/du census of the same tree, computed by a
different script than the scanner. Disagreement is a detector failure.

Also: delete the .git rule and prove the git_dir case goes red; plant a
forbidden path the per-class fixture did not use and confirm the scanner fires.
"""
from __future__ import annotations

import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import census as census_mod  # noqa: E402
import forbidden_scan as fs  # noqa: E402

# Reviewer-chosen plants the per-class fixture in probe 1 did not use:
# a nested Windows thumbnail cache and a nested gitlink under third_party/.
REVIEWER_GITLINK = "third_party/nested/lib/.git"
REVIEWER_OS_CACHE = "windows/cache/ehthumbs.db"


def _write(root: Path, rel: str, body: bytes = b"ok\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)


def main() -> int:
    src_path = Path(fs.__file__)
    src = src_path.read_text(encoding="utf-8")
    needle = 'GIT_DIR_SEGMENT = ".git"'
    if needle not in src:
        print("FAILED:IMP-0003-probe2 mutation target missing")
        return 1
    mutated = src.replace(needle, 'GIT_DIR_SEGMENT = ".git-MUTATED-OFF"', 1)
    mod = types.ModuleType("forbidden_scan_mutated_p2")
    mod.__file__ = str(src_path)
    sys.modules["forbidden_scan_mutated_p2"] = mod
    exec(compile(mutated, str(src_path), "exec"), mod.__dict__)  # noqa: S102

    with tempfile.TemporaryDirectory(prefix="imp0003-p2-") as tmp:
        tmp_path = Path(tmp)
        dirty = tmp_path / "dirty"
        dirty.mkdir()
        _write(dirty, "keep/readme.txt")
        _write(dirty, ".git/HEAD", b"ref: refs/heads/main\n")
        _write(dirty, "app/node_modules/x/index.js")
        _write(dirty, "pkg/__pycache__/z.pyc", b"\0")
        _write(dirty, "var/build.log")
        _write(dirty, "sessions/t.jsonl", b"{}\n")
        _write(dirty, "assets/.DS_Store", b"ds")
        _write(dirty, "huge.bin", b"x" * 50)
        _write(dirty, REVIEWER_GITLINK, b"gitdir: ../../../.git/modules/lib\n")
        _write(dirty, REVIEWER_OS_CACHE, b"thumb")

        scanned = fs.classify_tree(dirty, max_file_bytes=10)
        counted = census_mod.census(dirty)
        diff = census_mod.compare(scanned["paths_seen"], counted["paths"])
        if not diff["agree"]:
            print("FAILED:IMP-0003-probe2 census disagreement (detector failure)")
            print(json.dumps(diff, indent=2)[:2000])
            return 1

        live = fs.classify_tree(dirty, max_file_bytes=10)
        dead = mod.classify_tree(dirty, max_file_bytes=10)
        live_git = [f for f in live["findings"] if f["class"] in ("git_dir", "gitlink")]
        dead_git = [f for f in dead["findings"] if f["class"] in ("git_dir", "gitlink")]
        if not live_git:
            print("FAILED:IMP-0003-probe2 live scanner missed .git")
            return 1
        if dead_git:
            print("FAILED:IMP-0003-probe2 mutated scanner still flags git (rule not load-bearing)")
            return 1

        scan_rep = fs.scan(dirty, max_file_bytes=10)
        if scan_rep["control"]["found"] is not True:
            print("FAILED:IMP-0003-probe2 planted control not FOUND")
            return 1
        classes = {f["class"] for f in scan_rep["staging"]["findings"]}
        gitlink_paths = [f["path"] for f in scan_rep["staging"]["findings"] if f["class"] == fs.CLASS_GITLINK]
        os_paths = [f["path"] for f in scan_rep["staging"]["findings"] if f["class"] == fs.CLASS_OS_CACHE]
        if REVIEWER_GITLINK not in gitlink_paths:
            print(f"FAILED:IMP-0003-probe2 reviewer gitlink not named: {gitlink_paths}")
            return 1
        if REVIEWER_OS_CACHE not in os_paths:
            print(f"FAILED:IMP-0003-probe2 reviewer os_cache not named: {os_paths}")
            return 1

    out = {
        "probe": "probe2-census-mutation-reviewer",
        "unit_id": "IMP-0003",
        "pass": True,
        "census_agree": True,
        "census_path_count": counted["path_count"],
        "scanner_path_count": scanned["path_count"],
        "enumerator": counted.get("enumerator"),
        "mutation_git_rule_load_bearing": True,
        "reviewer_plants": [REVIEWER_GITLINK, REVIEWER_OS_CACHE],
        "reviewer_plants_fired": True,
        "control_found": True,
        "classes_seen": sorted(classes),
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0003-probe2 census agreement, git-rule mutation, reviewer plant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
