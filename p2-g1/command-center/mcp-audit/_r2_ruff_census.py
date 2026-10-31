#!/usr/bin/env python3
"""Repo-wide ruff-format census, split into THIS LANE vs everything else.

D3, the round-1 disclosure-accuracy defect.  Round 1 disclosed "the repo-wide ruff format
gate is RED with 60 files"; the round-1 verifier measured 51 for the same claim.  Neither
number was wrong when it was taken -- the repo-wide count is a MOVING TARGET, because a
dozen sibling lanes are committing into this worktree while the audit runs, each fixing
(or adding) offenders in its own paths.  A bare absolute count is therefore not a
reportable fact; it is a reading with a timestamp and a scope.

So this prints the only two numbers that are stable enough to act on:

  IN-SCOPE     offenders under docs/mcp-audit + command-center/mcp-audit.  This lane owns
               these, it is the number the lane can be held to, and it must be 0.
  OUT-OF-SCOPE offenders elsewhere, listed by top-level owner so the reading is
               attributable rather than a lump sum.

Exit code is driven by the IN-SCOPE count ONLY.  Failing this lane's gate on a sibling's
file would be the same category error as the round-1 disclosure: reporting a number whose
scope does not match the claim.

Run: ``python _r2_ruff_census.py`` -> exit 0 when this lane owns 0 offenders.
"""

from __future__ import annotations

import collections
import datetime
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCOPE = ("docs/mcp-audit", "command-center/mcp-audit")
RUFF = ["uvx", "ruff@0.15.17", "format", "--check", "."]


def main() -> int:
    proc = subprocess.run(
        RUFF, cwd=REPO, capture_output=True, text=True, check=False, shell=False
    )
    lines = [
        line.split("Would reformat:", 1)[1].strip()
        for line in (proc.stdout + proc.stderr).splitlines()
        if line.startswith("Would reformat:")
    ]
    if proc.returncode not in (0, 1):
        print(f"FAILED:ruff-census ruff itself errored rc={proc.returncode}")
        print((proc.stderr or "")[-400:])
        return 1
    norm = [p.replace("\\", "/") for p in lines]
    mine = [p for p in norm if any(p.startswith(s) for s in SCOPE)]
    theirs = [p for p in norm if p not in mine]
    owners = collections.Counter("/".join(p.split("/")[:2]) for p in theirs)

    stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    print(f"== ruff format --check census @ {stamp} ==")
    print(f"  repo-wide would-reformat : {len(norm)}   (MOVING TARGET, see docstring)")
    print(f"  IN-SCOPE (this lane)     : {len(mine)}  {mine}")
    print(f"  out-of-scope by owner    : {dict(owners.most_common())}")
    payload = {
        "measured_utc": stamp,
        "repo_wide": len(norm),
        "in_scope": len(mine),
        "in_scope_files": mine,
        "out_of_scope_by_owner": dict(owners.most_common()),
        "prior_readings": {
            "round1_build": 60,
            "round1_verifier": 51,
            "note": (
                "both readings were correct at their measurement times; the count moves "
                "as sibling lanes commit, so only the in-scope number is a stable claim"
            ),
        },
    }
    (HERE / "ruff-census.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if mine:
        print(f"FAILED:ruff-census this lane owns {len(mine)} offender(s)")
        return 1
    print(f"SUCCESS:ruff-census in_scope=0 repo_wide={len(norm)} at {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
