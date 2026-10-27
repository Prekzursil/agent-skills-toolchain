#!/usr/bin/env python3
"""IMP-0223 probe 1: two concurrent mutating units never share a git index.

Rebuilt 2026-10-26 by builder shard11 wave3 after the prior probe directory
was lost mid-flight (host session death). Runs the live provisioner against
a throwaway git repo and asserts:
  * staged sets of the two units are disjoint (computed intersection empty)
  * each unit owns a distinct gitdir and distinct index file (bytes differ)
  * the contamination control fires: both unit files on ONE shared checkout
    plus a broad git add -A stage both paths (detector's bad state proven)
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "gitcrypt-worktree"))

import gitcrypt_worktree as gw  # noqa: E402


def make_fixture_repo(base: Path) -> Path:
    repo = base / "fixture"
    repo.mkdir(parents=True)
    def git(*args, cwd=None):
        proc = subprocess.run(["git", *args], cwd=str(cwd or repo), capture_output=True,
                              text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(f"git {args} failed: {proc.stderr}")
        return proc.stdout
    git("init", "-b", "main")
    git("config", "user.name", "P2 Fixture")
    git("config", "user.email", "fixture@invalid")
    git("config", "commit.gpgsign", "false")
    git("config", "core.autocrlf", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    git("add", "seed.txt")
    git("commit", "-m", "seed")
    return repo


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0223-p1-") as tmp:
        base = Path(tmp)
        repo = make_fixture_repo(base)
        result = gw.measure_disjoint_indexes(repo, base / "worktrees")
        ok = bool(result.get("pass"))
        print(json.dumps(result, indent=2, sort_keys=True))
        if ok:
            print("SUCCESS:IMP-0223-probe1 concurrent mutators staged disjoint; "
                  "shared-checkout broad-add control detected contamination")
            return 0
        print("FAILED:IMP-0223-probe1 " + json.dumps(
            {k: result.get(k) for k in
             ("intersection", "index_paths_distinct", "index_bytes_differ",
              "contamination_control")}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
