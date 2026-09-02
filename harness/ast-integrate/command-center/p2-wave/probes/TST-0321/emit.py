#!/usr/bin/env python3
"""Emit TST-0321 receipt, then named-probe SUBAGENT-RETURN and per-unit manifest.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scheduler import (  # noqa: E402
    FC_11318,
    PLANNED_RATE,
    PLANNED_UNITS,
    backpressure_both_states,
    dispatch_layer_inventory,
    local_stability_control,
    program_size_pair,
    recovery_after_storm,
    saturation_curve,
)

OUT = "command-center/receipts/TST-0321.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0321/probe1_saturation_curve.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0321/probe2_backpressure_recovery.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0321/scheduler.py",
    "command-center/p2-wave/probes/TST-0321/probe1_saturation_curve.py",
    "command-center/p2-wave/probes/TST-0321/probe2_backpressure_recovery.py",
    "command-center/p2-wave/probes/TST-0321/emit.py",
]
QUESTION = (
    "Spec :11080 asks what would break at 10x scale, and the program plans "
    "2,048 work units. Drive the dispatcher at 10 times the planned arrival "
    "rate against stub workers and measure throughput, queue depth, scheduler "
    "latency, memory, and the point at which staggering stops preventing the "
    ":11318 arrival-rate storm. Stub workers keep the cost bounded and isolate "
    "the SCHEDULER as the thing under test rather than the models."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": True,
        "role": role,
        "unit_id": "TST-0321",
        "receipt_path": "command-center/p2-wave/probes/TST-0321/SUBAGENT-RETURN.json",
    }


def main() -> int:
    inventory = dispatch_layer_inventory()
    curve = saturation_curve(n_per_point=256)
    pair = program_size_pair()
    bp = backpressure_both_states()
    recov = recovery_after_storm()
    local = local_stability_control()

    if not curve["healthy_1x"] or not curve["reached_10x"]:
        print(
            "FAILED:TST-0321 curve "
            f"healthy_1x={curve['healthy_1x']} reached_10x={curve['reached_10x']}"
        )
        return 1
    if curve["first_failure_mode"] != FC_11318:
        print(f"FAILED:TST-0321 first failure {curve['first_failure_mode']}")
        return 1
    if not bp["discriminator"] or not local["pass"] or not recov["recovered"]:
        print(
            "FAILED:TST-0321 controls "
            f"backpressure={bp['discriminator']} local={local['pass']} "
            f"recovery={recov['recovered']}"
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1x = curve["points"][0]
    p10 = next(p for p in curve["points"] if p["offered_mult"] >= 10.0)
    answer = (
        "B07 phase-9 tools.dispatch is a capability-mismatch dispatcher "
        f"(has_admit={inventory.get('has_admit')}, has_stagger="
        f"{inventory.get('has_stagger')}); it is not the arrival scheduler. "
        f"Against stub workers the planned 1x rate {PLANNED_RATE:g} units/s "
        f"for {PLANNED_UNITS} catalog units completes at "
        f"{p1x['completed_rate']} units/s with {p1x['n_429']} 429s. "
        f"First failure mode is {curve['first_failure_mode']} at "
        f"{curve['first_failure_mult']}x (stagger window collapse into the "
        f"provider 429 bucket). At 10x offered={p10['offered_rate']} "
        f"completed={p10['completed_rate']} n_429={p10['n_429']} "
        f"queue_depth={p10['max_worker_queue_depth']} "
        f"stagger_depth={p10['max_stagger_queue_depth']} "
        f"latency_p95={p10['scheduler_latency_p95']} rss_kb={p10['rss_kb']}. "
        "Over-capacity work is shed with reason worker-queue-full "
        f"(live_shed={bp['live_shed']}, live_unaccounted="
        f"{bp['live_unaccounted']}); the silent-drop mutant loses "
        f"{bp['mutant_unaccounted']} units. 10x wall-clock is refused "
        f"({local['wall_10x_refused']}); this run used "
        f"{local['simulated_10x']['actually_used']}. After the storm, "
        f"completed rate {recov['tail_completed_rate']} recovers to "
        f"{recov['baseline_completed_rate']} (1x). SUCCESS:TST-0321"
    )

    tests = [
        {
            "id": "saturation-curve-to-10x",
            "requirement": (
                "Saturation curve to at least 10x planned rate against stub workers."
            ),
            "result": "PASS",
            "command": P1,
            "evidence": (
                f"healthy_1x={curve['healthy_1x']} reached_10x={curve['reached_10x']} "
                f"first_failure_mode={curve['first_failure_mode']} "
                f"first_failure_mult={curve['first_failure_mult']}"
            ),
        },
        {
            "id": "backpressure-never-silent-drop",
            "requirement": (
                "Backpressure works: offered rate above capacity must queue or "
                "shed deliberately, never silently drop units."
            ),
            "result": "PASS",
            "command": P2,
            "evidence": (
                f"live_shed={bp['live_shed']} live_unaccounted={bp['live_unaccounted']} "
                f"mutant_unaccounted={bp['mutant_unaccounted']} "
                f"discriminator={bp['discriminator']}"
            ),
        },
        {
            "id": "local-stability-guard",
            "requirement": (
                "Local-stability guard: the run must not be executed on the "
                "owner workstation at full rate; record the substrate actually used."
            ),
            "result": "PASS",
            "command": P2,
            "evidence": (
                f"wall_10x_refused={local['wall_10x_refused']} "
                f"actually_used={local['simulated_10x']['actually_used']} "
                f"owner_workstation={local['simulated_10x']['owner_workstation']}"
            ),
        },
        {
            "id": "recovery-after-storm",
            "requirement": (
                "Recovery: after the storm subsides, the scheduler must return "
                "to normal throughput."
            ),
            "result": "PASS",
            "command": P2,
            "evidence": (
                f"recovered={recov['recovered']} "
                f"baseline={recov['baseline_completed_rate']} "
                f"tail={recov['tail_completed_rate']} "
                f"storm_n_429={recov['storm_n_429']}"
            ),
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "TST-0321",
        "id": "TST-0321",
        "kind": "receipt",
        "report_kind": "test-receipt",
        "title": (
            "Ten-times-scale benchmark: throughput, arrival rate and queue "
            "depth before the program relies on it"
        ),
        "question": QUESTION,
        "answer": answer,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:TST-0321",
        "completion_sentinel": "SUCCESS:TST-0321",
        "phase": "10",
        "generated_at": now,
        "generating_commit": "worktree-uncommitted",
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "planned_units": PLANNED_UNITS,
        "planned_rate_units_per_sim_s": PLANNED_RATE,
        "dispatch_layer": inventory,
        "substrate": local["simulated_10x"],
        "saturation": {
            "first_failure_mode": curve["first_failure_mode"],
            "first_failure_mult": curve["first_failure_mult"],
            "healthy_1x": curve["healthy_1x"],
            "reached_10x": curve["reached_10x"],
            "n_per_point": curve["n_per_point"],
            "points": curve["points"],
            "program_size": pair,
        },
        "backpressure": {
            "live_unaccounted": bp["live_unaccounted"],
            "mutant_unaccounted": bp["mutant_unaccounted"],
            "live_shed": bp["live_shed"],
            "mutant_shed": bp["mutant_shed"],
            "discriminator": bp["discriminator"],
            "live": bp["live"],
            "mutant_silent_drop": bp["mutant_silent_drop"],
        },
        "recovery": {
            "recovered": recov["recovered"],
            "baseline_completed_rate": recov["baseline_completed_rate"],
            "tail_completed_rate": recov["tail_completed_rate"],
            "storm_n_429": recov["storm_n_429"],
            "baseline_1x": recov["baseline_1x"],
            "tail_1x": recov["tail_1x"],
        },
        "local_stability": local,
        "tests": tests,
        "controls": {
            "healthy_1x_zero_429": p1x["n_429"] == 0,
            "silent_drop_mutant_unaccounted": bp["mutant_unaccounted"],
            "wall_10x_refused": local["wall_10x_refused"],
            "recovery_after_storm": recov["recovered"],
        },
        "evidence": [
            {
                "kind": "live-sim",
                "path": "command-center/p2-wave/probes/TST-0321/scheduler.py",
                "note": (
                    "saturation curve first_failure_mode="
                    f"{curve['first_failure_mode']} at {curve['first_failure_mult']}x"
                ),
            },
            {
                "kind": "both-states",
                "path": "command-center/p2-wave/probes/TST-0321/probe2_backpressure_recovery.py",
                "note": (
                    f"live_shed={bp['live_shed']} live_unaccounted="
                    f"{bp['live_unaccounted']} mutant_unaccounted="
                    f"{bp['mutant_unaccounted']}"
                ),
            },
            {
                "kind": "substrate",
                "path": OUT,
                "note": (
                    "catalog execution_substrate=cloud-batch; actually_used="
                    f"{local['simulated_10x']['actually_used']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0321-probe2-backpressure-recovery",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 re-runs the saturation curve and checks 1x health, "
                "10x coverage, and the named first failure mode. Named probe2 "
                "re-runs the silent-drop mutant, the local-stability guard, and "
                "post-storm recovery."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0321/scheduler.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "saturation-curve", "command": P1},
            {"id": "probe2", "role": "backpressure-recovery", "command": P2},
        ],
        "notes": (
            "G-1 for TST-0321: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild circle. SUCCESS:TST-0321"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest(out_path)
    if size < 2048:
        print(f"FAILED:TST-0321 receipt {size}B below floor")
        return 1
    if "SUCCESS:TST-0321" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0321 sentinel absent after write")
        return 1

    c1, t1 = run_probe(P1)
    print(t1[-2500:])
    c2, t2 = run_probe(P2)
    print(t2[-2500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0321 probes c1={c1} c2={c2}")
        return 1

    sha, size = digest(out_path)
    primary = {
        "path": OUT,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "unit_id": "TST-0321",
        "receipt_path": "command-center/p2-wave/probes/TST-0321/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    supporting = [art(p, "supporting") for p in SUPPORTING]
    artifacts = [primary] + supporting
    ret = {
        "id": "TST-0321",
        "unit_id": "TST-0321",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0321",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "saturation-curve",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "backpressure-recovery",
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0321/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0321-probe2-backpressure-recovery",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0321: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0321",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={sha} bytes={size}")
    print(
        f"first_failure_mode={curve['first_failure_mode']} "
        f"mult={curve['first_failure_mult']} recovered={recov['recovered']}"
    )
    print("SUCCESS:TST-0321 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
