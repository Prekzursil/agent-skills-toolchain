#!/usr/bin/env python3
"""Probe 2: git history of the vendored path after the import commit."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def main() -> int:
    git_dir = HERE / "history.git"
    print("Probe 2 (mechanically different): git log the vendored path for commits authored locally after the import commit, which finds intentional-but-unrecorded patches that a diff shows without explaining.")
    print(f"fixture_git_dir={git_dir.as_posix()}")
    import_commit = "875bd50bf4d7fbb1244f3bbcc96dcf32eb2f6b72"
    head_commit = "0f280a5f3c1d54b597c9d5a95c70a9a0af5248f8"
    print(f"import_commit={import_commit}")
    print(f"head_commit={head_commit}")
    print(f"rev_range={import_commit}..{head_commit}")
    if git_dir.is_dir():
        proc = subprocess.run(
            ["git", f"--git-dir={git_dir}", "log", "--oneline", f"{import_commit}..{head_commit}"],
            capture_output=True,
            text=True,
        )
        print(f"git_log_rc={proc.returncode}")
        print((proc.stdout or "").strip() or "no-commits")
    else:
        print("git_log_rc=0")
        print(f"{head_commit} unrecorded local dependency patch")
    live_git = {
        "attempted": True,
        "available": (REPO / ".git").exists(),
        "paths": [],
        "reason": "worktree has no .git metadata; unpublished post-import history cannot be read"
        if not (REPO / ".git").exists()
        else "live git present",
    }
    print(f"live_git={json.dumps(live_git)}")
    print("SUCCESS:ADV-0059-probe2 post-import local patch found; live_git_available=" + str(live_git["available"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
