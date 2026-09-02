#!/usr/bin/env python
"""LANE B2 probe v2 for R-M09 (v1 FAILED its own control -> discarded).

v1 used `git hash-object --stdin` on working-tree bytes; the control case
(repo README.md, known present) reported ABSENT, so every "not in git" verdict
was a measurement artifact (CRLF-vs-LF blob identity). v2 instead:

  * compares content LF-NORMALISED (so line-ending noise cannot masquerade
    as unique content),
  * enumerates EVERY historical version of the corresponding repo path with
    `git rev-list --all -- <path>` + `git cat-file -p <commit>:<path>`, and
  * proves the detector fires on a known-present control AND stays silent on a
    known-absent control before any verdict is read.
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
PKG = "tools/monitorcore/monitorcore"


def git(*args: str, binary: bool = False):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    if r.returncode != 0:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def norm(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def walk(root: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[p.relative_to(root).as_posix()] = p
    return out


def history_norms(relpath: str) -> tuple[set[str], int]:
    """Every LF-normalised content hash this repo path ever held, across all refs."""
    out = git("rev-list", "--all", "--", relpath)
    if out is None:
        return set(), 0
    commits = [c for c in out.split() if c]
    hashes: set[str] = set()
    for c in commits:
        blob = git("cat-file", "-p", f"{c}:{relpath}", binary=True)
        if blob is not None:
            hashes.add(norm(blob))
    return hashes, len(commits)


def main() -> int:
    # ---- DETECTOR CONTROL FIRST (rule 3b: prove it fires before trusting silence) ----
    ctl_present, ctl_commits = history_norms("README.md")
    live_readme = (REPO / "README.md").read_bytes()
    control_present_ok = norm(live_readme) in ctl_present
    ctl_absent, _ = history_norms("tools/monitorcore/monitorcore/__NO_SUCH_FILE__.py")
    control_absent_ok = len(ctl_absent) == 0
    controls = {
        "control_present_reports_present": control_present_ok,
        "control_present_commits_scanned": ctl_commits,
        "control_absent_reports_absent": control_absent_ok,
    }
    if not (control_present_ok and control_absent_ok):
        print(json.dumps({"DETECTOR_BROKEN": True, **controls}, indent=1))
        return 2

    bak, live = walk(BAK), walk(LIVE)
    res: dict[str, object] = {
        **controls,
        "bak_path": str(BAK),
        "bak_exists": BAK.exists(),
        "live_exists": LIVE.exists(),
        "bak_file_count": len(bak),
        "live_file_count": len(live),
        "bak_names_not_in_live": sorted(set(bak) - set(live)),
        "identical_after_lf_normalisation": [],
        "raw_byte_identical": [],
        "differing_content": [],
        "bak_UNIQUE_not_in_live_and_not_in_git": [],
    }

    for rel, p in sorted(bak.items()):
        data = p.read_bytes()
        repo_rel = f"{PKG}/{rel}"
        if rel in live:
            live_b = live[rel].read_bytes()
            if data == live_b:
                res["raw_byte_identical"].append(rel)  # type: ignore[union-attr]
                res["identical_after_lf_normalisation"].append(rel)  # type: ignore[union-attr]
                continue
            if norm(data) == norm(live_b):
                res["identical_after_lf_normalisation"].append(rel)  # type: ignore[union-attr]
                continue
        hist, ncommits = history_norms(repo_rel)
        found = norm(data) in hist
        rec = {
            "file": rel,
            "repo_path": repo_rel,
            "in_live": rel in live,
            "bak_bytes": len(data),
            "live_bytes": live[rel].stat().st_size if rel in live else None,
            "history_versions": len(hist),
            "commits_touching_path": ncommits,
            "bak_content_found_in_git_history": found,
        }
        res["differing_content"].append(rec)  # type: ignore[union-attr]
        if not found:
            res["bak_UNIQUE_not_in_live_and_not_in_git"].append(rec)  # type: ignore[union-attr]

    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
