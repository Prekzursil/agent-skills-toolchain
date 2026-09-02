"""Adapters that fold today's ad-hoc rails into ONE work-unit contract.

Each adapter names the existing rail, the claim/complete records it must
write, and how in-flight work is drained rather than abandoned. These are
the three rails named by ARC-0035.
"""
from __future__ import annotations

RAILS: list[dict[str, str]] = [
    {
        "id": "task_subagent",
        "existing_rail": (
            "Task-tool / nested-agent dispatches that today carry no catalog "
            "unit_id and no ledger claim"
        ),
        "adapter": (
            "Wrap every Task spawn: before the host starts the child, write a "
            "ledger claim {unit_id, substrate, rail=task_subagent, "
            "external_ref=task_id, lease_owner}. The child argv/prompt is "
            "required to echo that unit_id; a spawn without a prior claim is "
            "refused by the adapter, not launched."
        ),
        "claim": (
            "kind=claim, unit_id from WORK-UNIT-CATALOG, external_ref=task_id, "
            "dedupe_key=(unit_id, attempt). Two dispatchers racing the same "
            "unit_id: exactly one claim row wins (first append with that "
            "dedupe_key); the loser records kind=claim_rejected."
        ),
        "complete": (
            "On Task return, append kind=complete|fail with the same unit_id "
            "and the child's exit/sentinel. Missing sentinel is fail, not "
            "success. Re-running an idempotent unit appends another complete "
            "row; it must not rewrite the first."
        ),
        "drain": (
            "Census running Task ids from the host. Each id with no terminal "
            "ledger row is leased (kind=drain, outcome=IN_FLIGHT_LEASED) or, "
            "if the process is gone with no artifact, kind=drain "
            "outcome=ABANDONED. Killing a Task without one of those two rows "
            "is forbidden."
        ),
        "external_ref": "task_id",
    },
    {
        "id": "codex_mcp",
        "existing_rail": (
            "Codex MCP threads (thread_id) that today can die mid-request and "
            "leave a running thread with no owner"
        ),
        "adapter": (
            "Map thread_id -> unit_id at open: ledger claim with "
            "rail=codex_mcp, external_ref=thread_id, substrate=cloud-batch or "
            "local-serialized as the MCP session dictates. Cancellation or "
            "network fault must either reclaim the thread by id or append "
            "ABANDONED; a running thread with no owner is a drain miss."
        ),
        "claim": (
            "kind=claim with external_ref=thread_id and unit_id. Re-open of "
            "the same thread_id after a crash is resume (kind=resume), not a "
            "second unit."
        ),
        "complete": (
            "MCP terminal payload folds to kind=complete|fail. A cancelled "
            "stream without reclaim or ABANDONED is incomplete; the shared "
            "completion reducer returns FALSE."
        ),
        "drain": (
            "List live MCP thread ids. For each: if ledger already terminal, "
            "skip; if thread still running, lease; if thread missing, "
            "ABANDONED. Never drop a thread_id from the census without a "
            "drain row."
        ),
        "external_ref": "thread_id",
    },
    {
        "id": "databricks_job",
        "existing_rail": (
            "Databricks Jobs (job_id + run_id) used as a portable batch rail "
            "without a work-unit claim or timeout readback"
        ),
        "adapter": (
            "jobs.submit is preceded by a ledger claim {unit_id, "
            "rail=databricks_job, external_ref=run_id, idempotency_key}. The "
            "Databricks idempotency key IS the unit_id+attempt, so a retry "
            "cannot mint a second run for the same claim. Timeout is read "
            "back from the run, never assumed."
        ),
        "claim": (
            "kind=claim with external_ref=run_id (filled in after submit "
            "returns) and job_id. A submit that fails before run_id exists "
            "still appends kind=claim_rejected so the queue is not silent."
        ),
        "complete": (
            "Terminal Databricks life-cycle (SUCCESS/FAILED/TIMEDOUT/"
            "CANCELLED) maps 1:1 onto kind=complete|fail. Polling is the "
            "adapter's job; the ledger does not infer completion from wall "
            "clock."
        ),
        "drain": (
            "jobs.list-runs --active-only is the census. Each active run_id "
            "without a terminal ledger row is leased; a run that vanished "
            "without terminal state is ABANDONED with the last known "
            "life_cycle_state. Runs are not cancelled as a drain shortcut."
        ),
        "external_ref": "run_id",
    },
]


WORK_UNIT_FIELDS: tuple[str, ...] = (
    "id",
    "title",
    "phase",
    "target",
    "inputs",
    "dependencies",
    "assignment",
    "tool_permissions",
    "execution_substrate",
    "timeout_seconds",
    "output_path",
    "output_schema",
    "evidence_requirement",
    "tests_required",
    "reviewer_requirement",
    "completion_sentinel",
    "retry_policy",
    "failure_classification",
    "owner_approval_required",
)


CONTRACT = {
    "id": "a5-work-unit-v1",
    "fields": list(WORK_UNIT_FIELDS),
    "delivery_guarantee": (
        "at-least-once plus idempotent units: a duplicate dispatch may "
        "append a second claim_rejected or a second complete row, but must "
        "not rewrite a prior ledger line or a prior artifact. Exactly-once "
        "is NOT claimed; the claim record + dedupe_key is the mechanism "
        "that makes a second dispatcher lose."
    ),
    "idempotence": (
        "A unit is idempotent when re-running it with the same unit_id "
        "leaves the artifact byte-identical (or appends an explicitly "
        "versioned successor path). Units that cannot meet that bar are "
        "classified non-idempotent and MUST be claimed with a unique "
        "attempt suffix so a retry cannot clobber the first artifact."
    ),
    "claim_record": (
        "ledger kind=claim with fields unit_id, rail, external_ref, "
        "dedupe_key, lease_owner, prev_hash, event_hash"
    ),
}
