#!/usr/bin/env python3
"""TST-0188 probe1 -- static scan for caret-bearing revision arguments + live
hazard check under pwsh7 (both-states: the bare-caret form must demonstrably
produce a WRONG or errored dereference on this box).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


def rm_tree(base: Path) -> None:
    """rmtree that clears the read-only bit git sets on pack/loose objects."""
    def _onexc(fn, path, exc):
        try:
            os.chmod(path, stat.S_IWRITE)
            fn(path)
        except OSError:
            pass
    shutil_rmtree = __import__("shutil").rmtree
    shutil_rmtree(base, onexc=_onexc)

HERE = Path(__file__).resolve().parent
REPO = HERE.resolve().parents[3]
UNIT = "TST-0188"
RUN = HERE / ".run-p1"

# dispatch surfaces the unit names; documentation/rules/probe dirs are excluded
SURFACES = [
    "tools/lib/codex-invocation.mjs",
    "tools/lib/codex_invocation.py",
]
CARET_PATTERNS = [
    re.compile(r"\^[{^]"),      # ^{commit}-style suffixes
    re.compile(r"\bHEAD\^"),    # HEAD^ parent refs
    re.compile(r"~\^"),         # ~^ forms
]


def scan_surfaces():
    hits = []
    for rel in SURFACES:
        f = REPO / rel
        if not f.is_file():
            hits.append({"path": rel, "line": 0, "text": "<surface-absent>", "note": "scanned surface missing"})
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for pat in CARET_PATTERNS:
                if pat.search(line):
                    hits.append({"path": rel, "line": i, "text": line.strip()[:160]})
    return hits


def make_tagged_repo(repo: Path) -> str:
    repo.mkdir(parents=True, exist_ok=True)
    def git(*args):
        subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "probe@example.invalid")
    git("config", "user.name", "probe")
    (repo / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "seed")
    git("tag", "v1.2.3")
    truth = subprocess.run(
        ["git", "rev-list", "-n", "1", "v1.2.3"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    ).stdout.strip()
    return truth


def run_pwsh(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        ["pwsh", "-NoProfile", "-Command", cmd],
        cwd=str(RUN / "repo"), capture_output=True, text=True, timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    import shutil

    if RUN.exists():
        rm_tree(RUN)
    RUN.mkdir(parents=True)
    repo = RUN / "repo"
    truth = make_tagged_repo(repo)

    # correct form: single-quoted revision dereferences to the tagged commit
    rc_quoted, out_quoted = run_pwsh("git rev-parse --verify 'v1.2.3^{commit}'")
    quoted_ok = rc_quoted == 0 and truth in out_quoted

    # hazard form: BARE caret through PowerShell (^ is the PS escape char)
    rc_bare, out_bare = run_pwsh("git rev-parse --verify v1.2.3^{commit}")
    hazard_demonstrated = (rc_bare != 0) or (truth not in out_bare)

    hits = scan_surfaces()

    payload = {
        "probe": "probe1-static-and-hazard",
        "unit_id": UNIT,
        "pass": not hits and quoted_ok and hazard_demonstrated,
        "static_scan": {
            "surfaces": SURFACES,
            "caret_call_sites": hits,
            "zero_such_call_sites": not hits,
        },
        "live_check_pwsh7": {
            "tagged_commit_truth": truth,
            "quoted_form": {"rc": rc_quoted, "matches_truth": quoted_ok},
            "bare_caret_form": {
                "rc": rc_bare,
                "output_tail": out_bare[-200:],
                "wrong_or_errored": hazard_demonstrated,
            },
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 sites=0 quoted=ok hazard=demonstrated" % UNIT)
        return 0
    print("FAILED:%s-probe1 sites=%d quoted_ok=%s hazard=%s"
          % (UNIT, len(hits), quoted_ok, hazard_demonstrated))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
