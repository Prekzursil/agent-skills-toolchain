#!/usr/bin/env python3
"""IMP-0223 probe 2: teardown never deletes an unpreserved worktree.

Rebuilt 2026-10-26 by builder shard11 wave3 after the prior probe directory
was lost mid-flight (host session death). Asserts, all computed live:
  * a shard whose unique bytes are nowhere in the harvest is REFUSED and
    stays on disk (reason=unpreserved-content);
  * on the squash-merge state the branch reports AHEAD and the known-broken
    naive ancestry mutant authorizes deletion while the content gate refuses;
  * a worktree whose bytes ARE proven preserved in a harvest is deleted
    (reason=content-proven).
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
    def git(*args):
        proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
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
    with tempfile.TemporaryDirectory(prefix="imp0223-p2-") as tmp:
        base = Path(tmp)
        repo = make_fixture_repo(base)
        result = gw.measure_teardown_both_states(repo, base / "worktrees")
        ok = bool(result.get("pass"))
        print(json.dumps(result, indent=2, sort_keys=True))
        if ok:
            print("SUCCESS:IMP-0223-probe2 teardown refused on unpreserved "
                  "content; naive ancestry mutant authorizes where content gate refuses; "
                  "harvest-proven worktree deleted")
            return 0
        print("FAILED:IMP-0223-probe2 " + json.dumps(result.get("dangerous"), default=str))
        return 1


if __name__ == "__main__":
    sys.exit(main())
