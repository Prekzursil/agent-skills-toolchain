"""Four-scheduler durability mechanisms → IR fields.

Source reading only: no Temporal / Airflow / Prefect / Dagster import or
process. Anchors are published GitHub paths at pinned tags. WFA-0027
teardown artifact is ABSENT; transferable-vs-second-control-plane calls
are therefore made from these source anchors plus the WFA-0027 catalog
question, not from a measured teardown file.
"""
from __future__ import annotations

from ir_vocab import ARCHITECTURE_LANE, REQUIRES_DURABLE_LOG

FRAMEWORKS = ("temporal", "airflow", "prefect", "dagster")
MECHANISMS = (
    "deterministic_replay",
    "idempotency_keys",
    "retry_backoff",
    "sensors",
    "backfill",
    "task_sla",
)

LICENSES = {
    "temporal": {"spdx": "MIT", "repo": "github.com/temporalio/sdk-go"},
    "airflow": {"spdx": "Apache-2.0", "repo": "github.com/apache/airflow"},
    "prefect": {"spdx": "Apache-2.0", "repo": "github.com/PrefectHQ/prefect"},
    "dagster": {"spdx": "Apache-2.0", "repo": "github.com/dagster-io/dagster"},
}


def _row(
    framework: str,
    mechanism: str,
    native_construct: str,
    ir_field: str | None,
    disposition: str,
    requires_durable_log: bool,
    source_anchor: str,
    note: str,
    history_file: str | None = None,
) -> dict:
    routed = ARCHITECTURE_LANE if requires_durable_log else None
    if requires_durable_log and not routed:
        raise AssertionError("durable-log mechanism missing architecture route")
    if history_file:
        raise AssertionError("file-backed history is forbidden")
    ticket = None
    if requires_durable_log:
        ticket = f"ARCH-LANE:WFA-0051:{framework}:{mechanism}"
    return {
        "architecture_ticket": ticket,
        "disposition": disposition,
        "framework": framework,
        "history_file": None,
        "ir_field": ir_field,
        "license": LICENSES[framework]["spdx"],
        "mechanism": mechanism,
        "native_construct": native_construct,
        "note": note,
        "requires_durable_log": requires_durable_log,
        "routed_to": routed,
        "source_anchor": source_anchor,
    }


def mechanism_rows() -> list[dict]:
    rows = [
        _row(
            "temporal",
            "deterministic_replay",
            "workflow history event replay (SDK re-executes workflow code; activities are not re-run)",
            "replay_cursor",
            REQUIRES_DURABLE_LOG,
            True,
            "github.com/temporalio/sdk-go@v1.35.0 workflow/doc.go:76-77,374-375",
            "Command-event replay needs the workflow event history. This estate has no Temporal history store. Routed to architecture-lane; not faked with a JSONL file.",
        ),
        _row(
            "temporal",
            "idempotency_keys",
            "WorkflowID + WorkflowIDReusePolicy on StartWorkflow",
            "idempotency_key",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/temporalio/sdk-go@v1.35.0 internal/internal_workflow.go:190-198 WorkflowOptions.WorkflowID / WorkflowIDReusePolicy",
            "The key maps to IR. Uniqueness/reuse enforcement needs the service's durable ID index.",
        ),
        _row(
            "temporal",
            "retry_backoff",
            "common.v1.RetryPolicy on activities/workflows (InitialInterval, BackoffCoefficient, MaximumAttempts)",
            "retries",
            "MAPPED",
            False,
            "github.com/temporalio/sdk-go@v1.35.0 internal/internal_workflow.go:198 RetryPolicy *commonpb.RetryPolicy",
            "Declarative policy is an IR field. Crash-resume of attempt counters still needs a log (see deterministic_replay).",
        ),
        _row(
            "temporal",
            "sensors",
            "no BaseSensorOperator; wait is workflow.Await / signals / activity polling",
            "gates",
            "LOSSY",
            True,
            "github.com/temporalio/sdk-go@v1.35.0 workflow/doc.go:86-90 workflow.Sleep / Channel / Selector (deterministic waits)",
            "LOSSY: Temporal has no poke-sensor. Signal inbox is durable state → architecture-lane.",
        ),
        _row(
            "temporal",
            "backfill",
            "ScheduleSpec + ScheduleBackfill on Temporal Schedules",
            "backfill_window",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/temporalio/sdk-go@v1.35.0 (client.ScheduleBackfill); workflow/doc.go CronSchedule on WorkflowOptions:200",
            "The window maps. Completing a historical schedule range needs schedule+history durability.",
        ),
        _row(
            "temporal",
            "task_sla",
            "ScheduleToCloseTimeout / StartToCloseTimeout / ScheduleToStartTimeout (timeouts, not SLA-miss callbacks)",
            "sla_deadline",
            "LOSSY",
            False,
            "github.com/temporalio/sdk-go@v1.35.0 internal/internal_workflow.go:186-188 WorkflowExecutionTimeout / WorkflowRunTimeout / WorkflowTaskTimeout",
            "Timeouts map to sla_deadline with loss: no Airflow-style SLA miss email bundled by deadline.",
        ),
        _row(
            "airflow",
            "deterministic_replay",
            "DAG re-parse + TaskInstance state in metadata DB; not event-sourced workflow replay",
            "stages",
            REQUIRES_DURABLE_LOG,
            True,
            "github.com/apache/airflow@2.10.4 airflow/models/baseoperator.py:606-614 retries (state lives on TaskInstance, not in the operator class)",
            "Airflow does not replay operator Python from an event log. Resume is metadata-DB state. Routed to architecture-lane. Topology still maps to IR stages (see replay experiment for the transferable subset).",
        ),
        _row(
            "airflow",
            "idempotency_keys",
            "identity = dag_id + task_id + run_id; no caller-supplied idempotency_key",
            "idempotency_key",
            "LOSSY",
            False,
            "github.com/apache/airflow@2.10.4 airflow/models/baseoperator.py (task_id / dag_id identity; no idempotency_key parameter on BaseOperator.__init__)",
            "Derived identity maps LOSSY onto idempotency_key. Operators are documented as should-be-idempotent by convention, not by a key API.",
        ),
        _row(
            "airflow",
            "retry_backoff",
            "retries, retry_delay, retry_exponential_backoff, max_retry_delay",
            "retries",
            "MAPPED",
            False,
            "github.com/apache/airflow@2.10.4 airflow/models/baseoperator.py:606-616,210-216 DEFAULT_RETRIES / retry_exponential_backoff",
            "Policy maps onto IR retries. Attempt persistence is the metadata DB (architecture-lane via deterministic_replay row).",
        ),
        _row(
            "airflow",
            "sensors",
            "BaseSensorOperator poke/reschedule, poke_interval, timeout, exponential_backoff",
            "gates",
            "MAPPED",
            False,
            "github.com/apache/airflow@2.10.4 airflow/sensors/base.py BaseSensorOperator (mode in {poke, reschedule}, poke())",
            "Sensor wait-until is an IR gate. poke mode holding a worker slot is a runtime, not an IR field.",
        ),
        _row(
            "airflow",
            "backfill",
            "airflow dags backfill over logical dates / data intervals",
            "backfill_window",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/apache/airflow@2.10.4 airflow/cli/commands/dag_command.py backfill; logical_date range on DagRun",
            "The window maps. Which intervals already succeeded is metadata-DB state.",
        ),
        _row(
            "airflow",
            "task_sla",
            "sla timedelta on BaseOperator; SLA miss email + DB record",
            "sla_deadline",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/apache/airflow@2.10.4 airflow/models/baseoperator.py:691-701 :param sla",
            "Deadline maps. Miss recording/email is scheduler+DB — architecture-lane, not a side file.",
        ),
        _row(
            "prefect",
            "deterministic_replay",
            "flow-run / task-run state in the Prefect API DB; result cache is not Temporal replay",
            "replay_cursor",
            REQUIRES_DURABLE_LOG,
            True,
            "github.com/PrefectHQ/prefect@3.1.11 src/prefect/tasks.py (task run state + cache_key_fn; no event-history replay API)",
            "Prefect retries a task; it does not re-execute a deterministic workflow function against recorded commands. Routed to architecture-lane.",
        ),
        _row(
            "prefect",
            "idempotency_keys",
            "idempotency_key on run_deployment / arun_deployment / create_flow_run",
            "idempotency_key",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/PrefectHQ/prefect@3.1.11 src/prefect/deployments/flow_runs.py arun_deployment(idempotency_key=...)",
            "The parameter maps. Collapsing duplicate starts needs the API's durable run index.",
        ),
        _row(
            "prefect",
            "retry_backoff",
            "retries, retry_delay_seconds (number, list, or callable exponential helper)",
            "retries",
            "MAPPED",
            False,
            "github.com/PrefectHQ/prefect@3.1.11 src/prefect/tasks.py:267-272,117-132 retry_backoff_callable / retries",
            "Policy maps onto IR retries. Worked replay on this estate exercises this mapping.",
        ),
        _row(
            "prefect",
            "sensors",
            "Prefect 3 automations/triggers; no Airflow BaseSensorOperator in core 3.1.11",
            "gates",
            "LOSSY",
            False,
            "github.com/PrefectHQ/prefect@3.1.11 (no src/prefect/sensors.py equivalent to Airflow BaseSensorOperator)",
            "LOSSY: wait-until can be an IR gate; Prefect's automation engine is not that class.",
        ),
        _row(
            "prefect",
            "backfill",
            "no Airflow-style DAG logical_date backfill in core 3.1.11",
            "backfill_window",
            "LOSSY",
            False,
            "github.com/PrefectHQ/prefect@3.1.11 src/prefect/tasks.py (no backfill= on Task.__init__)",
            "LOSSY: a date window can be stored on IR; Prefect 3.1.11 core does not ship Airflow backfill.",
        ),
        _row(
            "prefect",
            "task_sla",
            "timeout_seconds on Task (hard timeout, not SLA-miss callback)",
            "sla_deadline",
            "LOSSY",
            False,
            "github.com/PrefectHQ/prefect@3.1.11 src/prefect/tasks.py:289,338 timeout_seconds",
            "LOSSY: timeout ≠ SLA miss. Prefect Cloud SLA APIs are out of this pinned core tag.",
        ),
        _row(
            "dagster",
            "deterministic_replay",
            "run event log / instance run storage; ops are not Temporal-style history-replayed functions",
            "replay_cursor",
            REQUIRES_DURABLE_LOG,
            True,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/policy.py RetryPolicy (retry is in-run; history is instance storage)",
            "Re-execution from failure uses instance storage. Routed to architecture-lane.",
        ),
        _row(
            "dagster",
            "idempotency_keys",
            "run_key on RunRequest / sensor RunRequest",
            "idempotency_key",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/sensor_definition.py RunRequest.run_key",
            "run_key maps. Dedup of runs needs instance run storage.",
        ),
        _row(
            "dagster",
            "retry_backoff",
            "RetryPolicy(max_retries, delay, backoff=LINEAR|EXPONENTIAL, jitter)",
            "retries",
            "MAPPED",
            False,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/policy.py RetryPolicy / calculate_delay",
            "Policy maps. Jitter is NON-DETERMINISTIC if used; the worked replay uses delay without jitter.",
        ),
        _row(
            "dagster",
            "sensors",
            "@sensor / SensorDefinition yielding RunRequest | SkipReason",
            "gates",
            "MAPPED",
            False,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/sensor_definition.py SensorDefinition",
            "Evaluation cursor is instance state; the wait-until shape is an IR gate.",
        ),
        _row(
            "dagster",
            "backfill",
            "partition backfills / BackfillPolicy on assets",
            "backfill_window",
            "MAPPED-POLICY-ONLY",
            True,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/backfill_policy.py BackfillPolicy",
            "The window/policy maps. Completed partition materialisations are instance storage.",
        ),
        _row(
            "dagster",
            "task_sla",
            "FreshnessPolicy / freshness checks (asset freshness, not Airflow task SLA)",
            "sla_deadline",
            "LOSSY",
            False,
            "github.com/dagster-io/dagster@1.9.6 python_modules/dagster/dagster/_core/definitions/freshness_policy.py FreshnessPolicy",
            "LOSSY: freshness is not a per-op SLA miss. Closest IR field is sla_deadline with that caveat.",
        ),
    ]
    if len(rows) != 24:
        raise AssertionError(f"expected 24 mappings, got {len(rows)}")
    seen = {(r["framework"], r["mechanism"]) for r in rows}
    if len(seen) != 24:
        raise AssertionError("duplicate mapping rows")
    return rows


def architecture_tickets(rows: list[dict] | None = None) -> list[dict]:
    out = []
    for r in rows or mechanism_rows():
        if r["requires_durable_log"]:
            out.append(
                {
                    "id": r["architecture_ticket"],
                    "framework": r["framework"],
                    "mechanism": r["mechanism"],
                    "reason": REQUIRES_DURABLE_LOG,
                    "routed_to": ARCHITECTURE_LANE,
                    "forbidden_substitute": "file-backed event log / JSONL history / sqlite sidecar pretending to be Temporal history",
                }
            )
    return out


def assert_no_file_fake(rows: list[dict] | None = None) -> None:
    for r in rows or mechanism_rows():
        if r.get("history_file"):
            raise AssertionError(
                f"file-fake history on {r['framework']}:{r['mechanism']}"
            )
        if r["requires_durable_log"] and r["routed_to"] != ARCHITECTURE_LANE:
            raise AssertionError(
                f"durable mechanism not routed {r['framework']}:{r['mechanism']}"
            )
        if r["requires_durable_log"] and not r.get("architecture_ticket"):
            raise AssertionError("missing architecture ticket")
