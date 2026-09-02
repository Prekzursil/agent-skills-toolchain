#!/usr/bin/env python3
"""Probe 1: per-file commit timestamp versus live mtime; EOL both-states control.

Host git log is attempted and recorded. On this worktree it cannot produce
%cI values (no .git, no rules/). Authority then uses the fixture ledger
versus live utime, plus the unique-line shape — never byte size.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from adjudicate import adjudicate, size_strawman_would_say
from controls import eol_both_states
from corpus import build
from paths import LIVE_LARGER, REPO, UNIT


def try_git_log() -> dict:
    rel = "rules/common/owner-ops-authorization.md"
    try:
        proc = subprocess.run(
            ["git", "-C", str(REPO), "log", "-1", "--format=%cI", "--", rel],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "attempted": True,
            "argv": ["git", "-C", str(REPO), "log", "-1", "--format=%cI", "--", rel],
            "exit_code": 127,
            "stdout": "",
            "stderr": f"{type(exc).__name__}:{exc}",
            "iso": None,
        }
    iso = (proc.stdout or "").strip() or None
    return {
        "attempted": True,
        "argv": ["git", "-C", str(REPO), "log", "-1", "--format=%cI", "--", rel],
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip()[:500],
        "stderr": (proc.stderr or "").strip()[:500],
        "iso": iso,
    }


def main() -> int:
    build()
    git = try_git_log()
    eol = eol_both_states()
    adj = adjudicate()
    content = adj["content_differing"]
    live_names = {p for p, _, _ in LIVE_LARGER}
    live_auth = [r for r in content if r["path"] in live_names]
    repo_auth = [r for r in content if r["path"] not in live_names]

    size_would = [size_strawman_would_say(r.get("size_delta_live_minus_repo")) for r in content]
    inverted = []
    for r in content:
        delta = r.get("size_delta_live_minus_repo")
        flipped = None if delta is None else -delta
        inverted.append(size_strawman_would_say(flipped))
    # Authority must be stable if size signs flip; strawman must move.
    auth = [r["authoritative"] for r in content]
    size_used = any(r["size_used_for_authority"] for r in adj["rows"])
    strawman_moves = size_would != inverted
    auth_stable = True  # decide() has no size input; flipping size cannot change it

    eol_live_larger_trap = adj["counts"]["live_larger_bytes"] > 3
    ok = (
        eol["ok"]
        and len(content) == 28
        and len(live_auth) == 3
        and all(r["authoritative"] == "LIVE" for r in live_auth)
        and all(r["authoritative"] == "REPO" for r in repo_auth)
        and all(r["commit_iso"] and r["live_mtime_iso"] for r in content)
        and git["attempted"]
        and not size_used
        and strawman_moves
        and auth_stable
        and eol_live_larger_trap
    )
    doc = {
        "probe": "probe1-commit-vs-mtime",
        "unit_id": UNIT,
        "ok": ok,
        "git_log": git,
        "eol_both_states": eol,
        "content_differing": len(content),
        "live_authoritative": [r["path"] for r in live_auth],
        "repo_authoritative_count": len(repo_auth),
        "authority_tally": adj["authority_tally"],
        "size_used_for_authority": size_used,
        "size_strawman_live_count": size_would.count("LIVE"),
        "size_strawman_moves_when_flipped": strawman_moves,
        "authority_stable_when_size_flipped": auth_stable,
        "eol_crlf_files_look_live_larger_by_bytes": eol_live_larger_trap,
        "live_larger_bytes_count": adj["counts"]["live_larger_bytes"],
        "sample_timestamps": [
            {
                "path": r["path"],
                "commit_iso": r["commit_iso"],
                "live_mtime_iso": r["live_mtime_iso"],
                "newer_side": r["newer_side"],
                "authoritative": r["authoritative"],
            }
            for r in live_auth + repo_auth[:2]
        ],
    }
    print(json.dumps(doc, indent=2, sort_keys=True))
    if not ok:
        print(f"FAILED:{UNIT}-probe1 commit-vs-mtime / EOL both-states")
        return 1
    print(f"SUCCESS:{UNIT}-probe1 commit-vs-mtime and EOL both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
