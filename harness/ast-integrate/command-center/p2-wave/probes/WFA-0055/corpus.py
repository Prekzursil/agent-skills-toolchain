#!/usr/bin/env python3
"""Nine-adapter native corpora and the closed IR field set (WFA-0044).

The IR is a typed document, not a second execution runtime. Native fields that
map onto IR_FIELDS round-trip. Everything else is a measured drop.
"""
from __future__ import annotations

IR_FIELDS = frozenset(
    {
        "stages",
        "roles",
        "gates",
        "tool_policy",
        "fan_out",
        "barriers",
        "loops",
        "convergence_rules",
        "human_checkpoints",
        "retries",
        "resume",
        "stopping_expressions",
        "lineage",
        "source_anchor",
    }
)

ADAPTERS: list[dict] = [
    {
        "id": "WFA-0045",
        "slug": "saved-workflow",
        "title": "Claude Code saved Workflow (.js/.mjs, agent/parallel/phase)",
    },
    {
        "id": "WFA-0046",
        "slug": "metaswarm-pipeline",
        "title": "metaswarm 9-phase pipeline and gates",
    },
    {
        "id": "WFA-0047",
        "slug": "skill-markdown",
        "title": "SKILL.md procedural prose",
    },
    {
        "id": "WFA-0048",
        "slug": "slash-command",
        "title": "slash-command markdown",
    },
    {
        "id": "WFA-0049",
        "slug": "langgraph",
        "title": "LangGraph state-graph (mechanism only)",
    },
    {
        "id": "WFA-0050",
        "slug": "crew-autogen",
        "title": "CrewAI / AutoGen role-crew frameworks",
    },
    {
        "id": "WFA-0051",
        "slug": "dag-schedulers",
        "title": "Temporal / Airflow / Prefect / Dagster durability",
    },
    {
        "id": "WFA-0052",
        "slug": "github-actions",
        "title": "GitHub Actions workflow YAML",
    },
    {
        "id": "WFA-0053",
        "slug": "paper-protocol",
        "title": "paper-described protocol prose",
    },
]

ADAPTER_IDS = tuple(a["id"] for a in ADAPTERS)

# Native field -> IR field. Only lossless mappings. Absent keys are drops.
CARRY: dict[str, dict[str, str]] = {
    "WFA-0045": {
        "stages": "stages",
        "gates": "gates",
        "barriers": "barriers",
        "fan_out": "fan_out",
        "tool_policy": "tool_policy",
        "retries": "retries",
        "source_anchor": "source_anchor",
    },
    "WFA-0046": {
        "stages": "stages",
        "gates": "gates",
        "roles": "roles",
        "human_checkpoints": "human_checkpoints",
        "stopping_expressions": "stopping_expressions",
        "source_anchor": "source_anchor",
    },
    "WFA-0047": {
        "stages": "stages",
        "tool_policy": "tool_policy",
        "human_checkpoints": "human_checkpoints",
        "source_anchor": "source_anchor",
        "lineage": "lineage",
    },
    "WFA-0048": {
        "stages": "stages",
        "lineage": "lineage",
        "source_anchor": "source_anchor",
        "tool_policy": "tool_policy",
    },
    "WFA-0049": {
        "stages": "stages",
        "gates": "gates",
        "human_checkpoints": "human_checkpoints",
        "resume": "resume",
        "source_anchor": "source_anchor",
        "loops": "loops",
    },
    "WFA-0050": {
        "roles": "roles",
        "stages": "stages",
        "stopping_expressions": "stopping_expressions",
        "source_anchor": "source_anchor",
        "barriers": "barriers",
    },
    "WFA-0051": {
        "stages": "stages",
        "retries": "retries",
        "resume": "resume",
        "source_anchor": "source_anchor",
        "gates": "gates",
    },
    "WFA-0052": {
        "stages": "stages",
        "gates": "gates",
        "fan_out": "fan_out",
        "source_anchor": "source_anchor",
        "retries": "retries",
    },
    "WFA-0053": {
        "stages": "stages",
        "roles": "roles",
        "source_anchor": "source_anchor",
        "stopping_expressions": "stopping_expressions",
        "human_checkpoints": "human_checkpoints",
    },
}

# Native field values used by the round-trip projector. Loss fields are present
# in the native document and absent from CARRY so the projector drops them.
NATIVE: dict[str, dict] = {
    "WFA-0045": {
        "stages": [{"id": "plan"}, {"id": "gate"}, {"id": "execute"}],
        "gates": [{"id": "plan-gate", "blocking": True}],
        "barriers": [{"id": "fan-in", "kind": "filter-boolean"}],
        "fan_out": {"parallel": ["research", "draft"]},
        "tool_policy": {"allow": ["Read", "Grep"]},
        "retries": {"max": 2, "backoff": "linear"},
        "source_anchor": "saved-workflows/plan-gate.mjs:1",
        "background_dispatch": {
            "call": "agent({ prompt, background: true })",
            "join": None,
        },
        "date_now": "Date.now()",
        "args_as_string": {"args": "owner=alice env=prod"},
        "injected_runtime_entrypoint": {
            "globals": ["agent", "parallel", "phase"],
            "runtime": "claude-code-workflow",
        },
    },
    "WFA-0046": {
        "stages": [
            {"id": "design-review"},
            {"id": "plan-review"},
            {"id": "implement"},
            {"id": "coverage"},
        ],
        "gates": [
            {"id": "design-review-gate", "blocking": True},
            {"id": "plan-review-gate", "blocking": True},
        ],
        "roles": ["implementer", "reviewer"],
        "human_checkpoints": [{"id": "owner-ack"}],
        "stopping_expressions": "coverage_gate == PASS",
        "source_anchor": "metaswarm/skills/pipeline.md:1",
        "metaswarm_runtime_import": {
            "would_import": "metaswarm",
            "control_plane": True,
        },
        "coverage_engine_implementation": {
            "engine": "metaswarm-coverage-enforcer",
            "not_just_a_gate_predicate": True,
        },
    },
    "WFA-0047": {
        "stages": [{"id": "read-skill"}, {"id": "apply-steps"}],
        "tool_policy": {"allow": ["Read"]},
        "human_checkpoints": [{"id": "ask-user"}],
        "source_anchor": "skills/example/SKILL.md:12",
        "lineage": {"from": "SKILL.md"},
        "unstructured_procedure_invention": {
            "skill": "skills/notes/SKILL.md",
            "ordered_procedure": False,
        },
        "skill_context_fork": {"frontmatter": {"context": "fork"}},
    },
    "WFA-0048": {
        "stages": [{"id": "invoke-skill"}],
        "lineage": {"alias_of": "skill.plan"},
        "source_anchor": ".claude/commands/plan.md:1",
        "tool_policy": {"allow": ["Read"]},
        "slash_arguments_interpolation": {"template": "/plan $ARGUMENTS"},
        "alias_counted_as_distinct": {
            "command": "/plan",
            "body": "invoke skill.plan",
            "own_procedure": False,
        },
    },
    "WFA-0049": {
        "stages": [{"id": "retrieve"}, {"id": "generate"}],
        "gates": [{"id": "cond-edge", "blocking": True}],
        "human_checkpoints": [{"id": "interrupt-before-generate"}],
        "resume": {"supported": True, "kind": "ir-resume-flag"},
        "source_anchor": "langgraph/graph.py:StateGraph",
        "loops": {"cycle": ["retrieve", "generate"], "convergence": "halt-on-gate"},
        "permission_merging_reducer": {
            "annotation": "Annotated[list, operator.or_]",
            "channel": "allowed_principals",
            "merges_permission_sets": True,
        },
        "checkpointer_backend": {
            "class": "SqliteSaver",
            "durable_log": True,
        },
        "pregel_runtime_loop": {
            "runtime": "langgraph.pregel",
            "execution_semantics": True,
        },
    },
    "WFA-0050": {
        "roles": ["researcher", "writer", "critic"],
        "stages": [{"id": "task-research"}, {"id": "task-write"}],
        "stopping_expressions": "unanimity == true OR max_rounds == 12",
        "source_anchor": "autogen/agentchat/groupchat.py:1",
        "barriers": [{"id": "all-tasks-done"}],
        "live_conversational_turn_loop": {
            "selector": "GroupChatManager.select_speaker",
            "requires_live_loop": True,
        },
        "llm_judge_termination": {
            "text": "stop when the conversation feels done",
            "boolean_expression": None,
        },
    },
    "WFA-0051": {
        "stages": [{"id": "extract"}, {"id": "load"}],
        "retries": {"max": 5, "backoff": "exponential"},
        "resume": {"supported": True, "kind": "ir-resume-flag"},
        "source_anchor": "temporalio/workflow.py:1",
        "gates": [{"id": "quality-gate", "blocking": True}],
        "durable_execution_log": {
            "framework": "Temporal",
            "history_events": True,
            "estate_has_log": False,
        },
        "airflow_sensor_poke": {
            "sensor": "ExternalTaskSensor",
            "poke_interval": 60,
        },
        "task_sla_kill": {
            "sla": "5m",
            "on_breach": "kill-task",
        },
    },
    "WFA-0052": {
        "stages": [
            {"id": "job.unit"},
            {"id": "job.lint"},
            {"id": "job.deploy"},
        ],
        "gates": [{"id": "needs-unit", "blocking": True}],
        "fan_out": {"matrix": {"python": ["3.11", "3.12"]}},
        "source_anchor": ".github/workflows/quality.yml:1",
        "retries": {"max": 0},
        "environment_protection_reviewers": {
            "environment": "production",
            "required_reviewers": ["release-owners"],
        },
        "matrix_fail_fast": {"strategy": {"fail-fast": True}},
        "required_vs_optional_check": {
            "unit": "required",
            "lint": "optional",
        },
        "runtime_dynamic_matrix": {
            "matrix": "${{ fromJson(needs.setup.outputs.matrix) }}",
        },
    },
    "WFA-0053": {
        "stages": [{"id": "round"}, {"id": "score"}],
        "roles": ["proposer", "critic"],
        "source_anchor": "papers/deliberation-protocol.md:14",
        "stopping_expressions": "proof_of_impossibility == true",
        "human_checkpoints": [{"id": "author-supply-parameters"}],
        "underspecified_stop": {
            "paper": "underspecified-protocol.pdf",
            "stop_rule_quoted": None,
        },
        "statistical_scoring_function": {
            "metric": "Elo",
            "boolean_stopping": False,
        },
        "implied_participant_count": {
            "prose": "a small panel of experts",
            "pinned_n": None,
        },
    },
}


def adapter_by_id(uid: str) -> dict:
    for row in ADAPTERS:
        if row["id"] == uid:
            return row
    raise KeyError(uid)


def native_doc(uid: str) -> dict:
    if uid not in NATIVE:
        raise KeyError(uid)
    return {"adapter_id": uid, "fields": dict(NATIVE[uid])}
