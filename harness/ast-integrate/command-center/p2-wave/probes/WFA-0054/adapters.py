#!/usr/bin/env python3
"""Nine dialect adapters: native → IR → native.

Each adapter declares the fields it carries and the fields it knowingly drops.
The harness, not the adapter, decides whether a measured drop is already in
the ledger.
"""
from __future__ import annotations

import itertools
from typing import Any, Callable

from ir import empty_ir, node, validate_ir

Native = dict[str, Any]
IR = dict[str, Any]


class Adapter:
    def __init__(
        self,
        *,
        adapter_id: str,
        unit_id: str,
        carried_fields: tuple[str, ...],
        lossy_fields: tuple[str, ...],
        to_ir: Callable[[Native], IR],
        from_ir: Callable[[IR], Native],
        plant: tuple[Any, ...],
    ) -> None:
        self.adapter_id = adapter_id
        self.unit_id = unit_id
        self.carried_fields = carried_fields
        self.lossy_fields = lossy_fields
        self._to_ir = to_ir
        self._from_ir = from_ir
        self.plant = plant

    def to_ir(self, native: Native) -> IR:
        ir = self._to_ir(native)
        validate_ir(ir)
        return ir

    def from_ir(self, ir: IR) -> Native:
        validate_ir(ir)
        return self._from_ir(ir)


def _roles_from_agents(agents: list[str], anchor: str) -> list[dict[str, Any]]:
    roles = []
    seen: set[str] = set()
    for agent in agents:
        if agent in seen:
            continue
        seen.add(agent)
        roles.append(node({"id": agent, "name": agent, "kind": "role"}, f"{anchor}#role:{agent}"))
    return roles


def saved_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"saved-workflow:{aid}"
    ir = empty_ir(adapter_id="saved-workflow", native_id=aid, source_anchor=root)
    ir["artifact_name"] = native["filename"]
    all_agents: list[str] = []
    for i, phase in enumerate(native["phases"]):
        st_anchor = f"{root}#phases[{i}]"
        ir["stages"].append(
            node(
                {
                    "id": phase["name"],
                    "name": phase["name"],
                    "kind": "phase",
                    "agents": list(phase["agents"]),
                    "parallel": bool(phase["parallel"]),
                    "schema": phase.get("schema"),
                    "barrier": phase.get("barrier"),
                    "worktree": bool(phase.get("worktree")),
                    "background": bool(native.get("background")),
                },
                st_anchor,
            )
        )
        all_agents.extend(phase["agents"])
        if phase.get("schema"):
            ir["gates"].append(
                node(
                    {
                        "id": f"schema-{phase['name']}",
                        "kind": "schema-fan-in",
                        "condition": phase["schema"],
                        "blocking": True,
                    },
                    f"{st_anchor}#schema",
                )
            )
        if phase.get("barrier"):
            ir["barriers"].append(
                node(
                    {
                        "id": f"barrier-{phase['name']}",
                        "kind": "barrier",
                        "mode": phase["barrier"],
                    },
                    f"{st_anchor}#barrier",
                )
            )
        if phase.get("parallel"):
            ir["fan_out"].append(
                node(
                    {
                        "id": f"fanout-{phase['name']}",
                        "kind": "fan-out",
                        "stage_id": phase["name"],
                    },
                    f"{st_anchor}#fan-out",
                )
            )
    ir["roles"] = _roles_from_agents(all_agents, root)
    ir["tool_policy"] = node(dict(native["tool_policy"]), f"{root}#tool_policy")
    ir["stopping"] = node({"expression": native["stopping"]}, f"{root}#stopping")
    ir["resume"] = node({"enabled": False}, f"{root}#resume")
    ir["lineage"] = node({"parent_ids": []}, f"{root}#lineage")
    # comments, date_now_construct, args_as_string deliberately not copied
    return ir


def saved_from_ir(ir: IR) -> Native:
    phases = []
    for st in ir["stages"]:
        phase = {
            "name": st["name"],
            "agents": list(st["agents"]),
            "parallel": bool(st["parallel"]),
            "worktree": bool(st["worktree"]),
        }
        if st.get("schema") is not None:
            phase["schema"] = st["schema"]
        if st.get("barrier") is not None:
            phase["barrier"] = st["barrier"]
        phases.append(phase)
    return {
        "id": ir["id"],
        "filename": ir["artifact_name"],
        "phases": phases,
        "tool_policy": {
            "allow": list(ir["tool_policy"].get("allow") or []),
            "deny": list(ir["tool_policy"].get("deny") or []),
        },
        "stopping": ir["stopping"]["expression"],
        "background": bool(ir["stages"][0].get("background")) if ir["stages"] else False,
    }


def metaswarm_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"metaswarm:{aid}"
    ir = empty_ir(adapter_id="metaswarm", native_id=aid, source_anchor=root)
    ir["coverage_enforcement"] = bool(native["coverage_enforcement"])
    ir["knowledge_capture_before_pr"] = bool(native["knowledge_capture_before_pr"])
    ir["vendor_runtime_import"] = bool(native["vendor_runtime_import"])
    for i, phase in enumerate(native["phases"]):
        st_anchor = f"{root}#phases[{i}]"
        ir["stages"].append(
            node(
                {
                    "id": phase["name"],
                    "name": phase["name"],
                    "kind": "metaswarm-phase",
                    "gate_name": phase.get("gate"),
                    "index": i,
                },
                st_anchor,
            )
        )
        if phase.get("gate") is not None:
            ir["gates"].append(
                node(
                    {
                        "id": phase["gate"],
                        "kind": "gate",
                        "condition": phase["gate"],
                        "blocking": bool(phase["blocking"]),
                        "stage_id": phase["name"],
                    },
                    f"{st_anchor}#gate",
                )
            )
        elif phase["blocking"]:
            ir["gates"].append(
                node(
                    {
                        "id": f"block-{phase['name']}",
                        "kind": "gate",
                        "condition": None,
                        "blocking": True,
                        "stage_id": phase["name"],
                    },
                    f"{st_anchor}#gate",
                )
            )
    ir["stopping"] = node(
        {"expression": "blocking_gates_all_pass"},
        f"{root}#stopping",
    )
    return ir


def metaswarm_from_ir(ir: IR) -> Native:
    gates_by_stage = {g.get("stage_id"): g for g in ir["gates"]}
    phases = []
    for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0))):
        gate = gates_by_stage.get(st["name"])
        phases.append(
            {
                "name": st["name"],
                "gate": st.get("gate_name"),
                "blocking": bool(gate["blocking"]) if gate is not None else False,
            }
        )
    return {
        "id": ir["id"],
        "coverage_enforcement": bool(ir["coverage_enforcement"]),
        "knowledge_capture_before_pr": bool(ir["knowledge_capture_before_pr"]),
        "vendor_runtime_import": bool(ir["vendor_runtime_import"]),
        "phases": phases,
    }


def _stage_nodes(stages: list[dict[str, Any]], root: str) -> list[dict[str, Any]]:
    out = []
    for i, st in enumerate(stages):
        out.append(
            node(
                {
                    "id": st["title"],
                    "name": st["title"],
                    "kind": "extracted-stage",
                    "source_line": st["source_line"],
                    "body": st["body"],
                    "index": i,
                },
                f"{root}#stages[{i}]:{st['source_line']}",
            )
        )
    return out


def skill_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"skill-markdown:{aid}"
    ir = empty_ir(adapter_id="skill-markdown", native_id=aid, source_anchor=root)
    ir["extractable"] = bool(native["extractable"])
    ir["frontmatter_description"] = native.get("frontmatter_description")
    if not native["extractable"]:
        ir["verdict"] = native.get("verdict", "NOT-EXTRACTABLE")
        ir["reason"] = native.get("reason")
        ir["stopping"] = node({"expression": "NOT-EXTRACTABLE"}, f"{root}#stopping")
        return ir
    ir["stages"] = _stage_nodes(native["stages"], root)
    ir["stopping"] = node({"expression": "stages_exhausted"}, f"{root}#stopping")
    return ir


def skill_from_ir(ir: IR) -> Native:
    if not ir.get("extractable"):
        return {
            "id": ir["id"],
            "extractable": False,
            "verdict": ir.get("verdict", "NOT-EXTRACTABLE"),
            "reason": ir.get("reason"),
            "frontmatter_description": ir.get("frontmatter_description"),
            "stages": [],
        }
    stages = []
    for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0))):
        stages.append(
            {
                "title": st["name"],
                "source_line": st["source_line"],
                "body": st["body"],
            }
        )
    return {
        "id": ir["id"],
        "extractable": True,
        "frontmatter_description": ir.get("frontmatter_description"),
        "stages": stages,
    }


def slash_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"slash-command:{aid}"
    ir = empty_ir(adapter_id="slash-command", native_id=aid, source_anchor=root)
    ir["kind"] = native["kind"]
    ir["target_skill"] = native.get("target_skill")
    if native["kind"] == "ALIAS":
        ir["lineage"] = node(
            {"parent_ids": [native["target_skill"]], "edge": "alias-of"},
            f"{root}#lineage",
        )
        ir["stopping"] = node({"expression": "delegate-to-skill"}, f"{root}#stopping")
        return ir
    ir["stages"] = _stage_nodes(native["stages"], root)
    ir["stopping"] = node({"expression": "own-procedure-exhausted"}, f"{root}#stopping")
    return ir


def slash_from_ir(ir: IR) -> Native:
    if ir.get("kind") == "ALIAS":
        return {
            "id": ir["id"],
            "kind": "ALIAS",
            "target_skill": ir.get("target_skill"),
            "stages": [],
        }
    stages = []
    for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0))):
        stages.append(
            {
                "title": st["name"],
                "source_line": st["source_line"],
                "body": st["body"],
            }
        )
    return {
        "id": ir["id"],
        "kind": "OWN-PROCEDURE",
        "target_skill": None,
        "stages": stages,
    }


def langgraph_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"langgraph:{aid}"
    ir = empty_ir(adapter_id="langgraph", native_id=aid, source_anchor=root)
    for i, name in enumerate(native["nodes"]):
        ir["stages"].append(
            node({"id": name, "name": name, "kind": "graph-node", "index": i}, f"{root}#nodes[{i}]")
        )
    for i, edge in enumerate(native["edges"]):
        ir["barriers"].append(
            node(
                {"id": f"edge-{i}", "kind": "edge", "src": edge[0], "dst": edge[1]},
                f"{root}#edges[{i}]",
            )
        )
    for i, cond in enumerate(native["conditionals"]):
        ir["gates"].append(
            node(
                {
                    "id": f"cond-{i}",
                    "kind": "conditional-edge",
                    "src": cond["from"],
                    "predicate": cond["predicate"],
                    "true": cond["true"],
                    "false": cond["false"],
                },
                f"{root}#conditionals[{i}]",
            )
        )
    for i, name in enumerate(native["interrupt_before"]):
        ir["checkpoints"].append(
            node(
                {"id": f"interrupt-{name}", "kind": "human-interrupt", "before": name},
                f"{root}#interrupt_before[{i}]",
            )
        )
    ir["resume"] = node(
        {
            "enabled": native.get("checkpointer") is not None,
            "checkpointer": native.get("checkpointer"),
        },
        f"{root}#resume",
    )
    ir["reducer_names"] = dict(native.get("reducer_names") or {})
    ir["stopping"] = node({"expression": "graph-terminal"}, f"{root}#stopping")
    return ir


def langgraph_from_ir(ir: IR) -> Native:
    nodes = [st["name"] for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0)))]
    edges = [[b["src"], b["dst"]] for b in ir["barriers"] if b.get("kind") == "edge"]
    conditionals = []
    for g in ir["gates"]:
        conditionals.append(
            {
                "from": g["src"],
                "predicate": g["predicate"],
                "true": g["true"],
                "false": g["false"],
            }
        )
    interrupt_before = [c["before"] for c in ir["checkpoints"] if c.get("kind") == "human-interrupt"]
    return {
        "id": ir["id"],
        "nodes": nodes,
        "edges": edges,
        "conditionals": conditionals,
        "interrupt_before": interrupt_before,
        "checkpointer": ir["resume"].get("checkpointer"),
        "reducer_names": dict(ir.get("reducer_names") or {}),
    }


def crew_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"crew-autogen:{aid}"
    ir = empty_ir(adapter_id="crew-autogen", native_id=aid, source_anchor=root)
    ir["kind"] = native["kind"]
    ir["process"] = native["process"]
    for i, role in enumerate(native["roles"]):
        ir["roles"].append(
            node(
                {
                    "id": role["id"],
                    "name": role["name"],
                    "kind": "role",
                    "council_role": role["council_role"],
                },
                f"{root}#roles[{i}]",
            )
        )
    for i, task in enumerate(native["tasks"]):
        ir["stages"].append(
            node(
                {
                    "id": task["id"],
                    "name": task["id"],
                    "kind": "task",
                    "role": task["role"],
                    "goal": task["goal"],
                    "after": list(task.get("after") or []),
                    "index": i,
                },
                f"{root}#tasks[{i}]",
            )
        )
    ir["stopping"] = node({"expression": native["termination"]}, f"{root}#stopping")
    # live_turn_loop is NON-TRANSFERABLE and is not copied
    return ir


def crew_from_ir(ir: IR) -> Native:
    roles = [
        {"id": r["id"], "name": r["name"], "council_role": r["council_role"]}
        for r in ir["roles"]
    ]
    tasks = []
    for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0))):
        task = {"id": st["id"], "role": st["role"], "goal": st["goal"]}
        if st.get("after"):
            task["after"] = list(st["after"])
        tasks.append(task)
    return {
        "id": ir["id"],
        "kind": ir["kind"],
        "roles": roles,
        "tasks": tasks,
        "process": ir["process"],
        "termination": ir["stopping"]["expression"],
    }


def dag_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"dag-scheduler:{aid}"
    ir = empty_ir(adapter_id="dag-scheduler", native_id=aid, source_anchor=root)
    ir["framework"] = native["framework"]
    ir["replay_deterministic"] = bool(native["replay_deterministic"])
    for i, task in enumerate(native["tasks"]):
        ir["stages"].append(
            node(
                {
                    "id": task["id"],
                    "name": task["id"],
                    "kind": "task",
                    "retries": task["retries"],
                    "backoff_s": task["backoff_s"],
                    "sla_s": task.get("sla_s"),
                    "after": list(task.get("after") or []),
                    "index": i,
                },
                f"{root}#tasks[{i}]",
            )
        )
        if task.get("after"):
            ir["barriers"].append(
                node(
                    {
                        "id": f"after-{task['id']}",
                        "kind": "depends-on",
                        "stage_id": task["id"],
                        "after": list(task["after"]),
                    },
                    f"{root}#tasks[{i}]#after",
                )
            )
    for i, sensor in enumerate(native.get("sensors") or []):
        ir["checkpoints"].append(
            node(
                {
                    "id": sensor["id"],
                    "kind": sensor["kind"],
                    "target": sensor["target"],
                },
                f"{root}#sensors[{i}]",
            )
        )
    ir["stopping"] = node({"expression": "dag-complete-or-sla"}, f"{root}#stopping")
    ir["resume"] = node(
        {"enabled": True, "requires_durable_log": True, "achieved": False},
        f"{root}#resume",
    )
    return ir


def dag_from_ir(ir: IR) -> Native:
    tasks = []
    for st in sorted(ir["stages"], key=lambda s: int(s.get("index", 0))):
        task = {
            "id": st["id"],
            "retries": st["retries"],
            "backoff_s": st["backoff_s"],
            "sla_s": st.get("sla_s"),
        }
        if st.get("after"):
            task["after"] = list(st["after"])
        tasks.append(task)
    sensors = []
    for cp in ir["checkpoints"]:
        sensors.append({"id": cp["id"], "kind": cp["kind"], "target": cp["target"]})
    return {
        "id": ir["id"],
        "framework": ir["framework"],
        "tasks": tasks,
        "sensors": sensors,
        "replay_deterministic": bool(ir["replay_deterministic"]),
    }


def _expand_matrix(matrix: dict[str, list[Any]] | None) -> list[dict[str, Any]]:
    if not matrix:
        return [{}]
    keys = list(matrix.keys())
    values = [list(matrix[k]) for k in keys]
    combos = []
    for combo in itertools.product(*values):
        combos.append(dict(zip(keys, combo)))
    return combos


def gha_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"github-actions:{aid}"
    ir = empty_ir(adapter_id="github-actions", native_id=aid, source_anchor=root)
    ir["name"] = native["name"]
    ir["matrix"] = native.get("matrix")
    ir["required_contexts"] = list(native.get("required_contexts") or [])
    expansions = _expand_matrix(native.get("matrix"))
    ir["expanded_jobs"] = []
    for job_id, job in native["jobs"].items():
        j_anchor = f"{root}#jobs.{job_id}"
        ir["stages"].append(
            node(
                {
                    "id": job_id,
                    "name": job_id,
                    "kind": "gha-job",
                    "steps": list(job["steps"]),
                    "needs": list(job.get("needs") or []),
                    "if": job.get("if"),
                    "continue_on_error": bool(job.get("continue_on_error")),
                    "required": bool(job.get("required")),
                    "fail_fast_job": bool(job.get("fail_fast_job")),
                },
                j_anchor,
            )
        )
        for need in job.get("needs") or []:
            ir["barriers"].append(
                node(
                    {
                        "id": f"needs-{job_id}-{need}",
                        "kind": "needs",
                        "src": need,
                        "dst": job_id,
                    },
                    f"{j_anchor}#needs:{need}",
                )
            )
        for combo in expansions:
            ir["expanded_jobs"].append(
                {"job_id": job_id, "matrix": combo, "steps": list(job["steps"])}
            )
    ir["stopping"] = node(
        {"expression": "fail-fast-first-failing-required-step"},
        f"{root}#stopping",
    )
    return ir


def gha_from_ir(ir: IR) -> Native:
    jobs = {}
    for st in ir["stages"]:
        jobs[st["id"]] = {
            "steps": list(st["steps"]),
            "needs": list(st.get("needs") or []),
            "if": st.get("if"),
            "continue_on_error": bool(st.get("continue_on_error")),
            "required": bool(st.get("required")),
            "fail_fast_job": bool(st.get("fail_fast_job")),
        }
    return {
        "id": ir["id"],
        "name": ir["name"],
        "jobs": jobs,
        "matrix": ir.get("matrix"),
        "required_contexts": list(ir.get("required_contexts") or []),
        "expanded_job_count": len(ir.get("expanded_jobs") or []),
    }


def paper_to_ir(native: Native) -> IR:
    aid = native["id"]
    root = f"paper-protocol:{aid}"
    ir = empty_ir(adapter_id="paper-protocol", native_id=aid, source_anchor=root)
    ir["title"] = native["title"]
    ir["extractable"] = bool(native["extractable"])
    if not native["extractable"]:
        ir["verdict"] = native.get("verdict", "UNDERSPECIFIED")
        ir["missing_parameters"] = list(native.get("missing_parameters") or [])
        ir["stopping"] = node({"expression": "UNDERSPECIFIED"}, f"{root}#stopping")
        return ir
    quotes = native["quotes"]
    ir["participants"] = node(
        {"count": native["participants"], "quote": quotes["participants"]},
        f"{root}#participants",
    )
    ir["stages"].append(
        node(
            {
                "id": "turn-structure",
                "name": "turn-structure",
                "kind": "turn-structure",
                "body": native["turn_structure"],
                "quote": quotes["turn_structure"],
            },
            f"{root}#turn_structure",
        )
    )
    ir["stopping"] = node(
        {"expression": native["stopping"], "quote": quotes["stopping"]},
        f"{root}#stopping",
    )
    ir["scoring"] = node(
        {"expression": native["scoring"], "quote": quotes["scoring"]},
        f"{root}#scoring",
    )
    return ir


def paper_from_ir(ir: IR) -> Native:
    if not ir.get("extractable"):
        return {
            "id": ir["id"],
            "title": ir["title"],
            "extractable": False,
            "verdict": ir.get("verdict", "UNDERSPECIFIED"),
            "missing_parameters": list(ir.get("missing_parameters") or []),
            "quotes": {},
        }
    turns = ir["stages"][0]
    return {
        "id": ir["id"],
        "title": ir["title"],
        "extractable": True,
        "participants": ir["participants"]["count"],
        "turn_structure": turns["body"],
        "stopping": ir["stopping"]["expression"],
        "scoring": ir["scoring"]["expression"],
        "quotes": {
            "participants": ir["participants"]["quote"],
            "turn_structure": turns["quote"],
            "stopping": ir["stopping"]["quote"],
            "scoring": ir["scoring"]["quote"],
        },
    }


ADAPTERS: dict[str, Adapter] = {
    "saved-workflow": Adapter(
        adapter_id="saved-workflow",
        unit_id="WFA-0045",
        carried_fields=(
            "id",
            "filename",
            "phases",
            "tool_policy",
            "stopping",
            "background",
        ),
        lossy_fields=("comments", "date_now_construct", "args_as_string"),
        to_ir=saved_to_ir,
        from_ir=saved_from_ir,
        plant=("stages", 0, "name"),
    ),
    "metaswarm": Adapter(
        adapter_id="metaswarm",
        unit_id="WFA-0046",
        carried_fields=(
            "id",
            "phases",
            "coverage_enforcement",
            "knowledge_capture_before_pr",
            "vendor_runtime_import",
        ),
        lossy_fields=("prose_rationale",),
        to_ir=metaswarm_to_ir,
        from_ir=metaswarm_from_ir,
        plant=("gates", 0, "blocking"),
    ),
    "skill-markdown": Adapter(
        adapter_id="skill-markdown",
        unit_id="WFA-0047",
        carried_fields=(
            "id",
            "extractable",
            "frontmatter_description",
            "stages",
            "verdict",
            "reason",
        ),
        lossy_fields=("unstructured_aside",),
        to_ir=skill_to_ir,
        from_ir=skill_from_ir,
        plant=("stages", 0, "name"),
    ),
    "slash-command": Adapter(
        adapter_id="slash-command",
        unit_id="WFA-0048",
        carried_fields=("id", "kind", "target_skill", "stages"),
        lossy_fields=("help_blurb",),
        to_ir=slash_to_ir,
        from_ir=slash_from_ir,
        plant=("kind",),
    ),
    "langgraph": Adapter(
        adapter_id="langgraph",
        unit_id="WFA-0049",
        carried_fields=(
            "id",
            "nodes",
            "edges",
            "conditionals",
            "interrupt_before",
            "checkpointer",
            "reducer_names",
        ),
        lossy_fields=("reducer_callables",),
        to_ir=langgraph_to_ir,
        from_ir=langgraph_from_ir,
        plant=("checkpoints", 0, "before")
        if False
        else ("stages", 0, "name"),
    ),
    "crew-autogen": Adapter(
        adapter_id="crew-autogen",
        unit_id="WFA-0050",
        carried_fields=("id", "kind", "roles", "tasks", "process", "termination"),
        lossy_fields=("live_turn_loop",),
        to_ir=crew_to_ir,
        from_ir=crew_from_ir,
        plant=("stopping", "expression"),
    ),
    "dag-scheduler": Adapter(
        adapter_id="dag-scheduler",
        unit_id="WFA-0051",
        carried_fields=(
            "id",
            "framework",
            "tasks",
            "sensors",
            "replay_deterministic",
        ),
        lossy_fields=("durable_event_log",),
        to_ir=dag_to_ir,
        from_ir=dag_from_ir,
        plant=("stages", 0, "retries"),
    ),
    "github-actions": Adapter(
        adapter_id="github-actions",
        unit_id="WFA-0052",
        carried_fields=(
            "id",
            "name",
            "jobs",
            "matrix",
            "required_contexts",
        ),
        lossy_fields=("secret_values",),
        to_ir=gha_to_ir,
        from_ir=gha_from_ir,
        plant=("stages", 0, "fail_fast_job"),
    ),
    "paper-protocol": Adapter(
        adapter_id="paper-protocol",
        unit_id="WFA-0053",
        carried_fields=(
            "id",
            "title",
            "extractable",
            "participants",
            "turn_structure",
            "stopping",
            "scoring",
            "quotes",
            "verdict",
            "missing_parameters",
        ),
        lossy_fields=("inferred_defaults", "prose"),
        to_ir=paper_to_ir,
        from_ir=paper_from_ir,
        plant=("participants", "count"),
    ),
}


def all_adapters() -> list[Adapter]:
    return list(ADAPTERS.values())
