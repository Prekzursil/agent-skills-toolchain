#!/usr/bin/env python3
"""TST-0188 probe2 -- second-shell cross-check: the same tag-to-commit dereference
run under Git Bash must agree with the pwsh7-quoted result and the ground truth;
any divergence is a finding (reviewer requirement: second Windows shell).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path


def rm_tree(base: Path) -> None:
    def _onexc(fn, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            fn(path)
        except OSError:
            pass
    __import__("shutil").rmtree(base, onexc=_onexc)

HERE = Path(__file__).resolve().parent
UNIT = "TST-0188"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        rm_tree(RUN)
    RUN.mkdir(parents=True)
    repo = RUN / "repo"
    repo.mkdir(parents=True)

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "seed")
    git("tag", "v2.0.0")

    truth = git("rev-list", "-n", "1", "v2.0.0").stdout.strip()

    # pwsh7 lane (quoted caret form)
    p1 = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", "git rev-parse --verify 'v2.0.0^{commit}'"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    pwsh_commit = (p1.stdout or "").strip().splitlines()[0] if p1.returncode == 0 and p1.stdout else None

    # Git Bash lane (bare caret is safe in POSIX shells; single-quoted also fine)
    p2 = subprocess.run(
        ["bash", "-c", "git rev-parse --verify 'v2.0.0^{commit}'"],
        cwd=str(repo), capture_output=True, text=True, timeout=120,
    )
    bash_commit = (p2.stdout or "").strip().splitlines()[0] if p2.returncode == 0 and p2.stdout else None

    no_divergence = truth == pwsh_commit == bash_commit

    payload = {
        "probe": "probe2-second-shell",
        "unit_id": UNIT,
        "pass": no_divergence and bool(truth),
        "ground_truth_rev_list": truth,
        "pwsh7_quoted_commit": pwsh_commit,
        "git_bash_quoted_commit": bash_commit,
        "divergence": None if no_divergence else {
            "truth": truth, "pwsh7": pwsh_commit, "bash": bash_commit,
        },
        "reviewer_note": "the independent reviewer re-runs this on BOTH shells and reports any divergence as a finding",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 truth==pwsh7==bash (%s)" % (UNIT, truth[:12]))
        return 0
    print("FAILED:%s-probe2 divergence truth=%s pwsh7=%s bash=%s"
          % (UNIT, truth[:12], pwsh_commit and pwsh_commit[:12], bash_commit and bash_commit[:12]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
