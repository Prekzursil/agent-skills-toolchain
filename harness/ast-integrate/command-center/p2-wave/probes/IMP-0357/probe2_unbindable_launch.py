#!/usr/bin/env python3
"""Probe 2: unbindable / unsatisfiable-by-construction criteria refused at launch.

Catalog negative control: an unsatisfiable-by-construction criterion must be
refused at launch, not discovered at stop time.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council import charter as C  # noqa: E402

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
UID = "IMP-0357"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def mutant_defer_unsatisfiable_to_stop(charter: dict) -> dict:
    """Wrong design: refuse only UNBOUND at launch; let UNSATISFIABLE through.

    Lives in the probe, not in production. If this mutant would *accept* a
    charter that production refuses, the launch-time check is load-bearing.
    """
    census = C.binding_census(charter)
    if census["unbound"]:
        return {
            "accepted": False,
            "stage": "launch",
            "reasons": [row["reason"] for row in census["unbound"]],
        }
    return {"accepted": True, "stage": "launch", "reasons": []}


def main() -> int:
    good = load("good.json")
    unbindable = load("unbindable.json")
    unsat = load("unsatisfiable.json")
    ood = load("out_of_domain.json")

    good_launch = C.attempt_launch(good)
    unbindable_launch = C.attempt_launch(unbindable)
    unsat_launch = C.attempt_launch(unsat)
    ood_launch = C.attempt_launch(ood)

    mutant_on_unsat = mutant_defer_unsatisfiable_to_stop(unsat)
    stop_on_unsat = C.evaluate_at_stop(unsat, {"unique_ideas": 50, "completeness_score": 0.5})
    stop_on_good = C.evaluate_at_stop(
        good, {"unique_ideas": 120, "completeness_score": 0.95}
    )

    report = {
        "probe": "probe2-unbindable-launch",
        "unit_id": UID,
        "good_accepted": good_launch.accepted,
        "good_stage": good_launch.stage,
        "unbindable_accepted": unbindable_launch.accepted,
        "unbindable_stage": unbindable_launch.stage,
        "unsat_accepted": unsat_launch.accepted,
        "unsat_stage": unsat_launch.stage,
        "ood_accepted": ood_launch.accepted,
        "ood_stage": ood_launch.stage,
        "mutant_would_accept_unsat": mutant_on_unsat["accepted"],
        "stop_on_unsat_evaluated": stop_on_unsat["evaluated"],
        "stop_on_unsat_stage": stop_on_unsat["stage"],
        "stop_on_good_evaluated": stop_on_good["evaluated"],
        "stop_on_good_all_satisfied": stop_on_good.get("all_satisfied"),
        "unbindable_reasons": unbindable_launch.reasons,
        "unsat_reasons": unsat_launch.reasons,
        "ood_reasons": ood_launch.reasons,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    print(
        f"good={good_launch.accepted} unbindable={unbindable_launch.accepted} "
        f"unsat={unsat_launch.accepted} ood={ood_launch.accepted} "
        f"mutant_unsat={mutant_on_unsat['accepted']} "
        f"stop_unsat_stage={stop_on_unsat['stage']}"
    )

    if not good_launch.accepted or good_launch.stage != "launch":
        return fail("measurable charter was not accepted at launch")
    if unbindable_launch.accepted:
        return fail("unbindable criterion was not refused")
    if unbindable_launch.stage != "launch":
        return fail(f"unbindable refused at {unbindable_launch.stage}, not launch")
    if not any("world_peace" in r for r in unbindable_launch.reasons):
        return fail("unbindable refusal did not name world_peace")

    if unsat_launch.accepted:
        return fail("unsatisfiable-by-construction charter was not refused")
    if unsat_launch.stage != "launch":
        return fail(f"unsatisfiable refused at {unsat_launch.stage}, not launch")
    if ood_launch.accepted:
        return fail("out-of-domain completeness_score >= 1.5 was not refused")
    if ood_launch.stage != "launch":
        return fail("out-of-domain refusal was not at launch")

    # Load-bearing: a mutant that only checks UNBOUND would let this through.
    if not mutant_on_unsat["accepted"]:
        return fail("mutant also refused unsat; launch-vs-stop contrast is vacuous")
    if stop_on_unsat["evaluated"] or stop_on_unsat["stage"] != "launch":
        return fail("unsatisfiable charter reached stop evaluation")
    if not stop_on_good["evaluated"] or not stop_on_good.get("all_satisfied"):
        return fail("good charter stop evaluation failed on a satisfying snapshot")

    # Vacuous always-true criterion is also a launch refusal (cannot fail).
    vacuous = dict(good)
    vacuous["success_criteria"] = [
        {"metric": "unique_ideas", "op": ">=", "threshold": 0}
    ]
    vac = C.attempt_launch(vacuous)
    if vac.accepted:
        return fail("vacuous unique_ideas >= 0 was accepted at launch")
    if vac.stage != "launch":
        return fail("vacuous criterion not refused at launch")

    print(
        "SUCCESS:IMP-0357-probe2 unbindable and unsatisfiable-by-construction "
        "refused at launch, not at stop"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
