#!/usr/bin/env python
"""LANE B2 probe for R-M09: does monitorcore.bak-20260727-091532 hold ANY unique bytes?

Re-derives the inherited claim independently:
  1. name-subset check    bak files vs live files
  2. byte-identity check  sha256 per file
  3. git-history check    every differing bak blob must exist somewhere in repo history
Prints a machine-readable JSON verdict. Read-only: opens files, never writes/deletes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
BAK = HOME / ".agents/skills/workflow-monitor/monitorcore.bak-20260727-091532"
LIVE = HOME / ".agents/skills/workflow-monitor/monitorcore"
REPO = Path(__file__).resolve().parents[1]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def walk(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[p.relative_to(root).as_posix()] = p
    return out


def git_blob_hashes() -> set[str]:
    """sha256 of every blob reachable from any ref, keyed by content sha256."""
    # list all blob object ids across history
    cmd = ["git", "-C", str(REPO), "rev-list", "--objects", "--all"]
    objs = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.splitlines()
    ids = [line.split()[0] for line in objs if line.strip()]
    return set(ids)


def content_in_git(data: bytes) -> tuple[bool, str]:
    """Ask git for the blob id of this exact content, then test reachability."""
    h = subprocess.run(
        ["git", "-C", str(REPO), "hash-object", "--stdin"],
        input=data,
        capture_output=True,
        check=True,
    ).stdout.decode().strip()
    exists = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", h],
        capture_output=True,
    ).returncode == 0
    return exists, h


def main() -> int:
    bak, live = walk(BAK), walk(LIVE)
    res: dict[str, object] = {
        "bak_exists": BAK.exists(),
        "live_exists": LIVE.exists(),
        "bak_file_count": len(bak),
        "live_file_count": len(live),
        "bak_names_not_in_live": sorted(set(bak) - set(live)),
        "byte_identical": [],
        "differing": [],
        "bak_UNIQUE_not_in_live_and_not_in_git": [],
        "reachable_object_count": 0,
    }
    reachable = git_blob_hashes()
    res["reachable_object_count"] = len(reachable)

    for rel, p in bak.items():
        if rel not in live:
            data = p.read_bytes()
            in_git, blob = content_in_git(data)
            reach = in_git and blob in reachable
            if not reach:
                res["bak_UNIQUE_not_in_live_and_not_in_git"].append(  # type: ignore[union-attr]
                    {"file": rel, "reason": "name-absent-from-live", "blob": blob,
                     "in_odb": in_git, "reachable": reach}
                )
            continue
        if sha(p) == sha(live[rel]):
            res["byte_identical"].append(rel)  # type: ignore[union-attr]
        else:
            data = p.read_bytes()
            in_git, blob = content_in_git(data)
            reach = in_git and blob in reachable
            res["differing"].append(  # type: ignore[union-attr]
                {"file": rel, "blob": blob, "in_odb": in_git, "reachable_from_a_ref": reach,
                 "bak_bytes": len(data), "live_bytes": live[rel].stat().st_size}
            )
            if not reach:
                res["bak_UNIQUE_not_in_live_and_not_in_git"].append(  # type: ignore[union-attr]
                    {"file": rel, "reason": "content-differs-and-not-in-git", "blob": blob,
                     "in_odb": in_git, "reachable": reach}
                )

    # DETECTOR CONTROL: a byte string that cannot be in git must report absent,
    # and a known-present repo file must report present.
    fake = b"lane-b2-detector-control-" + b"x" * 64
    res["control_absent_reports_absent"] = not content_in_git(fake)[0]
    known = (REPO / "README.md").read_bytes()
    ok, blob = content_in_git(known)
    res["control_present_reports_present"] = ok and blob in reachable
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
