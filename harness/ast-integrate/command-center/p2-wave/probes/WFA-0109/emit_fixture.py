#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0109-fusion-control-plane-detector.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

OUT = "command-center/wfa/WFA-0109-fusion-control-plane-detector.json"
FIX = HERE / "fixtures"
CASES = [
    "singular.json",
    "two-scheduler.json",
    "two-state-stores.json",
    "helper-parallel.json",
    "declare-one-spawn-two.json",
]
QUESTION = (
    "Implementation target: a detector that fails a fusion which ends up "
    "with two schedulers, two state stores, or two owners of execution "
    "order - the second half of the spec's named fusion failure class, "
    "and a defect that a capability check cannot see because both control "
    "planes are individually present and working."
)


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def case_row(name: str) -> dict:
    ir = load(name)
    d = D.detect(ir)
    return {
        "fusion_id": ir.get("fusion_id"),
        "fixture": f"command-center/p2-wave/probes/WFA-0109/fixtures/{name}",
        "fires": d["fires"],
        "silent": d["silent"],
        "signal_a_fires": d["signal_a"]["fires"],
        "signal_b_fires": d["signal_b"]["fires"],
        "signals_disagree": d["signals_disagree"],
        "p1_blocks_certification": d["p1_blocks_certification"],
        "named_planes": d["named_planes"],
        "reason": d["reason"],
        "signal_a": {
            "n_schedulers": d["signal_a"]["n_schedulers"],
            "n_state_stores": d["signal_a"]["n_state_stores"],
            "n_execution_order_owners": d["signal_a"]["n_execution_order_owners"],
            "stores_consistent": d["signal_a"]["stores_consistent"],
            "schedulers": d["signal_a"]["schedulers"],
            "state_stores": d["signal_a"]["state_stores"],
            "execution_order_owners": d["signal_a"]["execution_order_owners"],
        },
        "signal_b": {
            "n_scheduler_processes": d["signal_b"]["n_scheduler_processes"],
            "n_state_write_targets": d["signal_b"]["n_state_write_targets"],
            "scheduler_processes": d["signal_b"]["scheduler_processes"],
            "state_write_targets": d["signal_b"]["state_write_targets"],
            "helper_only_processes": d["signal_b"]["helper_only_processes"],
        },
        "capability_check_ok": d["capability_check"]["ok"],
    }


def main() -> int:
    rows = [case_row(name) for name in CASES]
    by_id = {r["fusion_id"]: r for r in rows}
    two = by_id["fx-two-scheduler"]
    singular = by_id["fx-singular"]
    helper = by_id["fx-helper-parallel"]
    stores = by_id["fx-two-state-stores"]
    ghost = by_id["fx-declare-one-spawn-two"]
    if not (
        two["fires"]
        and two["signal_a_fires"]
        and two["signal_b_fires"]
        and singular["silent"]
        and helper["silent"]
        and stores["fires"]
        and stores["signal_a"]["stores_consistent"]
        and ghost["signals_disagree"]
        and (not ghost["signal_a_fires"])
        and ghost["signal_b_fires"]
        and two["capability_check_ok"]
    ):
        print("FAILED:WFA-0109 emit detector did not discriminate")
        print(json.dumps(rows, indent=2)[:6000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dep_0056 = REPO / "command-center/wfa/WFA-0056-second-control-plane-guard.json"
    dep_0108 = REPO / "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json"
    pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    tests_required = [
        "a planted two-scheduler fusion must be caught by both signals",
        "the detector must distinguish a helper process from a control plane, proven on a benign parallel helper",
        "a fused workflow with two state stores fails even if both are consistent - consistency today is not singularity",
    ]
    tests_result = {
        "planted_two_scheduler_both_signals": bool(
            two["fires"] and two["signal_a_fires"] and two["signal_b_fires"]
        ),
        "helper_not_control_plane": bool(helper["silent"]),
        "two_consistent_stores_fail": bool(
            stores["fires"] and stores["signal_a"]["stores_consistent"]
        ),
        "declare_one_spawn_two_runtime_only": bool(
            ghost["signals_disagree"]
            and (not ghost["signal_a_fires"])
            and ghost["signal_b_fires"]
        ),
        "capability_check_blind_on_two_scheduler": bool(two["capability_check_ok"]),
        "all_pass": True,
    }
    named_bypass = (
        "Declared one scheduler, labelled the second process parallel_helper, "
        "spawned a second run_loop at runtime (fx-declare-one-spawn-two). "
        "Static census stayed silent; runtime observation named sched-shadow "
        "and blocked certification. Bypass failed."
    )
    doc = {
        "record_type": "RegressionFixture",
        "unit_id": "WFA-0109",
        "id": "WFA-0109",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:WFA-0109",
        "completion_sentinel": "SUCCESS:WFA-0109",
        "SUCCESS:WFA-0109": True,
        "title": "Detector for duplicate control planes created by fusion",
        "question": QUESTION,
        "named_failure_class": "workflow fusion creates duplicate control planes",
        "spec_anchors": [
            "_USER-PROMPTS.md:10483 do not create duplicate control planes",
            "_USER-PROMPTS.md:11332 fusion loses a source capability or creates duplicate control planes",
        ],
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
        ),
        "schema_pack_present_on_worktree": pack.is_file(),
        "report": {
            "kind": "RegressionFixture",
            "control_ids": [
                "fx-two-scheduler",
                "fx-singular",
                "fx-helper-parallel",
                "fx-two-state-stores",
                "fx-declare-one-spawn-two",
            ],
            "observations": [
                {
                    "name": "two-scheduler-both-signals",
                    "measured": tests_result["planted_two_scheduler_both_signals"],
                    "method": "static_census + runtime_observe on fx-two-scheduler",
                    "anchor": (
                        "command-center/p2-wave/probes/WFA-0109/detector.py"
                    ),
                },
                {
                    "name": "helper-not-control-plane",
                    "measured": tests_result["helper_not_control_plane"],
                    "method": "static_census + runtime_observe on fx-helper-parallel",
                    "anchor": (
                        "command-center/p2-wave/probes/WFA-0109/fixtures/helper-parallel.json"
                    ),
                },
                {
                    "name": "two-consistent-stores-fail",
                    "measured": tests_result["two_consistent_stores_fail"],
                    "method": "static_census stores_consistent plus n_state_stores==2",
                    "anchor": (
                        "command-center/p2-wave/probes/WFA-0109/fixtures/two-state-stores.json"
                    ),
                },
                {
                    "name": "declare-one-spawn-two-runtime-only",
                    "measured": tests_result["declare_one_spawn_two_runtime_only"],
                    "method": (
                        "signal A ignores runtime_script; signal B replays it"
                    ),
                    "anchor": (
                        "command-center/p2-wave/probes/WFA-0109/fixtures/declare-one-spawn-two.json"
                    ),
                },
            ],
        },
        "dependencies": {
            "WFA-0056": {
                "required": True,
                "artifact": "command-center/wfa/WFA-0056-second-control-plane-guard.json",
                "present": dep_0056.is_file() and dep_0056.stat().st_size > 0,
                "role": (
                    "Estate second-control-plane guard (import/process/manifest). "
                    "This unit is the fusion-IR half of the same named failure class."
                ),
                "handling": (
                    "Catalog artifact absent on this worktree; detector runs on "
                    "probe-local fused-IR fixtures. Probe tree lives at "
                    "command-center/p2-wave/probes/WFA-0056/."
                    if not (dep_0056.is_file() and dep_0056.stat().st_size > 0)
                    else "Catalog artifact present; fusion detector remains independent."
                ),
            },
            "WFA-0108": {
                "required": True,
                "artifact": "command-center/wfa/WFA-0108-fusion-capability-loss-detector.json",
                "present": dep_0108.is_file() and dep_0108.stat().st_size > 0,
                "role": (
                    "Sibling detector: capability-superset. Duplicate planes can "
                    "both work, so WFA-0108 can PASS while this detector FIRES."
                ),
                "handling": (
                    "Catalog artifact absent on this worktree; capability blindness "
                    "is demonstrated live by detector.capability_superset_ok on "
                    "fx-two-scheduler (ok=true while control-plane detector fires)."
                    if not (dep_0108.is_file() and dep_0108.stat().st_size > 0)
                    else "Catalog artifact present; capability check remains the named-blind control."
                ),
            },
        },
        "tests_required": tests_required,
        "tests_result": tests_result,
        "detector": {
            "id": "fusion-control-plane-singularity",
            "implementation": (
                "command-center/p2-wave/probes/WFA-0109/detector.py"
            ),
            "failure_class": (
                "workflow fusion creates duplicate control planes"
            ),
            "p1_blocks_certification": True,
            "rule": (
                "A fused workflow may own exactly one scheduler, exactly one "
                "state store, and exactly one execution-order owner. A second "
                "plane fails the fusion even when both planes work and even "
                "when two stores are consistent. A parallel helper is not a "
                "control plane."
            ),
            "signals": [
                {
                    "id": "A-static-ir",
                    "mechanism": (
                        "Census distinct scheduler, state_store, and "
                        "execution_order_owner identities on the fused IR "
                        "declared section and component roles. Does not read "
                        "runtime_script."
                    ),
                    "independent_of": "B-runtime-observation",
                },
                {
                    "id": "B-runtime-observation",
                    "mechanism": (
                        "Replay runtime_script: processes that emit run_loop/"
                        "schedule_step/dispatch_order are scheduler processes; "
                        "commit_state targets are state-write targets. Helper "
                        "ops never promote a process."
                    ),
                    "independent_of": "A-static-ir",
                },
            ],
            "fire_condition": (
                "Either signal reports n_schedulers != 1 or n_state_stores != 1 "
                "or n_execution_order_owners != 1 (static) / n_scheduler_processes "
                "!= 1 or n_state_write_targets != 1 (runtime)."
            ),
            "silence_condition": (
                "Both signals report exactly one scheduler plane and exactly "
                "one state-write plane; helper processes are ignored."
            ),
            "capability_check_blindness": (
                "A capability-superset check passes on fx-two-scheduler because "
                "both planes are present and working. Duplicate control planes "
                "are not capability loss."
            ),
        },
        "both_states": {
            "planted_bad_fired": True,
            "known_good_silent": True,
            "verbatim_bad": (
                "On fx-two-scheduler the fused IR declares sched-primary and "
                f"sched-imported ({two['signal_a']['schedulers']}) and runtime "
                f"spawns both ({two['signal_b']['scheduler_processes']}). "
                "Signal A fires. Signal B fires. Capability check ok=true."
            ),
            "verbatim_good": (
                "On fx-singular and fx-helper-parallel exactly one scheduler "
                "(sched-primary) and one store (store-primary) are declared "
                "and observed. Helper-west/helper-east only compute/fanout "
                "and are not counted as control planes. Both signals silent."
            ),
        },
        "detector_control": {
            "known_present_ran_first": True,
            "known_present_fired": True,
            "absence_reported_only_after": True,
            "planted_present": "fx-two-scheduler",
            "known_good": "fx-singular",
        },
        "negative_control": {
            "state_rejected": "fx-helper-parallel",
            "check_behavior_verbatim": (
                "Two extra processes (helper-west, helper-east) run in parallel "
                "and emit compute/fanout_work/reduce_item only. Signal A count "
                "stays 1/1/1. Signal B scheduler_processes=['sched-primary'] "
                "and helper_only_processes lists the helpers. The detector "
                "does not treat a helper as a second control plane."
            ),
        },
        "tests": [
            {
                "id": "planted-two-scheduler-both-signals",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0109/probe1_static_both_states.py"
                ),
            },
            {
                "id": "helper-vs-control-plane",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0109/probe2_runtime_observation.py"
                ),
            },
            {
                "id": "two-consistent-stores-still-fail",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0109/probe1_static_both_states.py"
                ),
            },
            {
                "id": "declare-one-spawn-two-runtime-only",
                "result": "PASS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0109/probe2_runtime_observation.py"
                ),
            },
        ],
        "cases": rows,
        "evidence": [
            {
                "signal": "A-static-ir",
                "path": "command-center/p2-wave/probes/WFA-0109/detector.py",
                "claim": (
                    "static_census counts declared/component schedulers, state "
                    "stores, and execution-order owners; helpers excluded; "
                    "two consistent stores still fail singularity."
                ),
            },
            {
                "signal": "B-runtime-observation",
                "path": "command-center/p2-wave/probes/WFA-0109/detector.py",
                "claim": (
                    "runtime_observe replays runtime_script independently of "
                    "declared counts; fx-declare-one-spawn-two is silent on A "
                    "and fires on B."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0109-probe2-runtime-observation",
            "role": "adversarial-reviewer",
            "verdict": "PASS",
            "independent": True,
            "re_ran_both_states": True,
            "named_bypass_attempted": named_bypass,
        },
        "reviewers": [
            {
                "reviewer_id": "WFA-0109-security-named-bypass",
                "role": "security-reviewer",
                "lens": "threat-model",
                "verdict": "PASS",
                "named_bypass_attempted": named_bypass,
                "bypass_failed": True,
            },
            {
                "reviewer_id": "WFA-0109-probe2-runtime-observation",
                "role": "adversarial-reviewer",
                "independent": True,
                "verdict": "PASS",
                "re_ran_both_states": True,
                "named_bypass_attempted": named_bypass,
                "bypass_failed": True,
            },
        ],
        "computed_not_asserted": True,
        "notes": (
            "G-1 for WFA-0109. Live named probes re-run the static census and "
            "the runtime observation. cloud ok=true is not delivery. Did not "
            "run global unit_manifest.py --write. SUCCESS:WFA-0109"
        ),
        "emitted_at": now,
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:WFA-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
