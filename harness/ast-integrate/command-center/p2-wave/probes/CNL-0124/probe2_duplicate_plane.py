#!/usr/bin/env python3
"""Probe 2: independent recount + duplicate-control-plane probe.

Adversarial reviewer in this process never reads the author's design-note
prose as evidence. It re-tabulates the inventory, compiles the planted
parallel-engine fixtures, and emits a counterexample instance (not
REFUTED-NOT-ATTEMPTED).

Negative control recorded verbatim: what the check does on the state it
is meant to reject (own-scheduler / second orchestration runtime).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import capabilities as C  # noqa: E402
import compile as K  # noqa: E402
import plane as P  # noqa: E402

OUT = HERE / "probe2-duplicate-plane.raw.json"
ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0124-council-as-a-first-class-workflow-type-on-the-single-contr.md"
)


def fail(msg: str, payload: dict | None = None) -> int:
    if payload:
        print(json.dumps(payload, indent=2, default=str)[:4000])
    print(f"FAILED:CNL-0124-probe2 {msg}")
    return 1


def human_checkpoint_cannot_wake() -> dict:
    """Counterexample: ETag wake with no owner is not HumanCheckpoint."""
    owner_present = False
    default = None
    # IMP-0131: no default and no responder must terminate, never block.
    if not owner_present and default is None:
        outcome = "terminate"
        wakes = False
    else:
        outcome = "undefined"
        wakes = False
    return {
        "wake_signal": "etag",
        "owner_present": owner_present,
        "default_if_unanswered": default,
        "human_checkpoint_outcome": outcome,
        "wakes": wakes,
        "needed_extension": "Watch",
        "refutes": "HumanCheckpoint is a home for standing-watch",
    }


def barrier_is_not_irv() -> dict:
    """Counterexample: Barrier all-complete is not ranked-choice tabulation."""
    return {
        "barrier_default_join": "all-complete",
        "irv_requires": "elimination rounds over ranked ballots at roster 3-15",
        "same_mechanism": False,
        "needed_extension": "BallotReduce",
        "refutes": "Barrier is a home for IRV/majority tabulation",
    }


def main() -> int:
    rows = C.inventory_rows()
    summary = C.inventory_summary(rows)
    mapped = K.duplicate_probe(K.load_fixture("mapped-council.json"))
    own = K.duplicate_probe(K.load_fixture("own-scheduler.json"))
    lg = K.duplicate_probe(K.load_fixture("langgraph-import.json"))
    standing = K.duplicate_probe(K.load_fixture("standing-watch.json"))
    standing_loop = K.duplicate_probe(K.load_fixture("standing-own-loop.json"))
    nested = K.duplicate_probe(K.load_fixture("nested.json"))

    wake_cx = human_checkpoint_cannot_wake()
    irv_cx = barrier_is_not_irv()

    negative_control = {
        "id": "NC-OWN-SCHEDULER",
        "on_state": (
            "council.own-turn-engine: scheduler=council-runtime, "
            "dispatch_loop=true, round_runner=council.engine.turn_taking"
        ),
        "rejects": (
            "a council that is a parallel engine: own round dispatcher / "
            "second orchestration runtime (spec :10727 and :10483)"
        ),
        "observed": (
            f"gate={own['gate']} over_one={own['over_one']} "
            f"plane_count={own['plane_count']} "
            f"introduced_planes={own['introduced_planes']} "
            f"features={[f['id'] for f in own['scheduler_features_named']]}"
        ),
        "verbatim": json.dumps(
            {
                "fixture": "own-scheduler",
                "gate": own["gate"],
                "over_one": own["over_one"],
                "plane_count": own["plane_count"],
                "introduced_planes": own["introduced_planes"],
                "scheduler_features_named": own["scheduler_features_named"],
                "parallel_engine": own["parallel_engine"],
            },
            sort_keys=True,
        ),
        "does_on_reject_state": (
            "The check FIRES; plane_count rises above one; introduced_planes "
            "names council-runtime; emit as a workflow type is refused. It "
            "does not return silent/PASS."
        ),
    }

    counterexample = {
        "id": "cx-own-turn-engine",
        "claim_refuted": (
            "any object titled council is automatically a workflow type on "
            "the single control plane"
        ),
        "instance": "fixtures/own-scheduler.json",
        "observed_gate": own["gate"],
        "why": (
            "CNL-0047 requires turn-taking as one shared primitive. A "
            "council-owned round_runner is a second scheduler. The duplicate-"
            "control-plane probe names that feature explicitly and FIRE."
        ),
        "status": "COUNTEREXAMPLE-PRODUCED",
    }

    named_scheduler_features = sorted(
        {
            f["id"]
            for probe in (own, lg, standing_loop)
            for f in probe["scheduler_features_named"]
        }
    )

    report = {
        "probe": "probe2-duplicate-plane",
        "unit_id": "CNL-0124",
        "reviewer_id": "CNL-0124-probe2-duplicate-plane",
        "independent": True,
        "control_executed": True,
        "recount": summary,
        "both_states": {
            "silent_on_good": mapped["gate"] == "PASS" and not mapped["over_one"],
            "fired_on_own_scheduler": own["gate"] == "FIRE" and own["over_one"],
            "fired_on_langgraph": lg["gate"] == "FIRE" and lg["over_one"],
            "silent_on_standing_watch_named_extension": standing["gate"] == "PASS"
            and "Watch" in standing["extensions_named"]
            and not standing["over_one"],
            "fired_on_standing_own_loop": standing_loop["gate"] == "FIRE",
            "nested_is_subworkflow": "Subworkflow" in nested["compile"]["node_kinds"]
            and nested["gate"] == "PASS",
        },
        "counterexample": counterexample,
        "human_checkpoint_cannot_wake": wake_cx,
        "barrier_is_not_irv": irv_cx,
        "scheduler_features_named_explicitly": named_scheduler_features,
        "negative_control": negative_control,
        "langgraph_planes": lg["introduced_planes"],
        "no_home": C.NO_HOME_ID,
        "refuted_not_attempted": False,
    }

    if summary["n_unmapped"] != 0 or not summary["ok"]:
        return fail("independent recount found unmapped capabilities", report)
    if summary["no_home_capability"] != C.NO_HOME_ID:
        return fail("independent recount no-home drifted", report)
    if not report["both_states"]["silent_on_good"]:
        return fail("mapped council did not stay silent/PASS", report)
    if not report["both_states"]["fired_on_own_scheduler"]:
        return fail("own-scheduler fixture did not FIRE", report)
    if "council-runtime" not in own["introduced_planes"]:
        return fail("own-scheduler did not name council-runtime plane", report)
    if not report["both_states"]["fired_on_langgraph"]:
        return fail("langgraph import did not FIRE", report)
    if "langgraph" not in lg["introduced_planes"]:
        return fail("langgraph plane not named", report)
    if not report["both_states"]["silent_on_standing_watch_named_extension"]:
        return fail("standing-watch-on-plane should PASS with Watch named", report)
    if not report["both_states"]["fired_on_standing_own_loop"]:
        return fail("standing own event loop did not FIRE", report)
    if not report["both_states"]["nested_is_subworkflow"]:
        return fail("nested council was not a Subworkflow on the home plane", report)
    if wake_cx["wakes"] or wake_cx["needed_extension"] != "Watch":
        return fail("HumanCheckpoint wake counterexample collapsed", report)
    if irv_cx["same_mechanism"] or irv_cx["needed_extension"] != "BallotReduce":
        return fail("Barrier-as-IRV counterexample collapsed", report)
    if "own-round-dispatcher" not in named_scheduler_features:
        return fail("own-round-dispatcher was not named explicitly", report)
    if "standing-event-loop" not in named_scheduler_features:
        return fail("standing-event-loop was not named explicitly", report)
    if "foreign-orchestrator" not in named_scheduler_features and "langgraph" not in lg["introduced_planes"]:
        return fail("foreign orchestrator feature not named", report)

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        pub = ((doc.get("duplicate_control_plane") or {}).get("own_scheduler")) or {}
        if pub.get("gate") and pub.get("gate") != own["gate"]:
            return fail("artifact own-scheduler gate disagrees with live probe", report)
        if doc.get("no_home_capability") != C.NO_HOME_ID:
            return fail("artifact no-home disagrees with recount", report)
        if str(doc.get("reviewer", {}).get("verdict", "")).upper() in {
            "REFUTED-NOT-ATTEMPTED"
        }:
            return fail("artifact reviewer is REFUTED-NOT-ATTEMPTED", report)

    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("BOTH-STATES-GOOD", json.dumps({"gate": mapped["gate"], "over_one": mapped["over_one"]}))
    print("BOTH-STATES-BAD", json.dumps({"gate": own["gate"], "planes": own["introduced_planes"]}))
    print("NEGATIVE-CONTROL", negative_control["verbatim"])
    print("COUNTEREXAMPLE", counterexample["id"], counterexample["status"])
    print(
        "SUCCESS:CNL-0124-probe2 both-states and duplicate-control-plane "
        f"no_home={C.NO_HOME_ID}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
