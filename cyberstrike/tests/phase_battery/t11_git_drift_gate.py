#!/usr/bin/env python3
"""T-11 git drift gate - live config surface vs git SSOT (G-2 discipline).

The repo IS the source of truth (Phase-1 git init). Gate semantics:

  FAIL  - any tracked file with UNSTAGED modifications (live bytes diverged
          from both HEAD and the index: config edited outside git);
          a staged change later clobbered by a further live edit ("MM");
          a tracked file deleted from the worktree.
  PASS   - clean tree, or staged-only state (`A `/`M ` with nothing behind
           it: the main session stages, the OWNER commits - staging is the
           sanctioned hand-off, per the no-commit rule).
  WARN   - untracked files outside .gitignore are recorded as hits (runtime
           junk / new artifacts) but do not fail the gate by default;
           `--strict-untracked` flips them to failures.

Both-states control: the gate is exercised against a planted defect in a
SCRATCH clone (never the live repo): one file modified after staging must
register as drift (MM/" M"), proving the detector fires. Without this leg a
"CLEAN" reading could be a porcelain-parsing artifact.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    REPO, SUCCESS, FAILED, VerdictRecorder, git,
)


def porcelain() -> list[str]:
    r = git(["status", "--porcelain"])
    if r.returncode != 0:
        raise RuntimeError(f"git status failed: {r.stderr[:200]}")
    return [ln for ln in (r.stdout or "").splitlines() if ln.strip()]


def classify(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return (fail_lines, warn_lines) from porcelain output."""
    fails, warns = [], []
    for ln in lines:
        xy, path = ln[:2], ln[3:]
        if xy in (" M", "MM", "MT", "RM", " D", "MD", "AD", "AM"):
            # unstaged modification/deletion behind (or after) staging = drift
            fails.append({"xy": xy, "path": path})
        elif xy == "??":
            warns.append({"xy": xy, "path": path})
        # "A ", "M ", staged-only: sanctioned hand-off state - not drift
    return fails, warns


def control() -> bool:
    """Both-states control in a scratch clone: plant drift, must be detected."""
    with tempfile.TemporaryDirectory(prefix="t11-ctl-") as td:
        clone = Path(td) / "repo"
        r = subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks",
             str(REPO).replace("\\", "/"), str(clone).replace("\\", "/")],
            capture_output=True, text=True, timeout=120,
            encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False
        f = clone / "CONTEXT.md"
        f.write_text("planted drift\n", encoding="utf-8")
        q = subprocess.run(["git", "-C", str(clone), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        out = (q.stdout or "").splitlines()
        # planted edit on a tracked file must surface as " M" (or "MM")
        return any(ln.startswith((" M", "MM")) for ln in out)


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    opts = opts or {}
    strict_untracked = opts.get("strict_untracked", False)
    try:
        lines = porcelain()
    except RuntimeError as e:
        rec.record("T-11", FAILED, reason=str(e))
        return FAILED

    head = git(["rev-parse", "HEAD"])
    fails, warns = classify(lines)
    for f in fails:
        rec.hit("T-11", "tracked_drift", **f)
    for w in warns:
        rec.hit("T-11", "untracked_warn", **w)

    ctrl_ok = control()
    rec.hit("T-11", "detector_control", scratch_clone_planted_drift=ctrl_ok)

    fail = bool(fails) or (strict_untracked and bool(warns)) or not ctrl_ok
    rec.record("T-11", SUCCESS if not fail else FAILED,
               details={
                   "head": (head.stdout or "").strip(),
                   "staged_only_entries": [ln for ln in lines
                                           if ln[:2] in ("A ", "M ", "R ")],
                   "tracked_drift": fails,
                   "untracked_warns": warns,
                   "strict_untracked": strict_untracked,
                   "note": "staged-only is the sanctioned hand-off (owner "
                           "commits); unstaged live edits are the drift this "
                           "gate exists to catch",
               },
               anchors=[REPO / ".gitignore"],
               reason=None if not fail else
               ("tracked drift" if fails else
                "untracked under --strict-untracked" if warns else
                "drift detector control failed to fire"))
    return SUCCESS if not fail else FAILED


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict-untracked", action="store_true",
                    help="fail on untracked non-ignored files too")
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-11"}) as rec:
        status = run(rec, {"strict_untracked": args.strict_untracked})
        print(f"T-11 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
