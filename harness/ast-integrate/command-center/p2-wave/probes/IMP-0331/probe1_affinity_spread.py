#!/usr/bin/env python3
"""Named probe 1: affinity vs random caucus position-spread experiment.

Live measurement, not a canned assertion: form both caucuses on the same
question, compute sample stdev, and require affinity spread to be strictly
smaller AND below the echo-chamber ratio against a random baseline.
Also checks report-up fidelity (every conclusion traces to member turns).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    AFFINITY_SEED_ID,
    BASELINE_SEED,
    CAUCUS_SIZE,
    N_STANDING,
    QUESTION,
    RANDOM_SEED,
    two_cluster_roster,
)
from tools.council.topology.committee import (  # noqa: E402
    RecordingKernel,
    cluster_tags,
    run_session,
)


def main() -> int:
    roster = two_cluster_roster()
    kernel = RecordingKernel(roster)
    session = run_session(
        roster,
        question=QUESTION,
        caucus_size=CAUCUS_SIZE,
        n_standing=N_STANDING,
        affinity_seed_id=AFFINITY_SEED_ID,
        random_rng=random.Random(RANDOM_SEED),
        baseline_rng=random.Random(BASELINE_SEED),
        kernel=kernel,
    )
    spread = session.spread
    affinity_group = session.caucuses[0]
    affinity_tags = cluster_tags(affinity_group, roster)

    expected_turns = sum(len(g.member_ids) for g in session.standing) + 2 * CAUCUS_SIZE
    payload = {
        "probe": "probe1-affinity-vs-random-spread",
        "unit_id": "IMP-0331",
        "question": QUESTION,
        "affinity_member_ids": list(spread.affinity_member_ids),
        "random_member_ids": list(spread.random_member_ids),
        "affinity_spread": spread.affinity_spread,
        "random_spread": spread.random_spread,
        "baseline_spread": spread.baseline_spread,
        "affinity_echo": spread.affinity_echo.as_dict(),
        "random_echo": spread.random_echo.as_dict(),
        "affinity_reduced_vs_random": spread.affinity_reduced_vs_random,
        "affinity_cluster_tags": sorted(affinity_tags),
        "all_faithful": session.all_faithful,
        "isolation_ok": session.isolation_ok,
        "turns_executed": session.turns_executed,
        "turns_recorded": session.turns_recorded,
        "expected_turns": expected_turns,
        "report_up": session.as_dict()["report_up"],
        "fidelity": [f.as_dict() for f in session.fidelity],
    }
    print(json.dumps(payload, sort_keys=True))

    failures: list[str] = []
    if not spread.affinity_reduced_vs_random:
        failures.append(
            f"affinity_spread={spread.affinity_spread} not < "
            f"random_spread={spread.random_spread}"
        )
    if not spread.affinity_echo.echo_chamber:
        failures.append("affinity caucus was not flagged as echo chamber")
    if affinity_tags != {"hawk"}:
        failures.append(f"affinity caucus not mono-cluster: {affinity_tags}")
    if not session.all_faithful:
        failures.append("report-up fidelity failed on a live conclusion")
    if not session.isolation_ok:
        failures.append("foreign participant id leaked into a group prompt")
    if session.turns_executed != session.turns_recorded:
        failures.append("kernel turns_executed != turns_recorded")
    if session.turns_executed != expected_turns:
        failures.append(
            f"turns_executed={session.turns_executed} expected={expected_turns}"
        )
    if spread.baseline_spread <= 0:
        failures.append("random baseline spread is degenerate")

    if failures:
        print("FAILED:IMP-0331-probe1 " + " | ".join(failures))
        return 1
    print(
        "SUCCESS:IMP-0331-probe1 "
        f"affinity_spread={spread.affinity_spread:.6f} "
        f"random_spread={spread.random_spread:.6f} "
        f"baseline={spread.baseline_spread:.6f} "
        f"echo_affinity={spread.affinity_echo.echo_chamber} "
        f"faithful={session.all_faithful}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
