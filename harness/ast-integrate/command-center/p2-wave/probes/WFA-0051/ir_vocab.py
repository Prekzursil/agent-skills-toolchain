"""IR field vocabulary for WFA-0051.

WFA-0044 (workflow IR spec) is a declared dependency and is ABSENT on this
tree. Field names below are taken from the WFA-0044 catalog row
(question_or_target: stages, roles, gates, tool policy, fan-out, barriers,
loops with convergence, human checkpoints, retries, resume, stopping
expressions, lineage) plus the six durability extensions this unit must
place. This module has no runtime entrypoint.
"""
from __future__ import annotations

CATALOG_IR_FIELDS = (
    "stages",
    "roles",
    "gates",
    "tool_policy",
    "fan_out",
    "barriers",
    "loop_convergence",
    "human_checkpoints",
    "retries",
    "resume",
    "stop_expressions",
    "lineage",
)

DURABILITY_IR_FIELDS = (
    "idempotency_key",
    "replay_cursor",
    "backfill_window",
    "sla_deadline",
)

IR_FIELD_NOTES = {
    "stages": "Ordered work nodes; DAG topology lands here.",
    "roles": "Who may run a stage (catalog IR).",
    "gates": "Wait-until predicates; sensors/signals land here.",
    "tool_policy": "Allowed tools; operator/activity bodies do not map.",
    "fan_out": "Dynamic fan-out; out of this unit's six mechanisms.",
    "barriers": "Join points after fan-out.",
    "loop_convergence": "Loop-until; not a first-class durability mechanism here.",
    "human_checkpoints": "Human-in-the-loop; Temporal signals can LOSSY-map here.",
    "retries": "Declarative retry/backoff policy (attempts, delay, exponential).",
    "resume": "Continue a partially completed run; requires durable run state.",
    "stop_expressions": "Stopping conditions.",
    "lineage": "Provenance of a stage result; not a substitute for event history.",
    "idempotency_key": "Caller-supplied or derived key that must collapse duplicate starts.",
    "replay_cursor": "Position in an event history. Empty unless a durable log exists.",
    "backfill_window": "Historical partition/date range to materialise.",
    "sla_deadline": "Task-level deadline / miss condition.",
}

ARCHITECTURE_LANE = "architecture-lane"
REQUIRES_DURABLE_LOG = "REQUIRES-DURABLE-LOG"
UNACHIEVED = "UNACHIEVED"
