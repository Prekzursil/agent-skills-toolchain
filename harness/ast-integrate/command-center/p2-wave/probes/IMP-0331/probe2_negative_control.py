#!/usr/bin/env python3
"""Named probe 2: negative control + detector-control + fidelity mutants.

Starts from the public API (not an author summary):
  * a randomly formed caucus of the same size must NOT be flagged
  * an affinity caucus on the same question MUST still fire (detector-control)
  * citing a foreign turn, or dropping a member citation, must FAIL fidelity
"""
from __future__ import annotations

import ast
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
    mutate_drop_citation,
    mutate_foreign_citation,
    report_up_fidelity,
    run_session,
)

MOD = REPO / "tools" / "council" / "topology" / "committee.py"


def _deliberate_calls_kernel() -> bool:
    src = MOD.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "deliberate_group":
            continue
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "execute_turn"
            ):
                return True
    return False


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
    random_group = session.caucuses[1]
    random_tags = cluster_tags(random_group, roster)

    affinity_delib = next(
        d for d in session.deliberations if d.group.id == "caucus-affinity"
    )
    random_delib = next(
        d for d in session.deliberations if d.group.id == "caucus-random"
    )
    good_aff = report_up_fidelity(affinity_delib.conclusion, kernel)
    good_rand = report_up_fidelity(random_delib.conclusion, kernel)
    foreign_mutant = mutate_foreign_citation(
        affinity_delib.conclusion, random_delib.turns[0].turn_id
    )
    drop_mutant = mutate_drop_citation(affinity_delib.conclusion)
    foreign_fired = not report_up_fidelity(foreign_mutant, kernel).ok
    drop_fired = not report_up_fidelity(drop_mutant, kernel).ok
    kernel_port = _deliberate_calls_kernel()

    payload = {
        "probe": "probe2-negative-control-random-not-echo",
        "unit_id": "IMP-0331",
        "random_member_ids": list(spread.random_member_ids),
        "random_tags": sorted(random_tags),
        "random_spread": spread.random_spread,
        "baseline_spread": spread.baseline_spread,
        "random_echo": spread.random_echo.as_dict(),
        "affinity_echo": spread.affinity_echo.as_dict(),
        "detector_control_affinity_fires": spread.affinity_echo.echo_chamber,
        "negative_control_random_silent": not spread.random_echo.echo_chamber,
        "fidelity_good_affinity": good_aff.as_dict(),
        "fidelity_good_random": good_rand.as_dict(),
        "fidelity_foreign_citation_fails": foreign_fired,
        "fidelity_drop_citation_fails": drop_fired,
        "kernel_execute_turn_in_deliberate_group": kernel_port,
        "random_is_mixed_clusters": random_tags == {"hawk", "dove"},
    }
    print(json.dumps(payload, sort_keys=True))

    failures: list[str] = []
    if random_tags != {"hawk", "dove"}:
        failures.append(
            f"random caucus seed={RANDOM_SEED} is not a mixed-cluster "
            f"negative control (tags={sorted(random_tags)})"
        )
    if spread.random_echo.echo_chamber:
        failures.append(
            "NEGATIVE CONTROL FAILED: random caucus flagged as echo chamber "
            f"spread={spread.random_spread} baseline={spread.baseline_spread} "
            f"ratio={spread.random_echo.ratio}"
        )
    if not spread.affinity_echo.echo_chamber:
        failures.append(
            "DETECTOR CONTROL FAILED: affinity caucus did not fire; "
            "a silent detector would vacuous-pass the random negative control"
        )
    if not good_aff.ok or not good_rand.ok:
        failures.append("good conclusions failed fidelity")
    if not foreign_fired:
        failures.append("foreign-citation mutant was accepted (fidelity silent)")
    if not drop_fired:
        failures.append("drop-citation mutant was accepted (fidelity silent)")
    if not kernel_port:
        failures.append("deliberate_group does not call kernel.execute_turn")

    if failures:
        print("FAILED:IMP-0331-probe2 " + " | ".join(failures))
        return 1
    print(
        "SUCCESS:IMP-0331-probe2 "
        f"random_echo={spread.random_echo.echo_chamber} "
        f"affinity_echo={spread.affinity_echo.echo_chamber} "
        f"foreign_fails={foreign_fired} drop_fails={drop_fired} "
        f"mixed={sorted(random_tags)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
