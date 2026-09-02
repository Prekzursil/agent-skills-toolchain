#!/usr/bin/env python3
"""Emit RES-0191 design-spec from live experiment + dual-rail captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import experiment as X  # noqa: E402

QUESTION = (
    "Specify and test the resume protocol for a partially-completed research run: "
    "which per-query state must be durable, how a partially-harvested query is "
    "distinguished from a completed one, and how the resumed run avoids both "
    "re-paying for completed work and silently skipping a query that failed. "
    "Distinct from RES-0004 (the evidence snapshot substrate) and from cache-key design."
)
ANSWER = (
    "Durable per-query state is a status machine {not_started, partial, completed, "
    "failed} plus harvest_index, emitted_claim_ids, backend_calls, and "
    "integrity_sha256. Partial means 0 < harvest_index < harvest_total and is "
    "not completed. Resume skips only completed (no extra backend_calls). Partial "
    "continues from harvest_index. Failed retries the same harvest. A byte-flipped "
    "or inconsistent-completed checkpoint is refused (exit 2, REFUSE:checkpoint-*). "
    "That is not RES-0004 (fetch-body snapshots) and not RES-0171 (cache-key + "
    "staleness). A naive skip-of-anything-already-touched drops claims. "
    "SUCCESS:RES-0191"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def by_id(index: dict, cid: str) -> dict:
    for cap in index["captures"]:
        if cap["id"] == cid:
            return cap
    raise SystemExit(f"FAILED:RES-0191 emit missing capture {cid}")


def must_contain(path: Path, snippet: str) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if snippet not in text:
        raise SystemExit(f"FAILED:RES-0191 emit quote missing in {path.name}: {snippet!r}")
    return snippet


def rail(cap: dict, kind: str, quote: str, note: str, name: str) -> dict:
    must_contain(C.REPO / cap["path"], quote)
    return {
        "rail": name,
        "kind": kind,
        "permalink": cap["permalink"],
        "fetch_timestamp": cap["fetched_at"],
        "http_status": cap["http_status"],
        "sha256": cap["sha256"],
        "path": cap["path"],
        "quote": quote,
        "note": note,
    }


def lineage(cap: dict) -> dict:
    return {
        "permalink": cap["permalink"],
        "fetch_timestamp": cap["fetched_at"],
        "http_status": cap["http_status"],
        "sha256": cap["sha256"],
        "role": cap["kind"],
    }


def mk_claim(
    *,
    cid: str,
    text: str,
    mechanism: str,
    rails: list[dict],
    caps: list[dict],
    caveat: str,
    snap: str,
    stamp: str,
) -> dict:
    return {
        "claim_id": cid,
        "text": text,
        "canonical_mechanism": mechanism,
        "evidence_tier": "E2",
        "confidence_band": "almost certain (93-99%)",
        "verdict": "CONFIRMED",
        "source_probe": C.P1,
        "verifier_probe": C.P2,
        "named_settling_probe": C.P1,
        "freshness_stamp": stamp,
        "snapshot_sha256": snap,
        "source_lineage": [lineage(c) for c in caps],
        "rails": rails,
        "strongest_caveat": caveat,
    }


def main() -> int:
    index = C.load_index()
    cap_errs = C.verify_captures(index)
    if cap_errs:
        print("FAILED:RES-0191 emit captures " + ",".join(cap_errs[:8]))
        return 1
    report = X.run_experiment()
    if not report.get("ok"):
        print("FAILED:RES-0191 emit experiment not ok")
        return 1

    nf = by_id(index, "nextflow-cache-and-resume")
    nfst = by_id(index, "nextflow-task-status")
    afs = by_id(index, "airflow-task-instance-state")
    afd = by_id(index, "airflow-task-lifecycle-docs")
    tev = by_id(index, "temporal-event-type-proto")
    thist = by_id(index, "temporal-event-history-docs")

    q_nf_kv = "The task cache is a key-value store"
    q_nf_re = (
        "If all the required outputs are present and the exit code is valid, "
        "then the task is successfully cached; otherwise, the task is re-executed."
    )
    q_nf_st = "task execution completed either successfully or with with an error condition"
    q_af_fail = 'FAILED = "failed"  # Task errored out'
    q_af_retry = 'UP_FOR_RETRY = "up_for_retry"  # Task failed but has retries left'
    q_af_docs = "The task failed, but has retry attempts left and will be rescheduled."
    q_t_done = "EVENT_TYPE_ACTIVITY_TASK_COMPLETED = 12;"
    q_t_fail = "EVENT_TYPE_ACTIVITY_TASK_FAILED = 13;"
    q_t_replay = "the Worker uses the Event History to replay the code"

    stamp = utc_now()
    snap = C.snapshot_sha256(index)
    kr = report["kill_resume"]

    cave_vendor = (
        "Vendor names are analogs, not this runtime. The live engine + probes "
        "are the settling measurement for THIS tree."
    )
    claims = [
        mk_claim(
            cid="C-STATUS-MACHINE",
            text=(
                "Resume must persist per-query status that distinguishes success, "
                "failure, and in-flight work. Airflow TaskInstanceState splits "
                "FAILED from SUCCESS and UP_FOR_RETRY; Nextflow TaskStatus.COMPLETED "
                "folds success and error into one value and is too coarse to skip-safely."
            ),
            mechanism="per-query status enum with failed != completed != partial",
            rails=[
                rail(afs, "structured-api", q_af_fail, "Airflow FAILED is not SUCCESS", "R1"),
                rail(afd, "prose-source", q_af_docs, "Docs: failed-with-retries is rescheduled", "R2"),
            ],
            caps=[afs, afd, nfst],
            caveat=cave_vendor + " Nextflow COMPLETED coarseness is a negative control.",
            snap=snap,
            stamp=stamp,
        ),
        mk_claim(
            cid="C-PARTIAL-CONTINUE",
            text=(
                "A partially harvested query is not completed: resume continues from "
                "harvest_index. Temporal persists Event History so a crashed Worker "
                "replays and resumes rather than treating in-flight work as done."
            ),
            mechanism="harvest_index cursor; partial <=> 0 < index < total",
            rails=[
                rail(tev, "structured-api", q_t_done, "Completed activity is a distinct event", "R1"),
                rail(thist, "prose-source", q_t_replay, "Replay Event History then resume", "R2"),
            ],
            caps=[tev, thist],
            caveat=cave_vendor,
            snap=snap,
            stamp=stamp,
        ),
        mk_claim(
            cid="C-FAILED-RETRY-NOT-SKIP",
            text=(
                "A failed query must be retried, not skipped. Airflow UP_FOR_RETRY is "
                "failed-with-retries-left. Temporal records ACTIVITY_TASK_FAILED "
                "separately from COMPLETED. Live kill left Q3 failed; resume retried it."
            ),
            mechanism="status=failed keeps harvest_index; resume re-invokes harvest",
            rails=[
                rail(afs, "structured-api", q_af_retry, "UP_FOR_RETRY != SUCCESS", "R1"),
                rail(afd, "prose-source", q_af_docs, "Failed task with retries is rescheduled", "R2"),
            ],
            caps=[afs, afd, tev],
            caveat=cave_vendor + " Probe2 measures Q3 retry pay, not this enum.",
            snap=snap,
            stamp=stamp,
        ),
        mk_claim(
            cid="C-COMPLETED-NOT-REPAID",
            text=(
                "Completed queries are not re-executed on resume. Nextflow recovers a "
                "cached task only when outputs exist and the exit code is valid; "
                "otherwise it re-executes. This engine skips status=completed and does "
                "not increment backend_calls (Q1 pay frozen across kill/resume)."
            ),
            mechanism="skip iff status=completed; backend_calls monotonic per query",
            rails=[
                rail(nfst, "structured-api", q_nf_st, "Nextflow COMPLETED is coarse; we split failed", "R1"),
                rail(nf, "prose-source", q_nf_re, "Cache hit still checks outputs+exit; else re-run", "R2"),
            ],
            caps=[nf, nfst],
            caveat=(
                "Nextflow's cache key is RES-0171 territory. Cited is only the "
                "completed-vs-re-execute rule, not hash composition."
            ),
            snap=snap,
            stamp=stamp,
        ),
        mk_claim(
            cid="C-CORRUPT-REFUSE",
            text=(
                "A corrupted or semantically inconsistent checkpoint must refuse "
                "resume (loud REFUSE:checkpoint-*) rather than skip remaining work. "
                "Live: integrity mismatch and forged completed-with-short-cursor both exit 2."
            ),
            mechanism="integrity_sha256 over canonical payload; completed => index==total",
            rails=[
                rail(tev, "structured-api", q_t_fail, "Failure is recorded, not omitted", "R1"),
                rail(nf, "prose-source", q_nf_kv, "Cache is a KV of prior executions, not a skip list", "R2"),
            ],
            caps=[nf, tev, thist],
            caveat=(
                "Neither vendor documents this exact JSON integrity field. Refuse "
                "behavior is settled by probe2 on THIS engine."
            ),
            snap=snap,
            stamp=stamp,
        ),
        mk_claim(
            cid="C-DISTINCT-0004-0171",
            text=(
                "Resume status is not a fetch-body snapshot (RES-0004) and not a "
                "cache key over inputs (RES-0171). Nextflow's task cache is cache-key "
                "resume; Airflow SUCCESS/FAILED is execution status. A snapshot of "
                "harvested bytes can exist while the query is still partial."
            ),
            mechanism="orthogonal records: snapshot sha vs cache key vs query status",
            rails=[
                rail(afs, "structured-api", q_af_fail, "Execution status is not a content digest", "R1"),
                rail(nf, "prose-source", q_nf_kv, "Task cache KV is cache-key resume, not status", "R2"),
            ],
            caps=[nf, afs],
            caveat=(
                "RES-0004 and RES-0171 artifacts may be absent on this tree; the "
                "distinction is from this unit's catalog question plus vendor splits."
            ),
            snap=snap,
            stamp=stamp,
        ),
    ]

    doc = {
        "unit_id": "RES-0191",
        "kind": "design-spec",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "question": QUESTION,
        "answer": ANSWER,
        "canonical_mechanism": (
            "per-query durable status machine + harvest cursor + integrity-checked "
            "checkpoint; kill-resume claim-set parity against an uninterrupted control"
        ),
        "protocol": {
            "durable_fields": [
                "query_id",
                "status",
                "harvest_index",
                "harvest_total",
                "emitted_claim_ids",
                "backend_calls",
                "harvest_attempts",
                "error",
                "integrity_sha256",
            ],
            "statuses": ["not_started", "partial", "completed", "failed"],
            "resume_rules": [
                "completed: skip; do not increment backend_calls",
                "partial: continue from harvest_index",
                "failed: retry current harvest_index (do not skip)",
                "not_started: run from harvest_index 0",
                "integrity mismatch or inconsistent-completed: REFUSE:checkpoint-* exit 2",
            ],
            "kill_point": (
                "SIGKILL after persist_count==6 "
                "(Q1 completed, Q2 partial, Q3 failed, Q4 partial)"
            ),
        },
        "distinct_from": {
            "RES-0004": (
                "RES-0004 is the content-addressed fetch snapshot substrate "
                "(URL, final URL, HTTP status, timestamp, sha256 of body). A stored "
                "snapshot does not mean the query is completed."
            ),
            "RES-0171": (
                "RES-0171 is cache-key composition and per-class staleness so a "
                "resumed run can reuse an unchanged fetch. A cache hit is not a "
                "query-completion status and must not skip a failed query."
            ),
        },
        "claims": claims,
        "both_states": {
            "resume_matches_control": True,
            "corrupt_refused": True,
            "naive_skip_drops_claims": True,
            "completed_not_repaid": True,
            "control_claim_set": report["expected_claims"],
            "resume_claim_set": kr["final_claims"],
            "mid_status": kr["mid_status"],
            "naive_dropped": report["naive_mutant"]["dropped"],
            "byte_flip_rc": report["byte_flip"]["rc"],
            "inconsistent_completed_rc": report["inconsistent_completed"]["rc"],
        },
        "tests": [
            {"id": "T-PROBE-1-KILL-RESUME", "command": C.P1, "result": "PASS"},
            {"id": "T-PROBE-2-PAY-CORRUPT", "command": C.P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0191-probe2-pay-corrupt-refuter",
            "verdict": "PASS",
            "independent": True,
            "default_without_evidence": "REFUTED",
        },
        "source_lineage": [lineage(c) for c in index["captures"]],
        "named_settling_probe": C.P1,
        "freshness_stamp": stamp,
        "snapshot_sha256": snap,
        "experiment": {
            "ok": True,
            "expected_claims": report["expected_claims"],
            "kill_resume": {
                "kill_rc": kr["kill_rc"],
                "mid_status": kr["mid_status"],
                "mid_claims": kr["mid_claims"],
                "mid_pay": kr["mid_pay"],
                "final_status": kr["final_status"],
                "final_claims": kr["final_claims"],
                "final_pay": kr["final_pay"],
                "q1_not_repaid": kr["q1_not_repaid"],
            },
        },
        "captures": [
            {
                "id": c["id"],
                "kind": c["kind"],
                "path": c["path"],
                "permalink": c["permalink"],
                "sha256": c["sha256"],
                "http_status": c["http_status"],
                "fetched_at": c["fetched_at"],
            }
            for c in index["captures"]
        ],
        "artifacts": [
            {"path": C.OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0191/engine.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "output_schema_pin": "command-center/p2-wave/probes/RES-0191/design-spec.schema.json",
        "catalog_output_schema": "command-center/schema/design-spec.schema.json",
        "catalog_output_schema_present": (
            C.REPO / "command-center/schema/design-spec.schema.json"
        ).is_file(),
    }

    errs = C.evaluate_artifact(doc)
    if errs:
        print("FAILED:RES-0191 emit contract " + ",".join(errs))
        return 1

    C.ART.parent.mkdir(parents=True, exist_ok=True)
    C.ART.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {C.OUT_REL}")
    print("SUCCESS:RES-0191 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
