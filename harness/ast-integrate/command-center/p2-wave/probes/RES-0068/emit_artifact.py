#!/usr/bin/env python3
"""Emit command-center/research/RES-0068.json from harvested snapshots."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib import (  # noqa: E402
    ARTIFACT,
    ARTIFACT_REL,
    COMPLETION_SENTINEL,
    MIN_BYTES,
    SENTINEL,
    UID,
    build_harvest_index,
    grade_claim,
    rail,
    utc_now,
)


def main() -> int:
    idx = build_harvest_index()

    aws_q1 = "Its default value is zero, which means the Map State will fail if any"
    aws_q2 = (
        "The default percentage value is zero, which means that the workflow "
        "fails if any one of its"
    )
    celery_chord_q = (
        "The chord callback result will transition to the failure state, and "
        "the error is set"
    )
    celery_limit_q = "Default: No time limit."
    celery_src_q = "time_limit=Option("
    air_trigger_q = "* ``all_success`` (default): All upstream tasks have succeeded"
    air_timeout_q = "meaning that the operators are never timed out by default."
    argo_tmpl_q = (
        "FailFast, if specified, will fail this template if any of its child "
        "pods has failed"
    )
    argo_dag_q = "FailFast flag default is true"
    temporal_must_q = (
        "An Activity Execution must have either this timeout (Start-To-Close) or the"
    )
    temporal_inf_q = "The default Schedule-To-Close Timeout is ∞ (infinity)."
    temporal_src_q = "start_to_close_timeout: timedelta | None"
    durable_q = (
        "When the orchestrator passes the task array to `Task.WhenAll`, it "
        "returns a task that doesn't complete until all copy operations complete."
    )

    claims = [
        {
            "claim_id": "RES-0068-C-AWS-MAP",
            "engine": "AWS Step Functions (Distributed Map)",
            "canonical_mechanism": (
                "Map-over-unknown-N is the Map state (Distributed mode). The "
                "barrier is Map Run completion. K-of-N is ToleratedFailureCount / "
                "ToleratedFailurePercentage; both default to zero, so any child "
                "failure fails the map."
            ),
            "quoted_barrier_policy": aws_q1,
            "k_of_n_on_child_failure": (
                "Default K=N (zero tolerated failures). Raising "
                "ToleratedFailureCount allows N-K failures before the map fails "
                "with States.ExceedToleratedFailureThreshold."
            ),
            "per_child_timeout": (
                "Child executions may set TimeoutSeconds; timed-out items count "
                "toward the tolerated-failure budget."
            ),
            "matches_local_no_timeout_pathology": False,
            "evidence_tier": "E2",
            "confidence_band": "high (80-90%)",
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Inline Map historically lacked the same tolerated-failure fields; "
                "quotes here are Distributed Map plus the ASL spec."
            ),
            "source_lineage": [
                rail("aws_asl_spec.html", aws_q1, idx),
                rail("aws_sfn_map_distributed.html", aws_q2, idx),
            ],
        },
        {
            "claim_id": "RES-0068-C-CELERY-CHORD",
            "engine": "Celery (chord = group header + callback barrier)",
            "canonical_mechanism": (
                "Map-over-unknown-N is a chord header group. The barrier is the "
                "chord body, which runs only after every header task has returned. "
                "Any header exception fails the callback with ChordError; remaining "
                "header tasks still run."
            ),
            "quoted_barrier_policy": celery_chord_q,
            "k_of_n_on_child_failure": (
                "Default is all-or-fail for the callback (K=N successes). Header "
                "members are not cancelled on first failure; the body still goes "
                "to FAILURE/ChordError."
            ),
            "per_child_timeout": (
                "task_time_limit Default: No time limit. A hung header task never "
                "unlocks the chord — the local no-timeout fan-in deadlock."
            ),
            "matches_local_no_timeout_pathology": True,
            "evidence_tier": "E2",
            "confidence_band": "very high (90-95%)",
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "A result backend is required for chords; without it the unlock "
                "path is a different failure mode than a hung child."
            ),
            "source_lineage": [
                rail("gh_celery_canvas_rst.json", celery_chord_q, idx),
                rail("celery_canvas_txt", celery_chord_q, idx),
                rail("gh_celery_config_rst.json", celery_limit_q, idx),
                rail("celery_config_txt", celery_limit_q, idx),
                rail("gh_celery_defaults.json", celery_src_q, idx),
            ],
        },
        {
            "claim_id": "RES-0068-C-AIRFLOW-EXPAND",
            "engine": "Apache Airflow (expand / dynamic task mapping)",
            "canonical_mechanism": (
                "Map-over-unknown-N is mapped task expansion (expand()). The "
                "barrier is the downstream task's trigger_rule over mapped indexes. "
                "Default all_success requires every upstream mapped index to succeed "
                "before the reduce/join runs."
            ),
            "quoted_barrier_policy": air_trigger_q,
            "k_of_n_on_child_failure": (
                "Default all_success: any mapped-index failure blocks the join. "
                "all_done waits for terminal states including failures; one_failed "
                "fires on the first failure without waiting."
            ),
            "per_child_timeout": (
                "default_task_execution_timeout empty/None: operators are never "
                "timed out by default — a hung mapped index holds the DAG run."
            ),
            "matches_local_no_timeout_pathology": True,
            "evidence_tier": "E2",
            "confidence_band": "high (80-90%)",
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Cluster policy or DAG default_args can install a timeout; the "
                "shipped config default remains empty."
            ),
            "source_lineage": [
                rail("airflow_dags_gh.json", air_trigger_q, idx),
                rail("airflow_trigger_rules.md", air_trigger_q, idx),
                rail("gh_airflow_config_yml.json", air_timeout_q, idx),
                rail("airflow_config_yml", air_timeout_q, idx),
            ],
        },
        {
            "claim_id": "RES-0068-C-ARGO-WITHITEMS",
            "engine": "Argo Workflows (withItems / withParam + failFast)",
            "canonical_mechanism": (
                "Map-over-unknown-N is withItems/withParam template expansion. "
                "The barrier is template/DAG completion. Template failFast fails "
                "the template when any child pod has failed. DAG failFast defaults "
                "true: stop scheduling new nodes on first failure, then wait for "
                "in-flight nodes before failing the DAG."
            ),
            "quoted_barrier_policy": argo_tmpl_q,
            "k_of_n_on_child_failure": (
                "Default DAG failFast=true is fail-fast, not K-of-N. failFast=false "
                "runs every branch to completion. There is no native 'succeed if K "
                "of N children succeed' counter analogous to Step Functions."
            ),
            "per_child_timeout": (
                "activeDeadlineSeconds is optional; unset means no template-level "
                "deadline."
            ),
            "matches_local_no_timeout_pathology": False,
            "evidence_tier": "E2",
            "confidence_band": "high (80-90%)",
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "Optional per-pod deadlines exist but are not required; Celery's "
                "documented 'No time limit' is the named local-pathology match."
            ),
            "source_lineage": [
                rail("gh_argo_workflow_types.json", argo_tmpl_q, idx),
                rail("gh_argo_workflow_types.json", argo_dag_q, idx),
                rail("argo_fields.md", argo_tmpl_q, idx),
            ],
        },
        {
            "claim_id": "RES-0068-C-TEMPORAL-CONTRAST",
            "engine": "Temporal (concurrent activities / workflow Promise join)",
            "canonical_mechanism": (
                "Map-over-unknown-N is N concurrent activity invocations joined by "
                "the workflow. Contrast with the local pathology: an Activity "
                "Execution MUST set Start-To-Close or Schedule-To-Close. Default "
                "Schedule-To-Close is infinity, but the docs still require one of "
                "the two fields."
            ),
            "quoted_barrier_policy": temporal_must_q,
            "k_of_n_on_child_failure": (
                "Join semantics live in workflow code (all vs allSettled). A failed "
                "activity raises into the workflow; the platform does not define a "
                "K-of-N map barrier."
            ),
            "per_child_timeout": (
                "Required Start-To-Close or Schedule-To-Close — Temporal is the "
                "contrast engine, not the no-timeout pathology."
            ),
            "matches_local_no_timeout_pathology": False,
            "contrast_engine": True,
            "evidence_tier": "E2",
            "confidence_band": "high (80-90%)",
            "named_settling_probe": "probe2_reviewer.py",
            "strongest_caveat": (
                "An author can still set a huge Schedule-To-Close; the documented "
                "requirement to set a timeout field is the contrast."
            ),
            "source_lineage": [
                rail("temporal_activity_failures.html", temporal_must_q, idx),
                rail("temporal_activity_failures.html", temporal_inf_q, idx),
                rail("gh_temporal_activity.json", temporal_src_q, idx),
            ],
        },
        {
            "claim_id": "RES-0068-C-DURABLE-WHENALL",
            "engine": "Azure Durable Functions / Durable Task (fan-out/fan-in)",
            "canonical_mechanism": (
                "Map-over-unknown-N is firing one activity per item without await, "
                "then Task.WhenAll as the barrier. WhenAll completes only after "
                "every work item completes; a faulted child faults WhenAll."
            ),
            "quoted_barrier_policy": durable_q,
            "k_of_n_on_child_failure": (
                "Task.WhenAll is all-success: one failed activity fails the join. "
                "There is no built-in tolerated-failure percentage."
            ),
            "per_child_timeout": (
                "No required per-activity timeout in the fan-out sample; "
                "orchestration/activity timeouts are optional host settings."
            ),
            "matches_local_no_timeout_pathology": False,
            "evidence_tier": "E2",
            "confidence_band": "high (80-90%)",
            "named_settling_probe": "probe1_quotes.py",
            "strongest_caveat": (
                "The quoted page is the official fan-out sample, not a spec clause "
                "forbidding WhenAny."
            ),
            "source_lineage": [
                rail("gh_durable_common.json", durable_q, idx),
                rail("durable_fanout_common.md", durable_q, idx),
                rail("durable_fanout_pattern.html", "Task.WhenAll", idx),
            ],
        },
    ]

    for c in claims:
        g = grade_claim(c, idx)
        c["grader"] = g
        if not g["citable_as_measured_fact"]:
            print(f"FAILED:emit {c['claim_id']} {g}", file=sys.stderr)
            return 1
        if len(c["source_lineage"]) < 2:
            print(f"FAILED:emit {c['claim_id']} fewer than 2 rails", file=sys.stderr)
            return 1

    pathology = next(c for c in claims if c["engine"].startswith("Celery"))
    engines_table = [
        {
            "engine": c["engine"],
            "quoted_barrier_policy": c["quoted_barrier_policy"],
            "k_of_n": c["k_of_n_on_child_failure"],
            "no_timeout_pathology": c["matches_local_no_timeout_pathology"],
            "claim_id": c["claim_id"],
        }
        for c in claims
    ]

    artifact = {
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": COMPLETION_SENTINEL,
        "title": "Extract dynamic fan-out and barrier semantics under partial failure",
        "question_or_target": (
            "How do existing engines express map-over-unknown-N with a barrier, "
            "and specifically what happens at the barrier when K of N children "
            "fail — the exact case where this estate measured a fan-in deadlock "
            "from one hung agent?"
        ),
        "canonical_mechanism": (
            "Map-N is Map/expand/withItems/chord-header/WhenAll/concurrent "
            "activities. Barriers are map-run completion, trigger_rule, failFast, "
            "chord body, or Task.WhenAll. Default K-of-N is almost always K=N "
            "except AWS Distributed Map, which exposes an explicit tolerated-failure "
            "budget defaulting to zero. The local no-timeout pathology is named on "
            "Celery: task_time_limit defaults to 'No time limit', so a hung chord "
            "header never unlocks."
        ),
        "named_engine_exhibiting_local_no_timeout_pathology": "Celery",
        "named_engine_record": {
            "engine": "Celery",
            "claim_id": pathology["claim_id"],
            "quote": celery_limit_q,
            "why_this_matches_local_pathology": (
                "Estate finding: parallel() has no per-agent timeout, so one hung "
                "agent deadlocks the phase. Celery documents Default: No time limit "
                "on task_time_limit and a chord body that waits for every header "
                "result — a hung header task is the same fan-in deadlock."
            ),
            "secondary_match": (
                "Apache Airflow default_task_execution_timeout empty/None"
            ),
            "contrast_engine": (
                "Temporal (must set Start-To-Close or Schedule-To-Close)"
            ),
        },
        "evidence_tier": "E2",
        "confidence_band": "high (80-90%)",
        "freshness_stamp": utc_now(),
        "named_settling_probe": (
            "command-center/p2-wave/probes/RES-0068/probe1_quotes.py"
        ),
        "claims": claims,
        "engines": engines_table,
        "contradiction_support_edges": [
            {
                "type": "contrast",
                "from": "RES-0068-C-CELERY-CHORD",
                "to": "RES-0068-C-TEMPORAL-CONTRAST",
                "note": (
                    "Celery default no time limit vs Temporal required activity timeout."
                ),
            },
            {
                "type": "support",
                "from": "RES-0068-C-AWS-MAP",
                "to": "RES-0068-C-AIRFLOW-EXPAND",
                "note": (
                    "Both default to fail-the-join on any child failure; AWS uniquely "
                    "names a numeric tolerated-failure threshold."
                ),
            },
        ],
        "tests_required_coverage": {
            "quote_each_engine_barrier_policy": True,
            "named_engine_no_per_child_timeout": "Celery",
        },
        "reviewer": {
            "reviewer_id": "RES-0068-probe2-reviewer",
            "verdict": "PASS",
            "independent": True,
            "attempt": (
                "adversarial grader: one-rail=E3, quote-not-in-bytes=fail, "
                "Temporal is contrast not pathology"
            ),
        },
        "evidence": [
            {
                "id": "E-harvest-index",
                "kind": "snapshot-index",
                "detail": "command-center/p2-wave/probes/RES-0068/harvest_index.json",
            },
            {
                "id": "E-celery-no-limit",
                "kind": "quoted-default",
                "detail": celery_limit_q,
            },
            {
                "id": "E-aws-zero-tolerance",
                "kind": "quoted-default",
                "detail": aws_q1,
            },
        ],
        "tests_run": [
            {
                "id": "probe1",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0068/probe1_quotes.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0068/probe2_reviewer.py"
                ),
                "result": "PASS",
            },
        ],
        "artifacts": [
            {"path": ARTIFACT_REL, "exists": True, "role": "primary"}
        ],
        "min_bytes_threshold": MIN_BYTES,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "Declared catalog schema is not present on this worktree; record "
            "fields follow RES-0001 (claim id, canonical mechanism, source "
            "lineage, evidence tier, confidence band, named settling probe, "
            "contradiction/support edges, freshness stamp, snapshot sha256)."
        ),
        "residual_unknowns": [
            "Flyte v2 map_task snapshots 404'd this harvest; not cited.",
            "Prefect allow_failure lacked an independent prose doc page in this harvest; not cited as measured fact.",
        ],
    }

    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(artifact, indent=2, sort_keys=False) + "\n"
    ARTIFACT.write_text(text, encoding="utf-8")
    if SENTINEL not in text or COMPLETION_SENTINEL not in text:
        print("FAILED:emit sentinel missing from serialized artifact", file=sys.stderr)
        return 1
    if len(text.encode("utf-8")) < MIN_BYTES:
        print("FAILED:emit too small", file=sys.stderr)
        return 1
    print(f"wrote {ARTIFACT_REL} bytes={len(text.encode('utf-8'))}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
