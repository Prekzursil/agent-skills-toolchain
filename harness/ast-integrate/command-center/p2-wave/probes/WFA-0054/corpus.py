#!/usr/bin/env python3
"""Full claimed corpora for the nine WFA dialect adapters.

Live host trees (~/.claude/workflows, the 96-skill family, this estate's
.github/workflows) are absent on this Linux worktree. Each adapter therefore
claims the fixture set registered here — and the harness runs every item, not
a sample of it.
"""
from __future__ import annotations

from typing import Any

AdapterId = str


def _saved_workflow(i: int, **extra: Any) -> dict[str, Any]:
    phases = [
        {
            "name": f"phase-{i}-design",
            "agents": [f"architect-{i}", "skeptic"],
            "parallel": False,
            "schema": f"Design{i}",
            "barrier": "filterBoolean",
            "worktree": True,
        },
        {
            "name": f"phase-{i}-build",
            "agents": [f"builder-{i}"],
            "parallel": i % 2 == 0,
            "schema": f"Build{i}",
            "barrier": "join",
            "worktree": i % 3 != 0,
        },
    ]
    doc: dict[str, Any] = {
        "id": f"saved-wf-{i:02d}",
        "filename": f"saved-wf-{i:02d}.mjs",
        "phases": phases,
        "tool_policy": {"allow": ["Read", "Grep"], "deny": ["Bash(curl)"]},
        "stopping": "all_gates_pass",
        "comments": f"// injected globals workflow {i}",
        "date_now_construct": i % 3 == 0,
        "args_as_string": i % 4 == 0,
        "background": i == 10,
    }
    doc.update(extra)
    return doc


SAVED_WORKFLOWS = [_saved_workflow(i) for i in range(1, 11)]

METASWARM_PIPELINE = {
    "id": "metaswarm-nine-phase",
    "coverage_enforcement": True,
    "knowledge_capture_before_pr": True,
    "phases": [
        {"name": "design-review", "gate": "design-approved", "blocking": True},
        {"name": "plan-review", "gate": "plan-approved", "blocking": True},
        {"name": "implement", "gate": None, "blocking": False},
        {"name": "test", "gate": "tests-green", "blocking": True},
        {"name": "coverage-enforcement", "gate": "coverage-floor", "blocking": True},
        {"name": "review", "gate": "review-pass", "blocking": True},
        {"name": "pre-pr-knowledge-capture", "gate": "knowledge-written", "blocking": True},
        {"name": "open-pr", "gate": None, "blocking": False},
        {"name": "merge-gate", "gate": "merge-allowed", "blocking": True},
    ],
    "vendor_runtime_import": False,
    "prose_rationale": "operator notes not in IR",
}

SKILLS: list[dict[str, Any]] = []
for i in range(1, 11):
    SKILLS.append(
        {
            "id": f"skill.extractable-{i:02d}",
            "extractable": True,
            "frontmatter_description": f"Use this skill to do task {i}. Not a stage.",
            "stages": [
                {
                    "title": f"Step 1 of skill {i}",
                    "source_line": 12 + i,
                    "body": f"Do the first action of {i}.",
                },
                {
                    "title": f"Step 2 of skill {i}",
                    "source_line": 20 + i,
                    "body": f"Do the second action of {i}.",
                },
            ],
            "unstructured_aside": f"anecdote {i} is not a procedure",
        }
    )
SKILLS.append(
    {
        "id": "skill.unstructured-alpha",
        "extractable": False,
        "verdict": "NOT-EXTRACTABLE",
        "reason": "no ordered procedure; frontmatter description is use-not-mention",
        "frontmatter_description": "A reference card with no steps.",
        "stages": [],
        "unstructured_aside": "lorem",
    }
)
SKILLS.append(
    {
        "id": "skill.unstructured-beta",
        "extractable": False,
        "verdict": "NOT-EXTRACTABLE",
        "reason": "prose is a concept explainer, not a stage list",
        "frontmatter_description": "Explains what a latch is.",
        "stages": [],
        "unstructured_aside": "concept dump",
    }
)

SLASH_COMMANDS: list[dict[str, Any]] = []
for i in range(1, 5):
    SLASH_COMMANDS.append(
        {
            "id": f"cmd.alias-{i:02d}",
            "kind": "ALIAS",
            "target_skill": f"skill.extractable-{i:02d}",
            "stages": [],
            "help_blurb": f"thin wrapper {i}",
        }
    )
for i in range(1, 5):
    SLASH_COMMANDS.append(
        {
            "id": f"cmd.own-{i:02d}",
            "kind": "OWN-PROCEDURE",
            "target_skill": None,
            "stages": [
                {"title": f"own-step-a-{i}", "source_line": 4, "body": f"first own action {i}"},
                {"title": f"own-step-b-{i}", "source_line": 8, "body": f"second own action {i}"},
            ],
            "help_blurb": f"own procedure {i}",
        }
    )

LANGGRAPHS = [
    {
        "id": "lg-linear",
        "nodes": ["ingest", "write"],
        "edges": [["ingest", "write"]],
        "conditionals": [],
        "interrupt_before": [],
        "checkpointer": None,
        "reducer_names": {"msgs": "concat"},
        "reducer_callables": {"msgs": "<callable add_messages>"},
    },
    {
        "id": "lg-conditional",
        "nodes": ["research", "enough", "loop", "write"],
        "edges": [["enough", "write"]],
        "conditionals": [
            {
                "from": "research",
                "predicate": "enough_info",
                "true": "write",
                "false": "loop",
            }
        ],
        "interrupt_before": [],
        "checkpointer": "memory",
        "reducer_names": {"msgs": "add_messages"},
        "reducer_callables": {"msgs": "<callable>"},
    },
    {
        "id": "lg-interrupt",
        "nodes": ["research", "human", "write"],
        "edges": [["research", "human"], ["human", "write"]],
        "conditionals": [],
        "interrupt_before": ["human"],
        "checkpointer": "sqlite",
        "reducer_names": {"state": "merge"},
        "reducer_callables": {"state": "<callable merge_state>"},
    },
]

CREW_AUTOGEN = [
    {
        "id": "crew-sequential",
        "kind": "crew",
        "roles": [
            {"id": "researcher", "name": "Researcher", "council_role": "Skeptic"},
            {"id": "writer", "name": "Writer", "council_role": "Pragmatist"},
        ],
        "tasks": [
            {"id": "gather", "role": "researcher", "goal": "collect sources"},
            {"id": "draft", "role": "writer", "goal": "write note", "after": ["gather"]},
        ],
        "process": "sequential",
        "termination": "all_tasks_done",
        "live_turn_loop": "conversational-loop-NOT-TRANSFERABLE",
    },
    {
        "id": "autogen-groupchat",
        "kind": "autogen-groupchat",
        "roles": [
            {"id": "user", "name": "UserProxy", "council_role": "Owner"},
            {"id": "coder", "name": "Coder", "council_role": "Pragmatist"},
            {"id": "reviewer", "name": "Reviewer", "council_role": "Critic"},
        ],
        "tasks": [
            {"id": "session", "role": "user", "goal": "answer the ticket"},
        ],
        "process": "group-chat",
        "termination": "TERMINATE in last message OR max_turns==12",
        "live_turn_loop": "group-chat-speaker-selection-NOT-TRANSFERABLE",
    },
]

DAG_SCHEDULERS = [
    {
        "id": "temporal-order-flow",
        "framework": "temporal",
        "tasks": [
            {"id": "reserve", "retries": 3, "backoff_s": 5, "sla_s": 60},
            {"id": "charge", "retries": 5, "backoff_s": 10, "sla_s": 120, "after": ["reserve"]},
        ],
        "sensors": [],
        "replay_deterministic": True,
        "durable_event_log": "temporal-event-history-NOT-ON-THIS-ESTATE",
    },
    {
        "id": "airflow-daily",
        "framework": "airflow",
        "tasks": [
            {"id": "extract", "retries": 2, "backoff_s": 30, "sla_s": 3600},
            {"id": "load", "retries": 1, "backoff_s": 60, "sla_s": 7200, "after": ["extract"]},
        ],
        "sensors": [{"id": "s3-poke", "kind": "sensor", "target": "s3://bucket/ok"}],
        "replay_deterministic": False,
        "durable_event_log": "airflow-metadata-db-NOT-ON-THIS-ESTATE",
    },
    {
        "id": "prefect-flow",
        "framework": "prefect",
        "tasks": [
            {"id": "cacheable", "retries": 2, "backoff_s": 15, "sla_s": 300},
        ],
        "sensors": [],
        "replay_deterministic": True,
        "durable_event_log": "prefect-api-NOT-ON-THIS-ESTATE",
    },
    {
        "id": "dagster-assets",
        "framework": "dagster",
        "tasks": [
            {"id": "asset-a", "retries": 0, "backoff_s": 0, "sla_s": None},
            {"id": "asset-b", "retries": 1, "backoff_s": 20, "sla_s": 600, "after": ["asset-a"]},
        ],
        "sensors": [{"id": "asset-sensor", "kind": "asset-sensor", "target": "asset-a"}],
        "replay_deterministic": True,
        "durable_event_log": "dagster-storage-NOT-ON-THIS-ESTATE",
    },
]

GITHUB_ACTIONS = [
    {
        "id": "gha-two-job",
        "name": "ci-two-job",
        "jobs": {
            "build": {
                "steps": [{"name": "compile", "run": "make"}, {"name": "unit", "run": "pytest"}],
                "needs": [],
                "if": None,
                "continue_on_error": False,
                "required": True,
                "fail_fast_job": True,
            },
            "pack": {
                "steps": [{"name": "tarball", "run": "tar czf out.tgz dist"}],
                "needs": ["build"],
                "if": None,
                "continue_on_error": False,
                "required": True,
                "fail_fast_job": True,
            },
        },
        "matrix": None,
        "required_contexts": ["ci-two-job"],
        "secret_values": {"NPM_TOKEN": "must-not-round-trip"},
    },
    {
        "id": "gha-matrix",
        "name": "ci-matrix",
        "jobs": {
            "test": {
                "steps": [{"name": "pytest", "run": "pytest -q"}],
                "needs": [],
                "if": None,
                "continue_on_error": False,
                "required": True,
                "fail_fast_job": True,
            }
        },
        "matrix": {"os": ["linux", "windows"], "py": ["3.11", "3.12"]},
        "required_contexts": ["ci-matrix"],
        "secret_values": {},
    },
    {
        "id": "gha-conditional",
        "name": "ci-conditional",
        "jobs": {
            "lint": {
                "steps": [{"name": "ruff", "run": "ruff check ."}],
                "needs": [],
                "if": None,
                "continue_on_error": True,
                "required": False,
                "fail_fast_job": False,
            },
            "gate": {
                "steps": [{"name": "gate", "run": "python tools/gate.py"}],
                "needs": ["lint"],
                "if": "always()",
                "continue_on_error": False,
                "required": True,
                "fail_fast_job": True,
            },
        },
        "matrix": None,
        "required_contexts": ["ci-conditional / gate"],
        "secret_values": {"GITHUB_TOKEN": "must-not-round-trip"},
    },
]

PAPERS = [
    {
        "id": "paper-council-specified",
        "title": "A four-voice design council",
        "extractable": True,
        "participants": 4,
        "turn_structure": "Architect then Skeptic then Pragmatist then Critic, one pass",
        "stopping": "Critic files a blocking issue OR all four sign PASS",
        "scoring": "PASS if no blocking issue remains",
        "quotes": {
            "participants": "The council has four voices.",
            "turn_structure": "Each voice speaks once, in the order Architect, Skeptic, Pragmatist, Critic.",
            "stopping": "Stop when the Critic files a blocking issue, or when all four sign PASS.",
            "scoring": "The session scores PASS only if no blocking issue remains.",
        },
        "inferred_defaults": {},
    },
    {
        "id": "paper-review-specified",
        "title": "Two-reviewer patch protocol",
        "extractable": True,
        "participants": 3,
        "turn_structure": "author submits; reviewer-A; reviewer-B; author revises at most twice",
        "stopping": "both reviewers APPROVE or two revision rounds exhausted",
        "scoring": "ACCEPT iff two APPROVE",
        "quotes": {
            "participants": "One author and two reviewers.",
            "turn_structure": "Author submits, then reviewer A, then reviewer B; the author may revise at most twice.",
            "stopping": "Stop when both reviewers APPROVE, or when two revision rounds are exhausted.",
            "scoring": "ACCEPT if and only if both reviewers APPROVE.",
        },
        "inferred_defaults": {},
    },
    {
        "id": "paper-underspecified",
        "title": "Some agents talk until done",
        "extractable": False,
        "verdict": "UNDERSPECIFIED",
        "missing_parameters": [
            "participants",
            "turn_structure",
            "stopping",
            "scoring",
        ],
        "quotes": {},
        "inferred_defaults": {"participants": "MUST-NOT-FILL"},
        "prose": "Agents discuss the problem until they are happy.",
    },
]


def corpora() -> dict[str, list[dict[str, Any]]]:
    return {
        "saved-workflow": SAVED_WORKFLOWS,
        "metaswarm": [METASWARM_PIPELINE],
        "skill-markdown": SKILLS,
        "slash-command": SLASH_COMMANDS,
        "langgraph": LANGGRAPHS,
        "crew-autogen": CREW_AUTOGEN,
        "dag-scheduler": DAG_SCHEDULERS,
        "github-actions": GITHUB_ACTIONS,
        "paper-protocol": PAPERS,
    }


UPSTREAM_ARTIFACTS = {
    "WFA-0044": "command-center/wfa/WFA-0044-workflow-ir-spec.json",
    "WFA-0045": "command-center/wfa/WFA-0045-adapter-saved-workflow.json",
    "WFA-0046": "command-center/wfa/WFA-0046-adapter-metaswarm-pipeline.json",
    "WFA-0047": "command-center/wfa/WFA-0047-adapter-skill-markdown.json",
    "WFA-0048": "command-center/wfa/WFA-0048-adapter-slash-command.json",
    "WFA-0049": "command-center/wfa/WFA-0049-adapter-langgraph.json",
    "WFA-0050": "command-center/wfa/WFA-0050-adapter-crew-autogen.json",
    "WFA-0051": "command-center/wfa/WFA-0051-adapter-dag-schedulers.json",
    "WFA-0052": "command-center/wfa/WFA-0052-adapter-github-actions.json",
    "WFA-0053": "command-center/wfa/WFA-0053-adapter-paper-protocol.json",
    "WFA-0055": "command-center/wfa/WFA-0055-adapter-lossy-field-ledger.json",
    "WFA-0001": "command-center/wfa/schema/wfa-schema-pack.json",
}
