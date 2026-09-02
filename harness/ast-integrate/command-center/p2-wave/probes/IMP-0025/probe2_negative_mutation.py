#!/usr/bin/env python3
"""Probe 2: negative control + mutation, same process.

NEGATIVE CONTROL: DIVERGED fixture refused and REPO-AHEAD repaired in one apply.
MUTATION: one-directional classifier makes test_diverged_files_never_touched go red.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin" / "tests"))

from test_repair_respects_divergence import (  # noqa: E402
    DIVERGED_REL,
    LIVE_UNIQUE,
    REPO_AHEAD_REL,
    REPO_UNIQUE,
    plant_pair,
    test_diverged_files_never_touched,
    test_mutation_one_directional_makes_diverged_test_go_red,
    test_negative_control_diverged_refused_repo_ahead_repaired,
)
from plugin.repair import apply_repair  # noqa: E402
import tempfile

TEST_FILE = (
    REPO / "tools" / "plugin" / "tests" / "test_repair_respects_divergence.py"
)


def main() -> int:
    test_negative_control_diverged_refused_repo_ahead_repaired()
    test_mutation_one_directional_makes_diverged_test_go_red()

    with tempfile.TemporaryDirectory(prefix="imp0025-p2-") as tmp:
        repo, live = plant_pair(Path(tmp))
        diverged_before = (live / DIVERGED_REL).read_bytes()
        two_way = apply_repair(repo, live, one_directional=False, dry_run=False)
        diverged_after = (live / DIVERGED_REL).read_bytes()
        repo_ahead_after = (live / REPO_AHEAD_REL).read_bytes()
        two_ok = (
            DIVERGED_REL not in two_way["applied"]
            and REPO_AHEAD_REL in two_way["applied"]
            and diverged_after == diverged_before
            and LIVE_UNIQUE.encode() in diverged_after
            and REPO_UNIQUE.encode() in repo_ahead_after
        )

    with tempfile.TemporaryDirectory(prefix="imp0025-p2m-") as tmp:
        repo, live = plant_pair(Path(tmp))
        before = (live / DIVERGED_REL).read_bytes()
        mutated = apply_repair(repo, live, one_directional=True, dry_run=False)
        after = (live / DIVERGED_REL).read_bytes()
        mutation_overwrote = after != before and DIVERGED_REL in mutated["applied"]

    went_red = False
    try:
        test_diverged_files_never_touched(one_directional=True)
    except AssertionError:
        went_red = True

    proc = subprocess.run(
        [sys.executable, "-B", str(TEST_FILE)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=60,
    )
    tests_ok = proc.returncode == 0 and "SUCCESS:IMP-0025 tests" in (
        proc.stdout + proc.stderr
    )

    rec = {
        "probe": "probe2-negative-and-mutation",
        "unit_id": "IMP-0025",
        "same_run_diverged_refused": two_ok and DIVERGED_REL not in two_way["applied"],
        "same_run_repo_ahead_repaired": two_ok and REPO_AHEAD_REL in two_way["applied"],
        "mutation_overwrote_diverged": mutation_overwrote,
        "diverged_test_went_red_under_mutation": went_red,
        "unittest_exit": proc.returncode,
        "pass": bool(two_ok and mutation_overwrote and went_red and tests_ok),
    }
    print(json.dumps(rec, sort_keys=True))
    print(
        "same_run_refused_and_repaired="
        + str(two_ok)
        + " mutation_overwrote="
        + str(mutation_overwrote)
        + " diverged_test_red="
        + str(went_red)
        + " tests_ok="
        + str(tests_ok)
    )
    if proc.stdout:
        for line in proc.stdout.strip().splitlines()[-8:]:
            print(line)
    if not rec["pass"]:
        print("FAILED:IMP-0025-probe2 negative control or mutation")
        if proc.stderr:
            print(proc.stderr[-1500:])
        return 1
    print("SUCCESS:IMP-0025-probe2 negative control and mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
