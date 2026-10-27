#!/usr/bin/env python3
"""Measure which of this lane's gates actually RUN on a Linux CI runner.

Written for the INTEGRATE lane.  Every gate in this directory was authored and measured on
Windows; several deliberately characterise Windows behaviour (a bare ``.cmd`` shim on PATH,
MSYS ``grep`` in text mode).  Wiring the whole sweep into ``ubuntu-latest`` without measuring
would ship either a permanently RED job or -- worse -- a job that is green because the gate
it was supposed to run silently no-opped.

This does not guess from the source text.  It EXECUTES each gate and records the real exit
code, the terminal marker, and the stderr tail, so the workflow's gate list is chosen from
measurement.

Run inside a full clone (NOT a linked worktree -- WSL cannot resolve a worktree's ``.git``
file, which returns clean zeros forever)::

    python3 command-center/mcp-audit/_i1_ci_portability.py [--json OUT]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]

# Mirrors _r3_gate_sweep.py's plan exactly, plus the two producers whose determinism is the
# thing a CI gate would actually protect.  (label, argv, expected_rc)
PLAN: list[tuple[str, list[str], int]] = [
    ("probe_capability --control", ["probe_capability.py", "--control"], 0),
    ("redproof_control", ["redproof_control.py"], 0),
    ("overlap_report", ["overlap_report.py", "capability-matrix-r2.json"], 0),
    ("r2_reproduce", ["_r2_reproduce.py"], 0),
    ("r2_redproof_invariants", ["_r2_redproof_invariants.py"], 0),
    ("r2_corroborate", ["_r2_corroborate.py"], 0),
    ("r3_redproof_liveness", ["_r3_redproof_liveness.py"], 0),
    ("r4_eol_probe", ["_r4_eol_probe.py"], 0),
    ("r4_grep_control", ["_r4_grep_control.py"], 0),
    ("r4_cr_settle", ["_r4_cr_settle.py"], 0),
    ("r4_redproof", ["_r4_redproof.py"], 0),
    ("r4_selfcheck", ["_r4_selfcheck.py", "HEAD"], 0),
    ("dod_check @ HEAD", ["_r2_dod_check.py", "HEAD"], 0),
    ("dod_check @ 630bb8af (must FAIL)", ["_r2_dod_check.py", "630bb8af"], 1),
    ("rank_disposition (regen)", ["rank_disposition.py"], 0),
]


def run(argv: list[str], expect: int) -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, *argv], cwd=HERE, capture_output=True, text=True
    )
    out = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    marker = next(
        (ln for ln in reversed(out) if ln.startswith(("SUCCESS:", "FAILED:"))),
        (out[-1] if out else "<no stdout>"),
    )
    err = [ln for ln in proc.stderr.splitlines() if ln.strip()]
    return {
        "rc": proc.returncode,
        "expect": expect,
        "ok": proc.returncode == expect,
        "marker": marker.strip()[:160],
        "stderr_tail": err[-3:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    # Fail closed: a probe run in a linked worktree (or any tree where git history is
    # unreachable) would report every history-reading gate as broken and be mistaken for a
    # portability verdict.  Prove git works here FIRST.
    probe = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True
    )
    if probe.returncode != 0:
        print(f"FAILED:ci-portability git unusable here: {probe.stderr.strip()[:120]}")
        return 1
    head = probe.stdout.strip()
    depth = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=REPO, capture_output=True, text=True
    ).stdout.strip()
    print(
        f"  tree {REPO}  HEAD {head[:8]}  history {depth} commits  py {sys.version.split()[0]}"
    )

    results: dict[str, dict[str, object]] = {}
    for label, argv, expect in PLAN:
        if not (HERE / argv[0]).exists():
            results[label] = {
                "rc": None,
                "expect": expect,
                "ok": False,
                "marker": "<missing>",
                "stderr_tail": [],
            }
            continue
        results[label] = run(argv, expect)

    for label, r in results.items():
        flag = "ok " if r["ok"] else "BAD"
        print(f"  {flag} rc={r['rc']} (want {r['expect']})  {label:36} {r['marker']}")
        if not r["ok"] and r["stderr_tail"]:
            for ln in r["stderr_tail"]:
                print(f"        ! {ln[:150]}")

    portable = [k for k, v in results.items() if v["ok"]]
    broken = [k for k, v in results.items() if not v["ok"]]
    print(f"\n  PORTABLE {len(portable)}/{len(results)}")
    if broken:
        print(f"  NOT PORTABLE: {broken}")

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                {"head": head, "python": sys.version.split()[0], "results": results},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(
        f"SUCCESS:ci-portability measured {len(results)} gates, {len(portable)} portable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
