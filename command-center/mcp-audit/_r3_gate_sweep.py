#!/usr/bin/env python3
"""Run every shipped gate in this lane and report each one's REAL exit code.

Written because the obvious `python gate.py | tail -6; echo $?` reports **tail's** status,
not the gate's -- a shell pipeline hands you the last command's code, so a red gate reads
as green.  This captures returncode per child and fails closed if any gate is missing.

Run::  python _r3_gate_sweep.py [--rev SHA]
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def run(label: str, args: list[str], expect: int = 0) -> tuple[str, int, bool, str]:
    proc = subprocess.run(
        [sys.executable, *args], cwd=HERE, capture_output=True, text=True
    )
    tail = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    marker = next(
        (ln for ln in reversed(tail) if ln.startswith(("SUCCESS:", "FAILED:"))),
        (tail[-1] if tail else "<no output>"),
    )
    return label, proc.returncode, proc.returncode == expect, marker.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rev", default="WORKTREE")
    args = ap.parse_args()

    plan: list[tuple[str, list[str], int]] = [
        ("probe_capability --control", ["probe_capability.py", "--control"], 0),
        ("redproof_control", ["redproof_control.py"], 0),
        ("overlap_report", ["overlap_report.py", "capability-matrix-r2.json"], 0),
        ("r2_reproduce (round-1 defects)", ["_r2_reproduce.py"], 0),
        ("r2_redproof_invariants", ["_r2_redproof_invariants.py"], 0),
        ("r2_corroborate", ["_r2_corroborate.py"], 0),
        ("r3_redproof_liveness", ["_r3_redproof_liveness.py"], 0),
        # Round 4: the EOL claim, its root cause, and the two fixes' both-states proof.
        ("r4_eol_probe", ["_r4_eol_probe.py"], 0),
        ("r4_grep_control", ["_r4_grep_control.py"], 0),
        ("r4_cr_settle", ["_r4_cr_settle.py"], 0),
        ("r4_redproof", ["_r4_redproof.py"], 0),
        ("dod_check @ current", ["_r2_dod_check.py", args.rev], 0),
        # BOTH STATES: the same ledger must go RED on the round-2 blob, or its green on
        # the current one measures nothing.
        ("dod_check @ 630bb8af (must FAIL)", ["_r2_dod_check.py", "630bb8af"], 1),
    ]

    missing = [p[1][0] for p in plan if not (HERE / p[1][0]).exists()]
    if missing:
        print(f"FAILED:gate-sweep missing gates {missing} (fail closed)")
        return 1

    bad: list[str] = []
    for label, argv, expect in plan:
        name, code, ok, marker = run(label, argv, expect)
        print(
            f"  {'ok ' if ok else 'BAD'} rc={code} (want {expect})  {name:34} {marker}"
        )
        if not ok:
            bad.append(name)
    if bad:
        print(f"FAILED:gate-sweep {bad}")
        return 1
    print(
        f"SUCCESS:gate-sweep {len(plan)}/{len(plan)} gates behaved, exit codes captured"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
