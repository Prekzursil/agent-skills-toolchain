#!/usr/bin/env python3
"""Declared lossy-field ledger, declared-vs-measured compare, disposition gate.

A loss that removes a safety property (gate, permission bound, stop rule) is
P1 regardless of frequency and blocks ADOPT. The gate reads this ledger; it
does not re-derive severity from prose.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SAFETY = frozenset({"gate", "permission_bound", "stop_rule"})
TRANSFER_BLOCK = frozenset({"NON-TRANSFERABLE", "REQUIRES-DURABLE-LOG"})

# Hand-authored. Projector does not import this list.
DECLARED: list[dict] = [
    {
        "loss_id": "LOSS-0045-background-dispatch",
        "adapter_id": "WFA-0045",
        "native_field": "background_dispatch",
        "source_construct": "agent({ background: true }) fire-and-forget dispatch",
        "worked_example": {
            "source": "saved-workflows/plan-gate.mjs",
            "snippet": "await agent({ prompt: 'review', background: true })",
            "what_triggers": "background:true with no join barrier",
        },
        "ir_gap": "IR stages and barriers are blocking; there is no fire-and-forget node type",
        "downstream_consequence": (
            "Normalising into a blocking call changes error isolation; dropping "
            "the call deletes a stage. Must flag, never silently block-wait."
        ),
        "safety_class": None,
        "frequency": "common",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0045-date-now",
        "adapter_id": "WFA-0045",
        "native_field": "date_now",
        "source_construct": "Date.now() (non-deterministic clock) in workflow body",
        "worked_example": {
            "source": "saved-workflows/design-gate.mjs",
            "snippet": "const id = 'run-' + Date.now()",
            "what_triggers": "Date.now() used as identity or branch input",
        },
        "ir_gap": "IR has no clock primitive; replay cannot reproduce the native value",
        "downstream_consequence": "Round-trip identity and branches that key on wall time diverge",
        "safety_class": None,
        "frequency": "known-runtime-defect",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0045-args-as-string",
        "adapter_id": "WFA-0045",
        "native_field": "args_as_string",
        "source_construct": "stringly agent args instead of schema-typed fan-in",
        "worked_example": {
            "source": "saved-workflows/plan-gate.mjs",
            "snippet": "args: 'owner=alice env=prod'",
            "what_triggers": "args is a string, not an object matching a schema",
        },
        "ir_gap": "IR tool_policy and stage inputs are typed; a free string has no field map",
        "downstream_consequence": "Named bindings are not recovered; consumers see one opaque blob",
        "safety_class": None,
        "frequency": "known-runtime-defect",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0045-injected-runtime-entrypoint",
        "adapter_id": "WFA-0045",
        "native_field": "injected_runtime_entrypoint",
        "source_construct": "injected agent()/parallel()/phase() as a live runtime",
        "worked_example": {
            "source": "skill:workflow-authoring",
            "snippet": "export async function workflow({ agent, parallel, phase }) { ... }",
            "what_triggers": "file is an executable workflow module, not a document",
        },
        "ir_gap": "WFA-0044 IR has no execution semantics and no runtime entrypoint",
        "downstream_consequence": "Importing the module as a second control plane is forbidden; only the described graph carries",
        "safety_class": None,
        "frequency": "universal-for-saved-workflows",
        "transferability": "DECLARED-LOSS",
        "degrade": "describe-only",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0046-metaswarm-runtime-import",
        "adapter_id": "WFA-0046",
        "native_field": "metaswarm_runtime_import",
        "source_construct": "import or vendor of the metaswarm plugin as a runtime",
        "worked_example": {
            "source": "CLAUDE.md workflow-enforcement",
            "snippet": "require('metaswarm') as the phase runner",
            "what_triggers": "acquired pipeline tries to keep metaswarm as the scheduler",
        },
        "ir_gap": "IR is not a control plane; metaswarm process/state-store cannot be a node type",
        "downstream_consequence": "A second orchestration runtime would enter the estate",
        "safety_class": None,
        "frequency": "if-imported",
        "transferability": "DECLARED-LOSS",
        "degrade": "refuse-import",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0046-coverage-engine",
        "adapter_id": "WFA-0046",
        "native_field": "coverage_engine_implementation",
        "source_construct": "metaswarm coverage-enforcer engine (not the gate predicate)",
        "worked_example": {
            "source": "metaswarm/skills/coverage.md",
            "snippet": "run coverage engine; fail the phase if the engine is red",
            "what_triggers": "phase invokes a live coverage binary rather than a Boolean predicate",
        },
        "ir_gap": "IR can carry the blocking gate 'coverage_gate == PASS', not the engine",
        "downstream_consequence": "ADOPT of the pipeline without the engine leaves the gate unevaluable unless the estate supplies an equivalent",
        "safety_class": None,
        "frequency": "pipeline-core",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0047-unstructured-invention",
        "adapter_id": "WFA-0047",
        "native_field": "unstructured_procedure_invention",
        "source_construct": "SKILL.md with no ordered procedure (must NOT-EXTRACTABLE)",
        "worked_example": {
            "source": "skills/notes/SKILL.md",
            "snippet": "frontmatter description only; body is a concept list",
            "what_triggers": "no numbered/ordered procedure in the body",
        },
        "ir_gap": "IR stages cannot be invented from mention; absence is not a stage list",
        "downstream_consequence": "An adapter that never refuses manufactures structure and inflates the floor",
        "safety_class": None,
        "frequency": "large-G-skill-family",
        "transferability": "NOT-EXTRACTABLE",
        "degrade": "refuse",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0047-context-fork",
        "adapter_id": "WFA-0047",
        "native_field": "skill_context_fork",
        "source_construct": "SKILL.md frontmatter context: fork",
        "worked_example": {
            "source": "skills/isolated/SKILL.md",
            "snippet": "---\ncontext: fork\n---",
            "what_triggers": "frontmatter requests a forked context window",
        },
        "ir_gap": "IR has no context-window / fork primitive",
        "downstream_consequence": "Runtime isolation of the skill context is not carried; estate must not pretend it did",
        "safety_class": None,
        "frequency": "occasional",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0048-slash-arguments",
        "adapter_id": "WFA-0048",
        "native_field": "slash_arguments_interpolation",
        "source_construct": "slash-command $ARGUMENTS interpolation",
        "worked_example": {
            "source": ".claude/commands/plan.md",
            "snippet": "/plan $ARGUMENTS",
            "what_triggers": "command body contains $ARGUMENTS",
        },
        "ir_gap": "IR stage inputs are named fields, not shell-style template slots",
        "downstream_consequence": "User-supplied command tail is not a typed IR input unless re-specified",
        "safety_class": None,
        "frequency": "common-for-I-family",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0048-alias-identity",
        "adapter_id": "WFA-0048",
        "native_field": "alias_counted_as_distinct",
        "source_construct": "slash command that only invokes a skill (alias, not own procedure)",
        "worked_example": {
            "source": ".claude/commands/plan.md",
            "snippet": "Run the plan skill. No extra stages.",
            "what_triggers": "command adds no stages beyond the target skill id",
        },
        "ir_gap": "A distinct workflow identity is not representable for a pure alias; lineage.alias_of is the carry",
        "downstream_consequence": "Counting the alias as a workflow inflates the 160-candidate floor",
        "safety_class": None,
        "frequency": "I-family-aliases",
        "transferability": "DECLARED-LOSS",
        "degrade": "collapse-to-alias",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0049-permission-reducer",
        "adapter_id": "WFA-0049",
        "native_field": "permission_merging_reducer",
        "source_construct": "LangGraph state reducer that ORs permission sets",
        "worked_example": {
            "source": "langgraph state channel allowed_principals",
            "snippet": "allowed_principals: Annotated[list, operator.or_]",
            "what_triggers": "custom reducer merges authorization sets",
        },
        "ir_gap": "IR has no arbitrary reducer functions; permission bounds cannot be encoded as operator.or_",
        "downstream_consequence": "Dropping the reducer can drop or widen a permission bound on resume",
        "safety_class": "permission_bound",
        "frequency": "uncommon",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0049-checkpointer",
        "adapter_id": "WFA-0049",
        "native_field": "checkpointer_backend",
        "source_construct": "LangGraph SqliteSaver / Postgres checkpointer durable log",
        "worked_example": {
            "source": "langgraph.checkpoint.sqlite.SqliteSaver",
            "snippet": "graph.compile(checkpointer=SqliteSaver.from_conn_string(...))",
            "what_triggers": "compile() with a checkpointer backend",
        },
        "ir_gap": "IR resume is a flag, not a durable execution log this estate does not have",
        "downstream_consequence": "Exactly-once checkpoint/resume is UNACHIEVED without an architecture-lane log",
        "safety_class": None,
        "frequency": "typical-langgraph",
        "transferability": "REQUIRES-DURABLE-LOG",
        "degrade": "route-architecture",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0049-pregel-runtime",
        "adapter_id": "WFA-0049",
        "native_field": "pregel_runtime_loop",
        "source_construct": "LangGraph Pregel execution loop",
        "worked_example": {
            "source": "langgraph/pregel/__init__.py",
            "snippet": "Pregel.invoke(state)",
            "what_triggers": "graph is run by Pregel rather than described",
        },
        "ir_gap": "IR has no execution runtime; Pregel cannot be a node",
        "downstream_consequence": "Importing LangGraph as the runner is a second control plane",
        "safety_class": None,
        "frequency": "universal-for-langgraph",
        "transferability": "DECLARED-LOSS",
        "degrade": "refuse-import",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0050-turn-loop",
        "adapter_id": "WFA-0050",
        "native_field": "live_conversational_turn_loop",
        "source_construct": "AutoGen/CrewAI live speaker-selection conversational loop",
        "worked_example": {
            "source": "autogen/agentchat/groupchat.py",
            "snippet": "GroupChatManager.select_speaker(last_speaker, groupchat)",
            "what_triggers": "turn policy requires a live conversational loop",
        },
        "ir_gap": "IR roles and barriers have no live speaker-selection loop",
        "downstream_consequence": "Group-chat crews are not interchangeable with a barrier DAG",
        "safety_class": None,
        "frequency": "framework-core",
        "transferability": "NON-TRANSFERABLE",
        "degrade": "mark-non-transferable",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0050-llm-judge-termination",
        "adapter_id": "WFA-0050",
        "native_field": "llm_judge_termination",
        "source_construct": "LLM-as-judge termination ('when the conversation feels done')",
        "worked_example": {
            "source": "autogen GroupChat is_termination_msg",
            "snippet": "is_termination_msg = lambda m: llm_says_done(m)",
            "what_triggers": "stop is a model judgement, not a Boolean stopping expression",
        },
        "ir_gap": "IR stopping_expressions are Boolean (CNF-0089 grammar), not LLM judges",
        "downstream_consequence": "Dropping the stop leaves the crew without a halt; filling a max_rounds default forges a stop",
        "safety_class": "stop_rule",
        "frequency": "common-groupchat",
        "transferability": "NON-TRANSFERABLE",
        "degrade": "refuse-or-require-boolean",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0051-durable-log",
        "adapter_id": "WFA-0051",
        "native_field": "durable_execution_log",
        "source_construct": "Temporal history / Airflow XCom durable execution log",
        "worked_example": {
            "source": "temporalio workflow history",
            "snippet": "workflow.replay(history_events)",
            "what_triggers": "determinism claimed from a durable log this estate does not have",
        },
        "ir_gap": "IR resume is not a durable log; faking it with a file is forbidden",
        "downstream_consequence": "Deterministic replay is UNACHIEVED; route to the architecture lane",
        "safety_class": None,
        "frequency": "framework-core",
        "transferability": "REQUIRES-DURABLE-LOG",
        "degrade": "route-architecture",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0051-airflow-sensor",
        "adapter_id": "WFA-0051",
        "native_field": "airflow_sensor_poke",
        "source_construct": "Airflow ExternalTaskSensor poke loop",
        "worked_example": {
            "source": "airflow.sensors.external_task.ExternalTaskSensor",
            "snippet": "ExternalTaskSensor(poke_interval=60, timeout=3600)",
            "what_triggers": "stage waits by polling an external store",
        },
        "ir_gap": "IR has gates with predicates, not a sensor poke runtime",
        "downstream_consequence": "External wait is not scheduled unless the estate supplies an equivalent sensor",
        "safety_class": None,
        "frequency": "common-airflow",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0051-task-sla-kill",
        "adapter_id": "WFA-0051",
        "native_field": "task_sla_kill",
        "source_construct": "task-level SLA that kills the task on breach",
        "worked_example": {
            "source": "airflow SLA / Prefect timeout",
            "snippet": "sla=timedelta(minutes=5)  # kill on breach",
            "what_triggers": "timeout is a stop, not a metric",
        },
        "ir_gap": "IR retries do not encode a kill-on-SLA stop rule",
        "downstream_consequence": "Dropping the SLA removes the stop; the stage can run unbounded",
        "safety_class": "stop_rule",
        "frequency": "occasional",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0052-environment-reviewers",
        "adapter_id": "WFA-0052",
        "native_field": "environment_protection_reviewers",
        "source_construct": "GitHub Environment protection required reviewers",
        "worked_example": {
            "source": ".github/workflows/quality.yml job.deploy",
            "snippet": "environment: production  # required_reviewers: release-owners",
            "what_triggers": "job names a protected environment with required reviewers",
        },
        "ir_gap": "IR human_checkpoints can name a checkpoint, not GitHub environment policy",
        "downstream_consequence": "Dropping protection ships to production without the permission bound",
        "safety_class": "permission_bound",
        "frequency": "deploy-jobs",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0052-matrix-fail-fast",
        "adapter_id": "WFA-0052",
        "native_field": "matrix_fail_fast",
        "source_construct": "strategy.fail-fast: true (stop remaining matrix legs)",
        "worked_example": {
            "source": ".github/workflows/quality.yml",
            "snippet": "strategy: { fail-fast: true, matrix: { python: [3.11, 3.12] } }",
            "what_triggers": "fail-fast is true on a matrix job",
        },
        "ir_gap": "IR fan_out has no fail-fast stop across sibling stages",
        "downstream_consequence": "Dropping fail-fast continues later legs and hides the stop rule",
        "safety_class": "stop_rule",
        "frequency": "common-matrix",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0052-required-optional-check",
        "adapter_id": "WFA-0052",
        "native_field": "required_vs_optional_check",
        "source_construct": "required status check vs optional check (must not flatten)",
        "worked_example": {
            "source": "branch protection + workflow job",
            "snippet": "unit=required lint=optional",
            "what_triggers": "two jobs with different required-context status",
        },
        "ir_gap": "IR gates are blocking or they are not; optional-check is a distinct native status",
        "downstream_consequence": "Flattening makes an optional job a gate or drops a required gate",
        "safety_class": "gate",
        "frequency": "ci-core",
        "transferability": "DECLARED-LOSS",
        "degrade": "loud-flag",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0052-dynamic-matrix",
        "adapter_id": "WFA-0052",
        "native_field": "runtime_dynamic_matrix",
        "source_construct": "matrix materialised only at runtime from a prior job output",
        "worked_example": {
            "source": ".github/workflows/quality.yml",
            "snippet": "matrix: ${{ fromJson(needs.setup.outputs.matrix) }}",
            "what_triggers": "matrix is an expression, not a static list",
        },
        "ir_gap": "IR fan_out can hold a materialised stage list, not a GHA expression evaluated later",
        "downstream_consequence": "Unexpanded matrix under-counts steps; adapter must refuse or expand from a pinned snapshot",
        "safety_class": None,
        "frequency": "occasional",
        "transferability": "DECLARED-LOSS",
        "degrade": "refuse-unexpanded",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0053-underspecified-stop",
        "adapter_id": "WFA-0053",
        "native_field": "underspecified_stop",
        "source_construct": "paper protocol with no quoted stopping rule",
        "worked_example": {
            "source": "papers/underspecified-protocol.pdf",
            "snippet": "the panel continues until the discussion is fruitful",
            "what_triggers": "no evaluator-readable stop; prose only",
        },
        "ir_gap": "IR stopping_expressions require a Boolean form; implied stops are not representable",
        "downstream_consequence": "Filling a default stop forges a halt; adapter must REFUSE UNDERSPECIFIED",
        "safety_class": "stop_rule",
        "frequency": "common-in-papers",
        "transferability": "UNDERSPECIFIED",
        "degrade": "refuse",
        "acceptability": "BLOCKS_ADOPT",
    },
    {
        "loss_id": "LOSS-0053-statistical-scoring",
        "adapter_id": "WFA-0053",
        "native_field": "statistical_scoring_function",
        "source_construct": "Elo / p-value scoring that is not a Boolean stopping expression",
        "worked_example": {
            "source": "papers/deliberation-protocol.md:40",
            "snippet": "rank speakers by Elo after each round",
            "what_triggers": "scoring function named without a Boolean halt",
        },
        "ir_gap": "IR has no statistical scorer node type",
        "downstream_consequence": "Ranking side-effects are dropped; halt must not be inferred from Elo",
        "safety_class": None,
        "frequency": "occasional",
        "transferability": "DECLARED-LOSS",
        "degrade": "mark-missing",
        "acceptability": "ACCEPTABLE",
    },
    {
        "loss_id": "LOSS-0053-implied-n",
        "adapter_id": "WFA-0053",
        "native_field": "implied_participant_count",
        "source_construct": "participant count implied ('a small panel') not pinned",
        "worked_example": {
            "source": "papers/deliberation-protocol.md:8",
            "snippet": "a small panel of experts",
            "what_triggers": "n is prose, not a number",
        },
        "ir_gap": "IR roles need a pinned participant count or an explicit UNKNOWN",
        "downstream_consequence": "A plausible default n is a hallucinated field; adapter must mark MISSING and refuse ADOPT",
        "safety_class": None,
        "frequency": "common-in-papers",
        "transferability": "UNDERSPECIFIED",
        "degrade": "refuse",
        "acceptability": "ACCEPTABLE",
    },
]


def annotate(row: dict) -> dict:
    """Fill severity and blocks_adopt. Safety losses are P1 regardless of frequency."""
    out = dict(row)
    safety = out.get("safety_class")
    transfer = str(out.get("transferability") or "")
    if safety in SAFETY:
        out["severity"] = "P1"
        out["blocks_adopt"] = True
        out["acceptability"] = "BLOCKS_ADOPT"
    else:
        out["severity"] = "P2"
        block = transfer in TRANSFER_BLOCK or out.get("acceptability") == "BLOCKS_ADOPT"
        out["blocks_adopt"] = bool(block)
        if block:
            out["acceptability"] = "BLOCKS_ADOPT"
        else:
            out["acceptability"] = "ACCEPTABLE"
    out["safety_p1_rule"] = (
        "a loss that removes a safety property (gate, permission bound, "
        "stop rule) is P1 regardless of frequency"
    )
    return out


def declared_rows() -> list[dict]:
    return [annotate(dict(r)) for r in DECLARED]


def declared_fields_by_adapter() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in DECLARED:
        out.setdefault(str(row["adapter_id"]), set()).add(str(row["native_field"]))
    return out


def compare(
    declared_by: dict[str, set[str]],
    measured_by: dict[str, set[str]],
) -> dict:
    adapters = sorted(set(declared_by) | set(measured_by))
    undeclared: list[dict] = []
    unobserved: list[dict] = []
    per: dict[str, dict] = {}
    for uid in adapters:
        d = set(declared_by.get(uid) or [])
        m = set(measured_by.get(uid) or [])
        leak = sorted(m - d)
        miss = sorted(d - m)
        per[uid] = {
            "declared": sorted(d),
            "measured": sorted(m),
            "undeclared_leaks": leak,
            "declared_unobserved": miss,
        }
        for name in leak:
            undeclared.append({"adapter_id": uid, "native_field": name})
        for name in miss:
            unobserved.append({"adapter_id": uid, "native_field": name})
    return {
        "aligned": len(undeclared) == 0,
        "undeclared_leaks": undeclared,
        "declared_unobserved": unobserved,
        "per_adapter": per,
        "n_undeclared": len(undeclared),
        "n_unobserved": len(unobserved),
    }


def safety_violations(rows: list[dict]) -> list[str]:
    """Ids where a safety-class loss is not P1 or does not block ADOPT."""
    bad: list[str] = []
    for row in rows:
        safety = row.get("safety_class")
        if safety in SAFETY:
            if row.get("severity") != "P1" or row.get("blocks_adopt") is not True:
                bad.append(str(row.get("loss_id")))
        elif row.get("severity") == "P1" and safety not in SAFETY:
            # P1 is reserved for safety properties here.
            bad.append(str(row.get("loss_id")))
    return bad


def evaluate_adopt(
    adapter_id: str,
    used_fields: list[str] | None = None,
    rows: list[dict] | None = None,
) -> dict:
    """Disposition-gate consumer: ADOPT blocked by P1 safety or transfer blocks."""
    rows = rows if rows is not None else declared_rows()
    used = None if used_fields is None else set(used_fields)
    blocking: list[dict] = []
    for row in rows:
        if row.get("adapter_id") != adapter_id:
            continue
        if used is not None and row.get("native_field") not in used:
            continue
        if row.get("blocks_adopt"):
            blocking.append(
                {
                    "loss_id": row["loss_id"],
                    "native_field": row["native_field"],
                    "safety_class": row.get("safety_class"),
                    "severity": row.get("severity"),
                    "transferability": row.get("transferability"),
                    "reason": row.get("downstream_consequence"),
                }
            )
    p1 = [b for b in blocking if b.get("severity") == "P1"]
    if p1:
        ceiling = "ADOPT-BLOCKED"
    elif blocking:
        ceiling = "ADOPT-BLOCKED"
    else:
        ceiling = "ADOPT-PERMITTED-WITH-DECLARED-LOSS"
    return {
        "adapter_id": adapter_id,
        "allowed": len(blocking) == 0,
        "ceiling": ceiling,
        "blocking_losses": blocking,
        "n_blocking": len(blocking),
        "n_p1_blocking": len(p1),
    }


def gate_all_adapters(rows: list[dict] | None = None) -> dict[str, dict]:
    from corpus import ADAPTER_IDS

    rows = rows if rows is not None else declared_rows()
    return {uid: evaluate_adopt(uid, None, rows) for uid in ADAPTER_IDS}


def ingest_wfa0054(repo) -> dict[str, Any]:
    """Union WFA-0054 differing fields into measured, if that artifact exists."""
    rel = "command-center/wfa/WFA-0054-ir-roundtrip-fidelity.json"
    path = Path(repo) / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "present": False,
            "path": rel,
            "fields_by_adapter": {},
            "note": "WFA-0054 artifact absent on this worktree; measured set is this unit's projector on the nine native fixtures",
        }
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "present": True,
            "parse_error": type(exc).__name__,
            "fields_by_adapter": {},
            "note": "WFA-0054 present but unparseable; not merged",
        }
    fields: dict[str, list[str]] = {}
    rows = []
    if isinstance(doc, dict):
        for key in ("per_adapter", "adapters", "roundtrips", "results"):
            if isinstance(doc.get(key), list):
                rows = doc[key]
                break
        if not rows and isinstance(doc.get("differing_fields"), list):
            rows = [doc]
    for row in rows:
        if not isinstance(row, dict):
            continue
        uid = str(row.get("adapter_id") or row.get("id") or "")
        lost = (
            row.get("differing_fields")
            or row.get("lost_fields")
            or row.get("dropped")
            or []
        )
        if uid.startswith("WFA-") and isinstance(lost, list):
            fields.setdefault(uid, [])
            for item in lost:
                if isinstance(item, str):
                    fields[uid].append(item)
                elif isinstance(item, dict) and item.get("native_field"):
                    fields[uid].append(str(item["native_field"]))
    return {
        "present": True,
        "path": "command-center/wfa/WFA-0054-ir-roundtrip-fidelity.json",
        "fields_by_adapter": {k: sorted(set(v)) for k, v in fields.items()},
        "note": "WFA-0054 differing-field set unioned into measured",
    }
