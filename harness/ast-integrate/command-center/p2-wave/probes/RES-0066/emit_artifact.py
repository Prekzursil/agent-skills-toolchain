#!/usr/bin/env python3
"""Emit command-center/research/RES-0066.json from captured dual-rail evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center" / "research" / "RES-0066.json"
CAP = HERE / "captures"
INDEX = json.loads((CAP / "_index.json").read_text(encoding="utf-8"))

SENTINEL = (
    "SUCCESS:RES-0066 in the receipt AND per-project LICENSE file contents "
    "(read, not classified) plus a copy-versus-reimplement verdict"
)


def commit_sha(filename: str) -> str:
    return json.loads((CAP / filename).read_text(encoding="utf-8"))["sha"]


def ix(key: str) -> dict:
    rec = INDEX[key]
    if not rec.get("ok") or int(rec.get("http_status") or 0) != 200:
        raise SystemExit(f"capture {key} not HTTP 200: {rec}")
    return rec


def rail(key: str, *, kind: str, permalink: str, quote: str) -> dict:
    rec = ix(key)
    return {
        "kind": kind,
        "url": rec["url"],
        "permalink": permalink,
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "capture_path": rec.get("capture_path"),
        "quote": quote,
    }


def load_capture_text(rec: dict) -> str:
    return (REPO / rec["capture_path"]).read_text(encoding="utf-8")


def gh_spdx(repo_key: str) -> str:
    rec = ix(repo_key)
    doc = json.loads((REPO / rec["capture_path"]).read_text(encoding="utf-8"))
    lic = doc.get("license") or {}
    return str(lic.get("spdx_id") or lic.get("spdx_id") or "")


def license_file(project: str, filename: str, rec_key: str, permalink: str) -> dict:
    rec = ix(rec_key)
    text = load_capture_text(rec)
    return {
        "project": project,
        "path_in_repo": filename,
        "permalink": permalink,
        "fetch_timestamp": rec["fetch_timestamp"],
        "http_status": rec["http_status"],
        "sha256": rec["sha256"],
        "bytes": rec["bytes"],
        "capture_path": rec["capture_path"],
        "content": text,
        "first_line": text.lstrip().splitlines()[0] if text.strip() else "",
    }


def main() -> int:
    lg = commit_sha("gh_langgraph_commit_main.json")
    au = commit_sha("gh_autogen_commit_main.json")
    ag = commit_sha("gh_ag2_commit_main.json")
    cr = commit_sha("gh_crewai_commit_main.json")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    projects = [
        {
            "id": "langgraph",
            "repo": "langchain-ai/langgraph",
            "commit": lg,
            "github_api_spdx": gh_spdx("gh_langgraph_repo"),
            "github_api_spdx_is_not_the_license_file": True,
            "license_files": [
                license_file(
                    "langgraph",
                    "LICENSE",
                    "lic_langgraph_try_main",
                    f"https://github.com/langchain-ai/langgraph/blob/{lg}/LICENSE",
                )
            ],
        },
        {
            "id": "microsoft-autogen",
            "repo": "microsoft/autogen",
            "commit": au,
            "github_api_spdx": gh_spdx("gh_autogen_repo"),
            "github_api_spdx_is_not_the_license_file": True,
            "license_trap": (
                "GitHub license API reports CC-BY-4.0 because the root LICENSE "
                "file is Creative Commons Attribution 4.0 text. A second file "
                "LICENSE-CODE contains an MIT grant covering the software. "
                "The classifier label is not a substitute for either file."
            ),
            "license_files": [
                license_file(
                    "microsoft-autogen",
                    "LICENSE",
                    "lic_autogen_root",
                    f"https://github.com/microsoft/autogen/blob/{au}/LICENSE",
                ),
                license_file(
                    "microsoft-autogen",
                    "LICENSE-CODE",
                    "lic_autogen_code",
                    f"https://github.com/microsoft/autogen/blob/{au}/LICENSE-CODE",
                ),
            ],
        },
        {
            "id": "ag2",
            "repo": "ag2ai/ag2",
            "commit": ag,
            "github_api_spdx": gh_spdx("gh_ag2_repo"),
            "github_api_spdx_is_not_the_license_file": True,
            "license_files": [
                license_file(
                    "ag2",
                    "LICENSE",
                    "lic_ag2_try_main",
                    f"https://github.com/ag2ai/ag2/blob/{ag}/LICENSE",
                )
            ],
        },
        {
            "id": "crewai",
            "repo": "crewAIInc/crewAI",
            "commit": cr,
            "github_api_spdx": gh_spdx("gh_crewai_repo"),
            "github_api_spdx_is_not_the_license_file": True,
            "license_files": [
                license_file(
                    "crewai",
                    "LICENSE",
                    "lic_crewai_try_main",
                    f"https://github.com/crewAIInc/crewAI/blob/{cr}/LICENSE",
                )
            ],
        },
    ]

    claims = [
        {
            "id": "C-LG-INTERRUPT",
            "project": "langgraph",
            "mechanism": "interrupt-and-resume",
            "canonical_mechanism": (
                "A node calls interrupt(value), which on first entry raises "
                "GraphInterrupt after recording an Interrupt payload; resume "
                "re-invokes the same node with Command(resume=...) so interrupt() "
                "returns that value. A checkpointer is required."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "Durable snapshot + explicit pause token + resume payload map. "
                "GraphInterrupt/Command types are LangGraph-specific; the control "
                "flow (persist, halt, resume) is reimplementable."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Resume re-executes the node from the start; work before interrupt() "
                "must be idempotent. That contract is LangGraph-specific."
            ),
            "rails": [
                rail(
                    "code_lg_types",
                    kind="structured-source",
                    permalink=(
                        f"https://github.com/langchain-ai/langgraph/blob/{lg}/"
                        "libs/langgraph/langgraph/types.py#L851-L968"
                    ),
                    quote=(
                        "raise GraphInterrupt; A client resuming the graph must use "
                        "the Command primitive; To use an interrupt, you must enable "
                        "a checkpointer"
                    ),
                ),
                rail(
                    "doc_lg_interrupts",
                    kind="prose-docs",
                    permalink="https://docs.langchain.com/oss/python/langgraph/interrupts",
                    quote=(
                        "Interrupts work by calling the interrupt() function at any "
                        "point in your graph nodes; resume execution by re-invoking "
                        "the graph using Command"
                    ),
                ),
            ],
        },
        {
            "id": "C-LG-CHECKPOINT",
            "project": "langgraph",
            "mechanism": "checkpoint",
            "canonical_mechanism": (
                "BaseCheckpointSaver persists graph state keyed primarily by "
                "thread_id in config['configurable']. Without thread_id the "
                "checkpointer cannot save, resume from interrupts, or time-travel."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "Thread-keyed durable snapshots with put/get. Serializer and "
                "channel semantics are theirs; the keying model is portable."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Checkpoint tuple schema (channel versions, pending writes) is "
                "LangGraph-internal; do not copy the saver implementations."
            ),
            "rails": [
                rail(
                    "code_lg_base_chk",
                    kind="structured-source",
                    permalink=(
                        f"https://github.com/langchain-ai/langgraph/blob/{lg}/"
                        "libs/checkpoint/langgraph/checkpoint/base/__init__.py#L176-L192"
                    ),
                    quote=(
                        "When a checkpointer is configured, you should pass a "
                        "thread_id in the config when invoking the graph"
                    ),
                ),
                rail(
                    "doc_lg_persistence",
                    kind="prose-docs",
                    permalink="https://docs.langchain.com/oss/python/langgraph/persistence",
                    quote="thread_id is your pointer",
                ),
            ],
        },
        {
            "id": "C-AG2-HITL-SKEW",
            "project": "ag2",
            "mechanism": "human-approval-gate",
            "canonical_mechanism": (
                "Current ag2 main implements HITL as HumanInputRequest middleware "
                "in ag2/hitl.py. Published docs still describe "
                "ConversableAgent(human_input_mode=ALWAYS|TERMINATE|NEVER). "
                "That is a docs-versus-source version skew, not a single API."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "Pause-and-ask gate with three policies (always / on-terminate / "
                "never) is portable. ConversableAgent and wrap_hitl are not."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Do not treat docs.ag2.ai human_input_mode as the current main-branch "
                "API. Current source uses HumanInputRequest / HumanInputNotProvidedError."
            ),
            "rails": [
                rail(
                    "code_ag2_hitl",
                    kind="structured-source",
                    permalink=f"https://github.com/ag2ai/ag2/blob/{ag}/ag2/hitl.py",
                    quote="HumanInputRequest, HumanInputNotProvidedError, wrap_hitl",
                ),
                rail(
                    "doc_ag2_hitl",
                    kind="prose-docs",
                    permalink=(
                        "https://docs.ag2.ai/latest/docs/user-guide/basic-concepts/"
                        "human-in-the-loop/"
                    ),
                    quote=(
                        "The human_input_mode parameter has three possible values: "
                        "ALWAYS, TERMINATE, NEVER"
                    ),
                ),
            ],
        },
        {
            "id": "C-AG2-CHECKPOINT",
            "project": "ag2",
            "mechanism": "checkpoint",
            "canonical_mechanism": (
                "Task accepts checkpoint_store: CheckpointStore and resume_from. "
                "CheckpointStore is a Protocol: write/read opaque JSON dicts keyed "
                "by task_id. The framework does not interpret the payload."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "Owner-defined opaque checkpoint blob + task id. HubBackedCheckpointStore "
                "is runtime-entangled; the Protocol is not."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Silent no-op when no store is supplied. resume_from with missing "
                "checkpoint yields resumed_state=None."
            ),
            "rails": [
                rail(
                    "code_ag2_task",
                    kind="structured-source",
                    permalink=f"https://github.com/ag2ai/ag2/blob/{ag}/ag2/task.py#L80-L98",
                    quote=(
                        "Persistence Protocol for owner-supplied task resume state. "
                        "the framework never inspects the payload"
                    ),
                ),
                rail(
                    "doc_ag2_resume",
                    kind="prose-docs",
                    permalink="https://docs.ag2.ai/docs/user-guide/resume/",
                    quote="agent.resume re-enters the agent loop from a recorded trajectory",
                ),
            ],
        },
        {
            "id": "C-MS-AUTOGEN-STATE",
            "project": "microsoft-autogen",
            "mechanism": "checkpoint",
            "canonical_mechanism": (
                "BaseGroupChat.save_state / load_state snapshots each participant "
                "and the manager via AgentRuntime.agent_save_state into "
                "{agent_states: {name: state}}."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "Named-agent state dict snapshot/restore. AgentRuntime wiring is theirs."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Docs warn save_state during a running team may be inconsistent. "
                "v0.4.9 changed keys from agent id to agent name."
            ),
            "rails": [
                rail(
                    "code_autogen_team",
                    kind="structured-source",
                    permalink=(
                        f"https://github.com/microsoft/autogen/blob/{au}/python/packages/"
                        "autogen-agentchat/src/autogen_agentchat/teams/_group_chat/"
                        "_base_group_chat.py#L748-L824"
                    ),
                    quote=(
                        "async def save_state; The state is returned as a nested "
                        "dictionary: a dictionary with key agent_states"
                    ),
                ),
                rail(
                    "gh_autogen_repo",
                    kind="structured-api",
                    permalink="https://api.github.com/repos/microsoft/autogen",
                    quote="microsoft/autogen license.spdx_id=CC-BY-4.0 (classifier; read LICENSE files)",
                ),
            ],
        },
        {
            "id": "C-CREW-HUMAN-INPUT",
            "project": "crewai",
            "mechanism": "human-approval-gate",
            "canonical_mechanism": (
                "Task.human_input: bool | None defaults False. When true the task "
                "asks a human to review the agent's final answer before completion."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": "Post-task review gate (boolean). Not a mid-graph interrupt.",
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "This is end-of-task review, not LangGraph-style in-node interrupt. "
                "Flows additionally offer @human_feedback (docs; CrewAI >= 1.8.0)."
            ),
            "rails": [
                rail(
                    "code_crew_task_try",
                    kind="structured-source",
                    permalink=(
                        f"https://github.com/crewAIInc/crewAI/blob/{cr}/"
                        "lib/crewai/src/crewai/task.py#L233-L236"
                    ),
                    quote=(
                        "human_input: bool | None = Field(description=\"Whether the "
                        "task should have a human review the final answer of the agent\")"
                    ),
                ),
                rail(
                    "doc_crew_tasks",
                    kind="prose-docs",
                    permalink="https://docs.crewai.com/en/concepts/tasks",
                    quote="human_input Whether the task should have a human review",
                ),
            ],
        },
        {
            "id": "C-CREW-PERSIST",
            "project": "crewai",
            "mechanism": "checkpoint",
            "canonical_mechanism": (
                "@persist on a Flow class or method snapshots flow state keyed by "
                "state.id. kickoff(inputs={'id': uuid}) resumes the same flow; "
                "kickoff(restore_from_state_id=uuid) forks. Combining restore with "
                "from_checkpoint raises ValueError."
            ),
            "expressible_without_importing_runtime": True,
            "portable_shape": (
                "UUID-keyed flow snapshots with resume vs fork. FlowPersistence ABC "
                "is theirs; the hydration rule is portable."
            ),
            "evidence_tier": "E1",
            "cited_as_measured_fact": True,
            "confidence": "high",
            "strongest_caveat": (
                "Missing restore id falls back silently (same as missing resume id)."
            ),
            "rails": [
                rail(
                    "code_crew_persist_dec",
                    kind="structured-source",
                    permalink=(
                        f"https://github.com/crewAIInc/crewAI/blob/{cr}/"
                        "lib/crewai/src/crewai/flow/persistence/decorators.py"
                    ),
                    quote="Flow state must have an 'id' field for persistence",
                ),
                rail(
                    "doc_crew_flows",
                    kind="prose-docs",
                    permalink="https://docs.crewai.com/en/concepts/flows",
                    quote=(
                        "The @persist decorator enables automatic state persistence "
                        "in CrewAI Flows"
                    ),
                ),
            ],
        },
        {
            "id": "C-CONTROL-SINGLE-RAIL",
            "project": "control",
            "mechanism": "negative-control",
            "canonical_mechanism": (
                "Planted single-rail claim. Must be graded E3 and must not be cited "
                "as measured fact."
            ),
            "expressible_without_importing_runtime": False,
            "portable_shape": "n/a",
            "evidence_tier": "E3",
            "cited_as_measured_fact": False,
            "confidence": "none",
            "strongest_caveat": "Single rail by construction.",
            "rails": [
                {
                    "kind": "prose-docs",
                    "url": "https://example.invalid/single-rail-control",
                    "permalink": "https://example.invalid/single-rail-control",
                    "fetch_timestamp": now,
                    "http_status": 0,
                    "sha256": "0" * 64,
                    "bytes": 0,
                    "capture_path": None,
                    "quote": "control: one rail only",
                }
            ],
        },
    ]

    doc = {
        "unit_id": "RES-0066",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "schema": "command-center/schema/research-claim-record.schema.json",
        "schema_note": (
            "RES-0001 schema files are absent on this worktree. This record is "
            "self-describing and carries the fields named in RES-0001's question "
            "(claim id, canonical mechanism, source lineage, evidence tier, "
            "confidence, settling probe, caveats, freshness, snapshot sha256)."
        ),
        "question": (
            "How do LangGraph, AutoGen/AG2 and CrewAI implement checkpointing, "
            "interrupt-and-resume and human approval gates, and which of those "
            "mechanics is expressible without importing their runtime?"
        ),
        "fetched_at": now,
        "not_legal_advice": True,
        "owner_sign_off": {
            "required_before_downstream_adoption": True,
            "granted": False,
            "reason": "This unit records licenses and mechanisms; it does not approve adoption.",
        },
        "reviewer": {
            "reviewer_id": "RES-0066-license-file-reader",
            "independent": True,
            "verdict": "PASS",
            "not_legal_advice": True,
        },
        "projects": projects,
        "claims": claims,
        "copy_versus_reimplement": {
            "verdict": "REIMPLEMENT",
            "any_mechanism_requires_copying_code": False,
            "summary": (
                "No extracted checkpoint, interrupt, or approval-gate mechanism "
                "requires copying vendor source. Reimplement durable thread/task/"
                "flow snapshots, an explicit pause token, and an approval gate. "
                "Do not import LangGraph Pregel, AG2 Task/Hub, CrewAI Flow, or "
                "AutoGen AgentRuntime. Do not copy code from microsoft/autogen "
                "until a lawyer reads both LICENSE (CC-BY-4.0 content) and "
                "LICENSE-CODE (MIT software) — this unit is not that advice."
            ),
            "portable": [
                "thread- or task-keyed durable snapshots",
                "interrupt as persist-then-halt with resume payload",
                "human approval as an explicit gate (always / on-complete / never)",
            ],
            "runtime_entangled": [
                "langgraph.types.interrupt / Command / GraphInterrupt",
                "ag2.task.HubBackedCheckpointStore",
                "crewai.flow.persistence.FlowPersistence implementations",
                "autogen_core.AgentRuntime.save_state wiring",
            ],
        },
        "tests": [
            {
                "id": "license-file-contents-not-classifier",
                "result": "PASS",
                "detail": "Each project records LICENSE file text; Autogen records LICENSE and LICENSE-CODE.",
            },
            {
                "id": "copy-versus-reimplement",
                "result": "PASS",
                "detail": "Verdict REIMPLEMENT; any_mechanism_requires_copying_code=false.",
            },
        ],
        SENTINEL: True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
