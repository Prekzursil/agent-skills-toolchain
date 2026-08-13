#!/usr/bin/env python3
r"""B1: settle the DIRECTION of hook-body drift with an exact algorithm, not judgement.

Round 5 (_g5_bodydrift.py) proved 43 of 235 shared hook files differ and 12 of those are WIRED
live checks. It deliberately stopped there: byte counts, def-name sets and mtimes cannot tell
REPO-AHEAD (repo is a superset -> deploying is a clean upgrade) from DIVERGED (both sides hold
unique content -> deploying destroys live behaviour). That is precisely the case
fan-out-contract C4 measured six Opus agents getting wrong 31 times out of 47 disagreements,
with 100% of the errors pointing at data loss, because a one-directional read cannot see
two-directional divergence.

C4's own conclusion is the method here: if a question is answerable by an exact algorithm --
set membership over lines -- WRITE THE ALGORITHM. Agents describe the divergent content
afterwards; they do not classify it.

CLASSIFICATION (over LF-normalised, right-stripped, non-empty, non-comment lines):
  EQUAL       both sides identical after normalisation
  REPO-AHEAD  live_unique == 0 and repo_unique > 0  -> repo contains everything live has
  LIVE-AHEAD  repo_unique == 0 and live_unique > 0  -> live contains everything repo has
  DIVERGED    both sides hold lines the other lacks -> a copy in EITHER direction loses content

Line-set membership is deliberately order-insensitive: a pure reorder or a rename that keeps
every line is NOT drift worth blocking a deploy over, while a line that exists on one side only
IS. The known weakness, disclosed rather than hidden: a moved line reads as EQUAL, so this
UNDER-reports reordering. That bias is the safe direction for a gate whose failure mode is
data loss -- it never reports "safe to deploy" for a file that has live-only content.

CONTROLS (all must pass or the run publishes INCONCLUSIVE and exits 1):
  B1-C1 POSITIVE  a synthetic REPO-AHEAD pair must classify REPO-AHEAD.
  B1-C2 POSITIVE  a synthetic DIVERGED pair must classify DIVERGED (this is the arm that the
                  six agents failed; a classifier that cannot produce DIVERGED at all would
                  otherwise report every file deploy-safe and pass a naive smoke test).
  B1-C3 POSITIVE  a synthetic EQUAL pair must classify EQUAL.
  B1-C4 FAIL-CLOSED  at least one real input file must have been read; an empty walk is a
                  FAILURE, never "nothing found -> clean".
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_HOOKS = Path(r"C:\Users\Prekzursil\source\ast-integrate\hooks")
LIVE_HOOKS = Path(r"C:\Users\Prekzursil\.claude\hooks")
OUT = Path(__file__).resolve().parent / "B1-DIRECTION.json"

#: The 12 files round 5 measured as WIRED-and-drifted. Kept explicit rather than re-derived so
#: this probe answers exactly the question P0 asked, and so a change in the wired set is a
#: visible edit here rather than a silent change of scope.
WIRED_DRIFTED = [
    "_dispatch/dispatch.py",
    "background-digest/reader.py",
    "codex-monitor-autolaunch/check.py",
    "git-hygiene/check.py",
    "honest-signal/check.py",
    "memory-spool/flush_check.py",
    "no-force-push/hook.py",
    "per-edit-check/check.py",
    "semantic-router/route.py",
    "test-tamper-guard/guard.py",
    "wire-check/check.py",
    "workflow-monitor-autolaunch/check.py",
]

_DEF = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)")


def sig_lines(text: str) -> set[str]:
    """Normalise to the comparable line set.

    LF-normalise (windows-shell 8b: CRLF is not drift), right-strip, drop blank lines and
    whole-line comments. Leading indentation is KEPT -- moving a block into an `if` changes
    behaviour and must not normalise away.
    """
    out: set[str] = set()
    for raw in text.replace("\r\n", "\n").split("\n"):
        s = raw.rstrip()
        if not s.strip():
            continue
        if s.lstrip().startswith("#"):
            continue
        out.add(s)
    return out


def defs(text: str) -> set[str]:
    return {
        m.group(1)
        for m in (_DEF.match(ln) for ln in text.replace("\r\n", "\n").split("\n"))
        if m
    }


def classify(repo_text: str, live_text: str) -> dict:
    r, live = sig_lines(repo_text), sig_lines(live_text)
    repo_only = sorted(r - live)
    live_only = sorted(live - r)
    if not repo_only and not live_only:
        verdict = "EQUAL"
    elif not live_only:
        verdict = "REPO-AHEAD"
    elif not repo_only:
        verdict = "LIVE-AHEAD"
    else:
        verdict = "DIVERGED"
    dr, dl = defs(repo_text), defs(live_text)
    return {
        "verdict": verdict,
        "repo_only_lines": len(repo_only),
        "live_only_lines": len(live_only),
        "repo_only_defs": sorted(dr - dl),
        "live_only_defs": sorted(dl - dr),
        "live_only_sample": live_only[:12],
    }


def controls() -> dict:
    a = "def f():\n    return 1\n"
    b = "def f():\n    return 1\n\ndef g():\n    return 2\n"
    c = "def f():\n    return 1\n\ndef h():\n    return 3\n"
    ctl = {
        "B1_C1_repo_ahead": classify(b, a)["verdict"] == "REPO-AHEAD",
        "B1_C2_diverged": classify(b, c)["verdict"] == "DIVERGED",
        "B1_C3_equal": classify(a, a)["verdict"] == "EQUAL",
    }
    ctl["B1_C_live_ahead"] = classify(a, b)["verdict"] == "LIVE-AHEAD"
    return ctl


def main() -> int:
    ctl = controls()
    rows = []
    read_ok = 0
    for rel in WIRED_DRIFTED:
        rp, lp = REPO_HOOKS / rel, LIVE_HOOKS / rel
        if not rp.is_file() or not lp.is_file():
            rows.append(
                {
                    "path": rel,
                    "verdict": "SEARCH-FAILED",
                    "repo_exists": rp.is_file(),
                    "live_exists": lp.is_file(),
                }
            )
            continue
        row = classify(
            rp.read_text(encoding="utf-8", errors="replace"),
            lp.read_text(encoding="utf-8", errors="replace"),
        )
        row["path"] = rel
        rows.append(row)
        read_ok += 1

    ctl["B1_C4_read_at_least_one"] = read_ok > 0
    res = {
        "controls": ctl,
        "files_read": read_ok,
        "rows": rows,
        "summary": {},
    }
    if not all(ctl.values()):
        res["verdict"] = "INCONCLUSIVE - classifier failed its own controls"
        OUT.write_text(json.dumps(res, indent=2), encoding="utf-8", newline="\n")
        print(json.dumps(res["controls"], indent=2))
        print("FAILED:b1-direction controls")
        return 1

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    res["summary"] = tally
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({"controls": ctl, "summary": tally}, indent=2))
    for r in rows:
        print(
            f"  {r['verdict']:<12} {r['path']:<40} "
            f"repo_only={r.get('repo_only_lines')} live_only={r.get('live_only_lines')}"
        )
    print(f"SUCCESS:b1-direction {read_ok} files classified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
