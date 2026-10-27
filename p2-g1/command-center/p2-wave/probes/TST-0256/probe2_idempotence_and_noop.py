#!/usr/bin/env python3
"""TST-0256 probe 2: idempotence + already-migrated noop + both-states controls.

Second run of the documented command on an already-migrated tree must be a
noop (nothing moves, byte-identical tree hash). Controls:
  - already-migrated tree is a no-op (good state silent),
  - a mutant that stamps one byte into a migrated file CHANGES the tree hash
    (detector fires on the bad state),
  - fixture provenance: the fixture is old-layout BY CONSTRUCTION and is not
    the migrator's output (it carries old prefixes and none of the new ones).
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


def tree_hash(tree: Path) -> str:
    sha = hashlib.sha256()
    for p in sorted(tree.rglob("*")):
        if p.is_file():
            sha.update(p.relative_to(tree).as_posix().encode())
            sha.update(b"\0")
            sha.update(p.read_bytes().replace(b"\r\n", b"\n"))
            sha.update(b"\0")
    return sha.hexdigest()


def run_apply(work: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(REPO / "tools" / "layout_migrate.py"), "--apply"],
        cwd=str(work),
        capture_output=True,
        text=True,
        timeout=300,
    )


def main() -> int:
    checks: dict[str, bool] = {}
    work = HERE / "_work-probe2"
    if work.exists():
        shutil.rmtree(work)
    shutil.copytree(FIXTURE, work)
    first = run_apply(work)
    checks["first_run_migrated"] = first.returncode == 0 and "action=migrated" in first.stdout
    h1 = tree_hash(work)
    second = run_apply(work)
    checks["second_run_exit_0"] = second.returncode == 0
    checks["second_run_noop"] = "action=noop" in second.stdout
    h2 = tree_hash(work)
    checks["hash_run1_eq_run2"] = h1 == h2

    # Detector control: a stamped mutant must change the tree hash.
    probe_file = work / "docs" / "ops.md"
    before = probe_file.read_bytes()
    probe_file.write_bytes(before + b"\n<!-- stamped mutant -->\n")
    h3 = tree_hash(work)
    checks["mutant_stamp_changes_hash"] = h3 != h2
    probe_file.write_bytes(before)  # restore

    # Fixture provenance: old layout by construction, NOT the migrator output.
    fixture_files = [q.relative_to(FIXTURE).as_posix() for q in FIXTURE.rglob("*") if q.is_file()]
    old_prefixes = ("src/", "cc/", "handbook/")
    new_prefixes = ("tools/", "command-center/", "docs/", "src/lib", "tools/lib")
    has_old = any(r.startswith(old_prefixes) for r in fixture_files)
    # A fixture synthesized FROM the migrator would already be new-layout.
    synthetic_shapes = ("tools/", "command-center/", "docs/")
    has_new = any(r.startswith(synthetic_shapes) for r in fixture_files)
    checks["fixture_old_layout_by_construction"] = has_old and not has_new

    out = {
        "probe": "probe2_idempotence_and_noop",
        "unit": "TST-0256",
        "documented_command": "python tools/layout_migrate.py --apply",
        "hash_run1": h1,
        "hash_run2": h2,
        "hash_mutant": h3,
        "hash_unchanged_on_second_run": h1 == h2,
        "fixture_file_count": len(fixture_files),
        "checks": dict(sorted(checks.items())),
        "ok": all(checks.values()),
    }
    (HERE / "probe2-idempotence.raw.txt").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
