"""Shared CNF-0136 probe scenario: induced faults, genuine REFUTED, idempotence."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))

from cnf0136.queue import VerdictLaunderingError  # noqa: E402
from cnf0136.record import validate_record  # noqa: E402
from cnf0136.scheduler import (  # noqa: E402
    Clock,
    ConfirmationQueueScheduler,
    Job,
    RunnerEvent,
    mark_in_flight,
)
from cnf0136.taxonomy import (  # noqa: E402
    FORBIDDEN_INFRA_VERDICTS,
    TAXONOMY,
    evidence_looks_like_infra,
    map_fault,
    naive_launder_to_refuted,
)

CONFIRMER = {"identity": "cnf0136-confirmer", "vendor": "anthropic"}
ARRIVAL_RATE_HZ = 10.0


def _job(claim_id: str, wave: str, timeout_seconds: int = 30) -> Job:
    return Job(
        claim_id=claim_id,
        confirmer=CONFIRMER,
        wave=wave,
        timeout_seconds=timeout_seconds,
    )


def reviewer_infra_refuted(records: list[dict[str, Any]]) -> list[str]:
    """Grep emitted records for REFUTED whose evidence is an infra error string."""
    bad: list[str] = []
    for rec in records:
        if rec.get("verdict") != "REFUTED":
            continue
        blob = " ".join(rec.get("discrepancies") or []) + " " + str(
            rec.get("residual_caveat") or ""
        )
        if evidence_looks_like_infra(blob):
            bad.append(str(rec.get("record_id")))
    return bad


def run_scenario() -> dict[str, Any]:
    clock = Clock(0)
    sched = ConfirmationQueueScheduler(
        arrival_rate_hz=ARRIVAL_RATE_HZ,
        clock=clock,
        vendor_rate_cap_hz=None,
    )
    if sched.quota_posture != "NOT-CHECKED":
        raise RuntimeError(f"quota_posture={sched.quota_posture}")

    arrival_rate_required = False
    try:
        ConfirmationQueueScheduler(arrival_rate_hz=0)
    except ValueError:
        arrival_rate_required = True

    kill = sched.dispatch(
        _job("claim-kill", "kill"),
        RunnerEvent(
            kind="kill",
            claim_verdict="REFUTED",
            evidence="SIGKILL mid-stream",
        ),
    )
    crash = sched.dispatch(
        _job("claim-crash", "crash"),
        RunnerEvent(kind="crash", evidence="runner-crash"),
    )

    storm_clock = Clock(0)
    storm = ConfirmationQueueScheduler(
        arrival_rate_hz=ARRIVAL_RATE_HZ,
        clock=storm_clock,
        vendor_rate_cap_hz=None,
    )
    burst_jobs = [_job(f"claim-429-{i}", "storm") for i in range(8)]
    burst = storm.dispatch_batch(
        burst_jobs,
        lambda _j: RunnerEvent(
            kind="http-429",
            claim_verdict="REFUTED",
            evidence="http-429 429 storm",
        ),
    )
    burst_slots = [int(r["scheduled_at_ms"]) for r in burst]
    burst_gaps = [
        burst_slots[i + 1] - burst_slots[i] for i in range(len(burst_slots) - 1)
    ]
    want_gap_ms = storm.stagger_interval_ms("anthropic")

    timeout = sched.dispatch(
        _job("claim-timeout", "to", timeout_seconds=30),
        RunnerEvent(kind="timeout", timeout_seconds=30, evidence="deadline-exceeded"),
    )

    dup_job = _job("claim-dup", "dup")
    mark_in_flight(sched, dup_job)
    duplicate = sched.dispatch(
        dup_job,
        RunnerEvent(
            kind="healthy",
            claim_verdict="CONFIRMED",
            source_probe="src-healthy-aaa",
            verifier_probe="ver-healthy-bbb",
            discrepancies=["would-have-confirmed"],
        ),
    )

    genuine_job = _job("claim-genuine-refute", "healthy")
    genuine = sched.dispatch(
        genuine_job,
        RunnerEvent(
            kind="healthy",
            claim_verdict="REFUTED",
            source_probe="src-fingerprint-11111111",
            verifier_probe="ver-fingerprint-22222222",
            discrepancies=[
                "expected digest abc, observed def on fixture claim-genuine-refute"
            ],
            evidence="claim hash mismatch on fixture claim-genuine-refute",
        ),
    )
    launder_raised = False
    try:
        sched.dispatch(
            genuine_job,
            RunnerEvent(
                kind="healthy",
                claim_verdict="CONFIRMED",
                source_probe="src-fingerprint-11111111",
                verifier_probe="ver-fingerprint-33333333",
            ),
        )
    except VerdictLaunderingError:
        launder_raised = True

    idemp_job = _job("claim-idemp", "idemp")
    first = sched.dispatch(
        idemp_job,
        RunnerEvent(kind="kill", evidence="SIGKILL mid-stream"),
    )
    count_before = sched.store.count()
    second = sched.requeue_blocked(
        idemp_job,
        RunnerEvent(kind="kill", evidence="SIGKILL mid-stream"),
    )
    count_after = sched.store.count()

    two_job = _job("claim-two-strikes", "strikes")
    s1 = sched.dispatch(two_job, RunnerEvent(kind="crash", evidence="runner-crash"))
    clock.advance(1)
    s2 = sched.requeue_blocked(
        two_job, RunnerEvent(kind="crash", evidence="runner-crash")
    )

    all_records = sched.store.records() + storm.store.records()
    infra_refuted_ids = reviewer_infra_refuted(all_records)

    unsourced_confirmed_rejected = False
    try:
        validate_record(
            {
                "record_id": "a" * 32,
                "job_id": "j",
                "claim_id": "c",
                "confirmer": CONFIRMER,
                "blinding_attestation_hash": "x",
                "baseline_repro": "",
                "corrected_repro": "",
                "rollback_repro": "",
                "regression_diff": "",
                "discrepancies": [],
                "verdict": "CONFIRMED",
                "residual_caveat": "",
                "scheduled_at_ms": 0,
            }
        )
    except Exception:
        unsourced_confirmed_rejected = True

    taxonomy_ok = all(
        map_fault(cls)["verdict"] == "BLOCKED"
        and map_fault(cls)["verdict"] not in FORBIDDEN_INFRA_VERDICTS
        and naive_launder_to_refuted(cls) == "REFUTED"
        for cls in TAXONOMY
    )

    return {
        "arrival_rate_hz": ARRIVAL_RATE_HZ,
        "arrival_rate_required": arrival_rate_required,
        "quota_posture": sched.quota_posture,
        "taxonomy_ok": taxonomy_ok,
        "unsourced_confirmed_rejected": unsourced_confirmed_rejected,
        "kill": kill,
        "crash": crash,
        "timeout": timeout,
        "duplicate": duplicate,
        "burst": burst,
        "burst_slots": burst_slots,
        "burst_gaps": burst_gaps,
        "want_gap_ms": want_gap_ms,
        "genuine": genuine,
        "launder_raised": launder_raised,
        "idemp": {
            "first_id": first["record_id"],
            "second_id": second["record_id"],
            "count_before": count_before,
            "count_after": count_after,
        },
        "two_strikes": {
            "record_id": s2["record_id"],
            "same_id": s1["record_id"] == s2["record_id"],
            "parked": s2.get("parked_two_strikes"),
            "retry_len": len(s2.get("retries") or []),
        },
        "infra_refuted_ids": infra_refuted_ids,
        "induced": {
            "severed-stream": kill,
            "quota-429-storm": burst[0],
            "timeout-<n>s": timeout,
            "duplicate-dispatch": duplicate,
            "runner-crash-as-severed-stream": crash,
        },
        "record_count_main": sched.store.count(),
        "record_count_storm": storm.store.count(),
        "all_records": all_records,
    }


def main() -> int:
    data = run_scenario()
    slim = {k: data[k] for k in data if k not in {"all_records", "induced", "burst"}}
    print(json.dumps(slim, default=str)[:4000])
    print("SUCCESS:CNF-0136-scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
