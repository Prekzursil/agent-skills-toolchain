#!/usr/bin/env python3
"""Set-difference rollback vs wholesale snapshot restore.

Set-difference mutates only version-owned plugin paths: restore N-1 bytes
for paths in the N-1 projection, delete paths owned at N but not at N-1,
and never touch user-owned paths.

Wholesale snapshot restore replaces the entire profile with the N-1 plugin
tree. That is the naive engine this unit's detector must catch, because it
destroys user data (FC-11347).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PLUGIN = "plugin"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iter_files(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    rels: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rels.append(path.relative_to(root).as_posix())
    return rels


def inventory(root: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for rel in iter_files(root):
        raw = (root / rel).read_bytes()
        out[rel] = {"sha256": sha256_bytes(raw), "bytes": len(raw)}
    return out


def load_manifest(work: Path) -> dict[str, Any]:
    return json.loads((work / "manifest.json").read_text(encoding="utf-8"))


def set_difference_rollback(work: Path) -> dict[str, Any]:
    man = load_manifest(work)
    profile = work / str(man["profile"])
    n1 = work / str(man["n1_backup"])
    plugin = profile / PLUGIN
    restored: list[str] = []
    removed: list[str] = []
    skipped_missing_backup: list[str] = []
    for rel in man["owned_n1"]:
        src = n1 / rel
        dest = plugin / rel
        if not src.is_file():
            skipped_missing_backup.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        restored.append(rel)
    owned_n1 = set(man["owned_n1"])
    for rel in man["owned_n"]:
        if rel in owned_n1:
            continue
        dest = plugin / rel
        if dest.is_file():
            dest.unlink()
            removed.append(rel)
    return {
        "engine": "set-difference",
        "restored": restored,
        "removed": removed,
        "skipped_missing_backup": skipped_missing_backup,
        "user_tree_untouched": True,
    }


def wholesale_snapshot_restore(work: Path) -> dict[str, Any]:
    """Naive engine: replace the whole profile with the N-1 plugin snapshot."""
    man = load_manifest(work)
    profile = work / str(man["profile"])
    n1 = work / str(man["n1_backup"])
    if profile.exists():
        shutil.rmtree(profile)
    dest = profile / PLUGIN
    shutil.copytree(n1, dest)
    return {
        "engine": "wholesale-snapshot",
        "restored": iter_files(dest),
        "removed": ["<entire-profile-replaced>"],
        "user_tree_untouched": False,
    }


def execute(work: Path, engine: str) -> dict[str, Any]:
    if engine in {"set-difference", "set_difference"}:
        body = set_difference_rollback(work)
    elif engine in {"wholesale", "wholesale-snapshot", "wholesale_snapshot"}:
        body = wholesale_snapshot_restore(work)
    else:
        raise SystemExit(f"unknown engine {engine!r}")
    body["exit_code"] = 0
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="CNF-0042 rollback engines")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument(
        "--engine",
        required=True,
        choices=("set-difference", "wholesale"),
    )
    args = parser.parse_args()
    work = args.work.resolve()
    if not (work / "manifest.json").is_file():
        print("FAILED:rollback missing manifest.json", file=sys.stderr)
        return 2
    result = execute(work, args.engine)
    print(json.dumps(result, sort_keys=True))
    return int(result.get("exit_code") or 0)


if __name__ == "__main__":
    raise SystemExit(main())
