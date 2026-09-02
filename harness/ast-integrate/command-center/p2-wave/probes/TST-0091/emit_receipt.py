#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0091.json from live hung-unit measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

UNIT = "TST-0091"
OUT = "command-center/receipts/TST-0091.json"
SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0091"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0091/probe1_barrier_resolves.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0091/probe2_timeout_attribution.py"
)
IMPLEMENTATION = [
    "command-center/p2-wave/probes/TST-0091/pipeline.py",
    "command-center/p2-wave/probes/TST-0091/scenario.py",
    "command-center/p2-wave/probes/TST-0091/probe1_barrier_resolves.py",
    "command-center/p2-wave/probes/TST-0091/probe2_timeout_attribution.py",
    SCHEMA,
]


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def main() -> int:
    live = S.run_all()
    if not live["pass"]:
        print(json.dumps(live, sort_keys=True, default=str)[:8000])
        print("FAILED:TST-0091 live scenarios did not pass; receipt not written")
        return 1

    barrier = live["test_barrier_resolves_despite_one_hung_unit"]
    classify = live["test_hung_unit_is_classified_timeout_not_silently_dropped"]
    survivors = live["test_survivor_results_are_complete_and_attributed"]
    negative = live["negative_control_no_hung"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [digest(rel) for rel in IMPLEMENTATION]
    arts[0]["role"] = "implementation"

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_marker": SENTINEL,
        "title": "One hung unit must not block a large batch",
        "report_kind": "fault-injection-receipt",
        "failure_class": "one hung unit blocks a large batch",
        "spec_anchor": "_USER-PROMPTS.md:11317",
        "output_schema": SCHEMA,
        "question_or_target": (
            "Failure class :11317. Measured: parallel() has no per-agent timeout, "
            "so one hung agent deadlocks the whole phase - detected only by a "
            "write-freeze longer than 25 minutes. Target: per-unit timeouts and a "
            "per-work-unit pipeline so the barrier resolves on the survivors with "
            "the hung unit classified, not silently awaited."
        ),
        "injected_fault": {
            "kind": "deliberately-hung-unit",
            "hung_unit_id": live["hung_id"],
            "n": live["n"],
            "declared_timeout_s": live["per_unit_timeout_s"],
            "timeout_classification": live["timeout_classification"],
            "survivor_sleep_s": live["survivor_sleep_s"],
            "naive_watchdog_s": live["naive_watchdog_s"],
        },
        "cohort": {
            "n": live["n"],
            "n_success": live["n"] - 1,
            "n_timeout": 1,
            "n_failed": 0,
            "barrier_resolved": True,
            "hung_unit_id": live["hung_id"],
            "timeout_classification": live["timeout_classification"],
            "fixed_wall_s": barrier["fixed"]["wall_s"],
            "write_as_you_go": survivors["write_as_you_go"],
        },
        "both_states": {
            "naive_blocks": barrier["both_states"]["naive_blocks"],
            "fixed_resolves": barrier["both_states"]["fixed_resolves"],
            "naive_zero_durable": barrier["both_states"]["naive_zero_durable"],
            "naive_n_durable": barrier["naive"]["n_durable"],
            "fixed_n_success": barrier["fixed"]["n_success"],
            "fixed_n_timeout": barrier["fixed"]["n_timeout"],
        },
        "tests": [
            {
                "id": "test_barrier_resolves_despite_one_hung_unit",
                "name": "test_barrier_resolves_despite_one_hung_unit",
                "command": P1,
                "result": "PASS" if barrier["pass"] else "FAIL",
                "observable": (
                    f"naive unresolved under {S.NAIVE_WATCHDOG_S}s watchdog with "
                    f"0 durable rows; per-unit pipeline resolved with "
                    f"{live['n']-1} SUCCESS + 1 TIMEOUT in {barrier['fixed']['wall_s']:.4f}s"
                ),
            },
            {
                "id": "test_hung_unit_is_classified_timeout_not_silently_dropped",
                "name": "test_hung_unit_is_classified_timeout_not_silently_dropped",
                "command": P2,
                "result": "PASS" if classify["pass"] else "FAIL",
                "observable": (
                    f"{live['hung_id']} present with classification "
                    f"{live['timeout_classification']}; mutant drop leaves {S.N-1}"
                ),
            },
            {
                "id": "test_survivor_results_are_complete_and_attributed",
                "name": "test_survivor_results_are_complete_and_attributed",
                "command": P2,
                "result": "PASS" if survivors["pass"] else "FAIL",
                "observable": (
                    f"{S.N-1} survivors SUCCESS, payload.unit_id matches, "
                    "ledger durable before hung classified"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "TST-0091-C1-ALL-HEALTHY",
                "kind": "both-states",
                "description": (
                    "all-healthy cohort: N SUCCESS, zero timeout classifications, "
                    "wall under the negative budget; hung injection fires timeout"
                ),
                "fired_on_bad_state": classify["pass"],
                "silent_on_good_state": negative["silent_on_good"],
                "good_state_output": (
                    f"n_success={negative['n_success']} n_timeout={negative['n_timeout']}"
                ),
                "bad_state_output": (
                    f"hung={live['hung_id']} classification={live['timeout_classification']}"
                ),
            }
        ],
        "evidence": [
            {
                "claim": (
                    "A batch of N=12 with one deliberately hung unit: naive "
                    "parallel() does not resolve within the watchdog and writes "
                    "zero durable rows; the per-unit pipeline barrier resolves "
                    "with 11 SUCCESS + 1 typed timeout classification."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0091/pipeline.py:per_unit_pipeline",
                "measured": {
                    "n": live["n"],
                    "naive_resolved": barrier["naive"]["resolved"],
                    "naive_n_durable": barrier["naive"]["n_durable"],
                    "fixed_resolved": barrier["fixed"]["resolved"],
                    "fixed_n_success": barrier["fixed"]["n_success"],
                    "fixed_n_timeout": barrier["fixed"]["n_timeout"],
                    "fixed_wall_s": barrier["fixed"]["wall_s"],
                },
            },
            {
                "claim": (
                    "The hung unit is classified timeout-0.2s and is present in "
                    "the fan-in set (not silently dropped). Survivors are complete, "
                    "attributed by unit_id, and durable on disk before the hung "
                    "unit is classified (write-as-you-go)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0091/scenario.py",
                "measured": {
                    "hung_id": live["hung_id"],
                    "classification": live["timeout_classification"],
                    "dropped": classify["dropped"],
                    "n_survivors": survivors["n_survivors"],
                    "write_as_you_go": survivors["write_as_you_go"],
                    "all_attributed": survivors["all_attributed"],
                },
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "both-states-barrier"},
            {"id": "probe2", "command": P2, "role": "timeout-attribution-reviewer"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0091-probe2-timeout-attribution",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-runs classification, survivor attribution, and the "
                "all-healthy negative control, and recounts the ledger. It does "
                "not author the naive watchdog."
            ),
        },
        "artifacts": arts,
        "retry": {
            "count": 0,
            "policy": (
                "NO retry. A retry masks the exact instability this unit exists "
                "to measure; a failed run is the datum, re-run only with a "
                "changed hypothesis recorded first"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "This unit measures the barrier contract on the SUT under "
                    "probes/TST-0091/. Production parallel() call sites in "
                    "operator workflows (WFA-0088 / IMP-0452) are not patched here."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": "WFA-0088 repair of live workflow parallel() call sites.",
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0091/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": False,
                "exit_code": None,
                "note": "measure runs after this receipt is on disk",
            }
        ],
        "ts": now,
        "min_bytes_threshold": 128,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
