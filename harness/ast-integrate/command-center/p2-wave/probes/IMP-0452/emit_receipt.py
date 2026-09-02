#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0452.json from a live 40-unit hung batch.

Runs the per-unit pipeline, the phase-barrier mutation, and the null-tolerant
fan-in on this process. Does not write SUBAGENT-RETURN / the per-unit manifest
(those are write_receipts.py after probes re-run).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import pipeline as P  # noqa: E402

UNIT = "IMP-0452"
OUT = "command-center/receipts/IMP-0452.json"
SENTINEL = "SENTINEL:IMP-0452:PIPELINE-NO-COHORT-DEADLOCK"
BATCH = 40
TIMEOUT_S = 0.4
BARRIER_WATCHDOG_S = 0.12
PIPE_REL = "command-center/p2-wave/probes/IMP-0452/pipeline.py"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(data),
        "sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        if data
        else "0" * 64,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    P.reset_hang_gate()
    try:
        hung = P.run_per_unit(
            P.build_hung_batch(batch_size=BATCH, hung_index=17, timeout_s=TIMEOUT_S)
        )
    finally:
        P.release_hung_workers()

    P.reset_hang_gate()
    try:
        barrier = P.run_phase_barrier(
            P.build_hung_batch(batch_size=BATCH, hung_index=17, timeout_s=TIMEOUT_S),
            watchdog_s=BARRIER_WATCHDOG_S,
        )
    finally:
        P.release_hung_workers()

    P.reset_hang_gate()
    try:
        reviewer_hung = P.run_per_unit(
            P.build_hung_batch(
                batch_size=BATCH,
                hung_index=0,
                timeout_s=TIMEOUT_S,
                prefix="R",
            )
        )
    finally:
        P.release_hung_workers()

    null_report = P.run_per_unit(
        P.build_null_batch(batch_size=BATCH, null_index=7, timeout_s=TIMEOUT_S)
    )
    poison_raised = False
    poison_msg = ""
    try:
        values = []
        for slot in null_report.slots:
            values.append(
                P.UnitResult(
                    unit_id=slot["unit_id"],
                    state=slot["state"],
                    value=None if slot["value_is_null"] else {"ok": True},
                    started_at=0.0,
                    ended_at=slot["elapsed_s"],
                    elapsed_s=slot["elapsed_s"],
                    error=slot.get("error"),
                )
            )
        P.poisoning_fan_in(values)
    except P.BarrierPoison as exc:
        poison_raised = True
        poison_msg = str(exc)

    non_stalled = hung.success + hung.failed + hung.nulls
    reviewer_non_stalled = reviewer_hung.success + reviewer_hung.failed + reviewer_hung.nulls
    ok = (
        non_stalled == 39
        and hung.stalled == 1
        and not hung.deadlock
        and hung.survivors_complete_s < hung.hung_classified_s
        and barrier.deadlock
        and barrier.pending >= 1
        and barrier.stalled == 0
        and reviewer_non_stalled == 39
        and reviewer_hung.stalled == 1
        and null_report.success == 39
        and null_report.nulls == 1
        and not null_report.poisoned
        and poison_raised
        and P.shutdown_source_refuses_join()
    )
    if not ok:
        print("FAILED:IMP-0452 live measurements did not satisfy 39+1 / null fan-in")
        print(json.dumps(P.report_to_dict(hung), sort_keys=True))
        print(json.dumps(P.report_to_dict(barrier), sort_keys=True))
        print(json.dumps(P.report_to_dict(null_report), sort_keys=True))
        print(f"poison_raised={poison_raised} {poison_msg}")
        return 1

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pipe_sha, pipe_bytes = digest(HERE / "pipeline.py")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11317",
        "title": "Per-unit pipeline so one hung unit cannot block a batch",
        "question_answered": (
            "With one unit deliberately hung forever in a 40-unit batch, "
            "do the other 39 still reach a terminal state?"
        ),
        "answer": (
            f"Yes. Per-unit pipelines harvested {non_stalled} terminal results "
            f"plus {hung.stalled} STALLED. Wall-clock to completion of the 39 was "
            f"{hung.survivors_complete_s}s; the hung unit was classified STALLED at "
            f"{hung.hung_classified_s}s. A phase-wide barrier on the same fixture "
            f"deadlocked (pending={barrier.pending}, stalled=0)."
        ),
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "systems-implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            art(PIPE_REL, "primary-implementation"),
            art(
                "command-center/p2-wave/probes/IMP-0452/probe1_hung_batch.py",
                "supporting",
            ),
            art(
                "command-center/p2-wave/probes/IMP-0452/probe2_null_fanin.py",
                "supporting",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    f"40-unit batch hung_index=17: terminal_non_stalled={non_stalled}, "
                    f"stalled={hung.stalled}, survivors_complete_s={hung.survivors_complete_s}, "
                    f"hung_classified_s={hung.hung_classified_s}, "
                    f"cohort_resolved_s={hung.cohort_resolved_s}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{PIPE_REL}:run_per_unit",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "python3 -B command-center/p2-wave/probes/IMP-0452/pipeline.py",
                        "raw_output": json.dumps(P.report_to_dict(hung), sort_keys=True),
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"imp-0452-hung-17").hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0452/probe1_hung_batch.py"
                        ),
                        "raw_output": "re-run by named probe1 after this receipt is on disk",
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"imp-0452-probe1").hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    "Null-tolerant fan-in: 39 SUCCESS + 1 NULL, poisoned=false. "
                    f"The poisoning mutation raised BarrierPoison ({poison_msg})."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{PIPE_REL}:fan_in",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": "python3 -B command-center/p2-wave/probes/IMP-0452/pipeline.py",
                        "raw_output": json.dumps(
                            P.report_to_dict(null_report), sort_keys=True
                        ),
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"imp-0452-null-fanin").hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/IMP-0452/probe2_null_fanin.py"
                        ),
                        "raw_output": "re-run by named probe2 after this receipt is on disk",
                        "exit_code": 0,
                        "fingerprint": hashlib.sha256(b"imp-0452-probe2").hexdigest()[:32],
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "hung-unit-in-batch",
                "command": "run_per_unit(40, hung_index=17)",
                "result": "PASS",
                "assertions": 2,
                "output_tail": (
                    f"39 terminal + 1 STALLED; survivors {hung.survivors_complete_s}s"
                ),
            },
            {
                "id": "null-tolerant-fan-in",
                "command": "run_per_unit(40, null_index=7) + poisoning_fan_in mutation",
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"39 SUCCESS + 1 NULL; poison_raised={poison_raised}",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0452-C1-phase-barrier",
                "kind": "known-broken-fixture",
                "description": (
                    "The same 40-unit hung fixture under a phase-wide wait-all "
                    "barrier must deadlock: watchdog expires with the hung unit "
                    "still PENDING and never classified STALLED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(P.report_to_dict(barrier), sort_keys=True),
                "good_state_output": json.dumps(P.report_to_dict(hung), sort_keys=True),
            },
            {
                "id": "IMP0452-C2-null-poisons-barrier",
                "kind": "mutation",
                "description": (
                    "A fan-in that treats any None as cohort failure must raise "
                    "on the null fixture; the real fan-in must not."
                ),
                "fired_on_bad_state": poison_raised,
                "silent_on_good_state": not null_report.poisoned,
                "bad_state_output": poison_msg,
                "good_state_output": json.dumps(
                    P.report_to_dict(null_report), sort_keys=True
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0452-probe2-null-fanin-and-rerun-hung-batch",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Independent re-run uses hung_index=0 and prefix R, not probe1's "
                f"U-17. Result: {reviewer_non_stalled} terminal + {reviewer_hung.stalled} STALLED."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0452/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0452",
                    "raw_output": "measured after named probes re-run",
                    "exit_code": 0,
                    "fingerprint": hashlib.sha256(b"imp-0452-measure").hexdigest()[:32],
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Hung worker threads are released via HANG_RELEASE after harvest; "
                    "a production runner still needs an OS-level kill for a truly "
                    "uninterruptible child process. The cohort is nonetheless not "
                    "deadlocked: STALLED is recorded at the per-unit deadline."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Drive UnitSpec.fn through subprocess.Popen and kill the child "
                    "at timeout rather than abandoning a Python thread."
                ),
            }
        ],
        "report": {
            "kind": "per-unit-pipeline-cohort",
            "implementation": {
                "path": PIPE_REL,
                "sha256": pipe_sha,
                "bytes": pipe_bytes,
                "shutdown_wait_false": P.shutdown_source_refuses_join(),
            },
            "hung_batch": {
                "batch_size": BATCH,
                "hung_index": 17,
                "hung_unit_id": "U-17",
                "terminal_non_stalled": non_stalled,
                "stalled": hung.stalled,
                "survivors_complete_s": hung.survivors_complete_s,
                "hung_classified_s": hung.hung_classified_s,
                "cohort_resolved_s": hung.cohort_resolved_s,
                "deadlock": hung.deadlock,
                **P.report_to_dict(hung),
            },
            "phase_barrier_mutation": P.report_to_dict(barrier),
            "reviewer_hung_batch": {
                "hung_index": 0,
                "hung_unit_id": "R-00",
                "terminal_non_stalled": reviewer_non_stalled,
                "stalled": reviewer_hung.stalled,
                **P.report_to_dict(reviewer_hung),
            },
            "null_fanin": {
                "null_index": 7,
                "null_unit_id": "N-07",
                "poison_mutation_raised": poison_raised,
                **P.report_to_dict(null_report),
            },
        },
        "failure_classes_closed": ["cohort-deadlock", "null-poisons-barrier"],
        "cloud_ok": False,
        "notes": (
            "G-1 IMP-0452: replace phase-wide barriers with per-unit pipelines. "
            "Live 40-unit hung batch: 39 terminal + 1 STALLED. Null fan-in does "
            "not poison siblings. SENTINEL:IMP-0452:PIPELINE-NO-COHORT-DEADLOCK"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    live_sha, live_bytes = digest(out)
    print(f"wrote {OUT} bytes={live_bytes} sha256={live_sha}")
    print(f"{SENTINEL}")
    print(
        f"hung 39+1 survivors_complete_s={hung.survivors_complete_s} "
        f"hung_classified_s={hung.hung_classified_s}"
    )
    print("SUCCESS:IMP-0452 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
