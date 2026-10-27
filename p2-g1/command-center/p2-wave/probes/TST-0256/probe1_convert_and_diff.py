#!/usr/bin/env python3
"""TST-0256 probe 1: the documented migration command converts a real old-layout
tree into the guide-oracle layout (tree diff = 0).

Runs the guide's fenced apply command VERBATIM (``python tools/layout_migrate.py
--apply``) with cwd=worktree copy. The oracle is derived INDEPENDENTLY from the
guide's mapping table (path rewriting only, LF-normalized), not from the
migrator's code. Unmapped files must stay put; a missing mapped file is a
detector, not a skip.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "captured-old"
MAPPING = {"src": "tools", "cc": "command-center", "handbook": "docs"}


def tree_hash(tree: Path) -> tuple[str, int]:
    sha = hashlib.sha256()
    n = 0
    for p in sorted(tree.rglob("*")):
        if p.is_file():
            data = p.read_bytes().replace(b"\r\n", b"\n")
            sha.update(p.relative_to(tree).as_posix().encode())
            sha.update(b"\0")
            sha.update(data)
            sha.update(b"\0")
            n += 1
    return sha.hexdigest(), n


def oracle_paths(rel: str) -> str:
    parts = Path(rel).parts
    repl = MAPPING.get(parts[0].lower())
    if repl is None:
        return Path(*parts).as_posix()
    return Path(repl, *parts[1:]).as_posix()


def main() -> int:
    checks: dict[str, bool] = {}
    work = HERE / "_work-probe1"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(FIXTURE, work)
    documented_cmd = [sys.executable, "-B", str(REPO / "tools" / "layout_migrate.py"), "--apply"]
    p = subprocess.run(
        documented_cmd,
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=300,
    )
    checks["documented_command_exit_0"] = p.returncode == 0
    checks["documented_command_reports_migrated"] = "action=migrated" in (p.stdout or "")

    # Guide oracle: mapping-table rewrite of every fixture file.
    fixture_files = sorted(
        q.relative_to(FIXTURE).as_posix() for q in FIXTURE.rglob("*") if q.is_file()
    )
    expected = {oracle_paths(r): Path(FIXTURE, r).read_bytes().replace(b"\r\n", b"\n") for r in fixture_files}
    actual: dict[str, bytes] = {}
    for q in sorted(work.rglob("*")):
        if q.is_file():
            actual[q.relative_to(work).as_posix()] = q.read_bytes().replace(b"\r\n", b"\n")
    diff_added = sorted(set(actual) - set(expected))
    diff_missing = sorted(set(expected) - set(actual))
    diff_content = sorted(
        k for k in set(expected) & set(actual) if expected[k] != actual[k]
    )
    checks["tree_diff_zero"] = not diff_added and not diff_missing and not diff_content

    # Unmapped files stay put; mapped prefixes are GONE from the old locations.
    checks["unmapped_stay_put"] = (work / "README.md").is_file() and (work / "keep" / "unmoved.txt").is_file()
    checks["old_prefixes_vacated"] = not (work / "src").exists() and not (work / "cc").exists() and not (work / "handbook").exists()
    checks["lf_normalized"] = all(
        b"\r\n" not in (work / k).read_bytes() for k in actual if (work / k).suffix == ".md"
    )

    cand_hash, cand_n = tree_hash(work)
    out = {
        "probe": "probe1_convert_and_diff",
        "unit": "TST-0256",
        "documented_command": "python tools/layout_migrate.py --apply",
        "file_count": cand_n,
        "diff_added": diff_added,
        "diff_missing": diff_missing,
        "diff_content": diff_content,
        "tree_diff_count": len(diff_added) + len(diff_missing) + len(diff_content),
        "candidate_tree_hash": cand_hash,
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe1-convert.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
