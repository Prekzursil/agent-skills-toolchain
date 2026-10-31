"""Freeze gate for TST-0026: every change to the frozen launcher/schema set
requires a migration entry AND a schema_version bump. Unmigrated changes are
rejected with the changed paths named.

    python -B gate.py --tree DIR --baseline baseline.json --migrations migrations.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def digest_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_versions(tree: Path, baseline: dict) -> dict[str, int]:
    vers = {row["path"]: int(row.get("schema_version", 1)) for row in baseline.get("files", [])}
    for row in baseline.get("files", []):
        p = tree / row["path"]
        if p.is_file():
            try:
                head = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(head, dict) and isinstance(head.get("schema_version"), int):
                    vers[row["path"]] = int(head["schema_version"])
            except (json.JSONDecodeError, OSError):
                pass
    return vers


def run_gate(tree: Path, baseline: dict, migrations: dict) -> tuple[int, dict]:
    files = {row["path"]: row for row in baseline.get("files", [])}
    mig_rows = {
        m["path"]: m
        for m in (migrations.get("migrations") or [])
        if isinstance(m, dict) and m.get("path")
    }
    live_paths = {
        str(p.relative_to(tree)).replace("\\", "/")
        for p in tree.rglob("*")
        if p.is_file() and "not-frozen" not in str(p)
    }
    changed, added, gone = [], [], []
    for rel, row in files.items():
        p = tree / rel
        if not p.is_file():
            gone.append(rel)
        elif digest_lf(p) != row.get("sha256"):
            changed.append(rel)
    for rel in sorted(live_paths - set(files)):
        added.append(rel)
    # A change counts as migrated only when BOTH hold:
    #   1. the live file declares a schema_version STRICTLY greater than the
    #      baseline version (a real bump, not a stale row re-used), and
    #   2. a migration row exists whose to_version equals the live version.
    live_versions = load_versions(tree, baseline)
    offending = []
    for rel in changed + added:
        base_ver = int(files.get(rel, {}).get("schema_version", 1)) if rel in files else 1
        live_ver = int(live_versions.get(rel, base_ver))
        m = mig_rows.get(rel)
        if live_ver <= base_ver:
            offending.append({"path": rel, "reason": "no-version-bump"})
        elif not m:
            offending.append({"path": rel, "reason": "unmigrated"})
        elif int(m.get("to_version", 0)) != live_ver:
            offending.append({"path": rel, "reason": "migration-row-stale-version"})
    accepted = not gone and not offending
    return (0 if accepted else 1), {
        "exit_code": 0 if accepted else 1,
        "verdict": "accepted" if accepted else "rejected",
        "changed": changed,
        "added": added,
        "removed": gone,
        "offending": offending,
        "reason": None if accepted else "unmigrated-schema-change",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--migrations", required=True)
    a = ap.parse_args()
    tree = Path(a.tree)
    baseline = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    migrations = json.loads(Path(a.migrations).read_text(encoding="utf-8"))
    code, report = run_gate(tree, baseline, migrations)
    print(json.dumps(report, indent=1))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
