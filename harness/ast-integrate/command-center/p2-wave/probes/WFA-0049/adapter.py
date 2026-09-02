"""Translate a published LangGraph StateGraph description into estate IR.

This module is not an execution runtime. It emits data. WFA-0044's official
WorkflowIR artifact is absent on this tree; the dialect is the catalog IR
surface (stages, gates, human checkpoints, resume, lineage, source anchors)
plus a lossy-field ledger.
"""
from __future__ import annotations

from graph_data import END, START, load_graph, load_quotes

IR_VERSION = "estate-workflow-ir/v0-wfa0049"
KNOWN_NAMED_PREDICATES = frozenset({"topic_contains_urgent"})
MAPPED_REDUCERS = {
    "last_value": "overwrite",
    "operator.add": "concat",
}


def _anchor(quote_id: str, quotes: dict) -> dict:
    for q in quotes["quotes"]:
        if q["id"] == quote_id:
            return {
                "quote_id": quote_id,
                "url": q["url"],
                "anchor": q["anchor"],
                "snippet": q["quote"][:180],
            }
    raise KeyError(quote_id)


def translate(graph: dict | None = None) -> dict:
    graph = graph or load_graph()
    quotes = load_quotes()
    ledger: list[dict] = []
    construct_map: list[dict] = []
    channels: list[dict] = []

    for ch in graph["state_schema"]:
        red = ch["reducer"]
        mapped = MAPPED_REDUCERS.get(red)
        if mapped:
            channels.append(
                {
                    "key": ch["key"],
                    "merge": mapped,
                    "source_reducer": red,
                    "source_anchor": _anchor(
                        "default-reducer" if red == "last_value" else "operator-add",
                        quotes,
                    ),
                }
            )
            construct_map.append(
                {
                    "construct": f"state.{ch['key']}.reducer={red}",
                    "status": "MAPPED",
                    "ir_field": f"state_channels[{ch['key']}].merge={mapped}",
                }
            )
        else:
            ledger.append(
                {
                    "source_construct": f"state.{ch['key']}",
                    "source_reducer": red,
                    "ir_field": None,
                    "status": "NON-TRANSFERABLE",
                    "reason": (
                        "Arbitrary Python reducer is not an IR merge policy. "
                        "Only last_value (overwrite) and operator.add on lists "
                        "(concat) are named builtins. unique_append identity "
                        "semantics cannot be reproduced without executing the "
                        "callable (which would require importing or vendoring "
                        "the producing runtime)."
                    ),
                    "downstream": (
                        "IR execution ignores writes to this channel rather "
                        "than silently applying concat or last-write."
                    ),
                    "source_anchor": _anchor("reducer-binop", quotes),
                }
            )
            construct_map.append(
                {
                    "construct": f"state.{ch['key']}.reducer={red}",
                    "status": "NON-TRANSFERABLE",
                    "ir_field": "lossy_field_ledger",
                }
            )

    stages = []
    for n in graph["nodes"]:
        writes = {
            k: v
            for k, v in (n.get("writes") or {}).items()
            if any(c["key"] == k for c in channels)
        }
        dropped = sorted(
            k for k in (n.get("writes") or {}) if k not in writes
        )
        stages.append(
            {
                "id": n["id"],
                "kind": "stage",
                "writes": writes,
                "dropped_unmapped_writes": dropped,
                "source_anchor": {
                    "graph_id": graph["id"],
                    "node": n["id"],
                },
            }
        )
        construct_map.append(
            {
                "construct": f"node.{n['id']}",
                "status": "MAPPED",
                "ir_field": f"stages[{n['id']}]",
            }
        )

    edges = []
    for e in graph["edges"]:
        edges.append(
            {
                "from": e["from"],
                "to": e["to"],
                "kind": "fixed",
                "source_anchor": _anchor("pregel-superstep", quotes),
            }
        )
        construct_map.append(
            {
                "construct": f"edge.{e['from']}->{e['to']}",
                "status": "MAPPED",
                "ir_field": "edges[kind=fixed]",
            }
        )

    gates = []
    for ce in graph["conditional_edges"]:
        pred = ce["path"]
        if pred in KNOWN_NAMED_PREDICATES and isinstance(ce.get("path_map"), dict):
            gates.append(
                {
                    "after_stage": ce["source"],
                    "predicate_id": pred,
                    "path_map": dict(ce["path_map"]),
                    "source_anchor": _anchor("add-conditional-edges", quotes),
                }
            )
            construct_map.append(
                {
                    "construct": f"conditional_edges.{ce['source']}.{pred}",
                    "status": "MAPPED",
                    "ir_field": f"gates[after_stage={ce['source']}]",
                }
            )
        else:
            ledger.append(
                {
                    "source_construct": f"add_conditional_edges({ce['source']})",
                    "status": "NON-TRANSFERABLE",
                    "ir_field": None,
                    "reason": "Arbitrary path Callable without a named predicate + path_map cannot be expressed as IR.",
                    "source_anchor": _anchor("add-conditional-edges", quotes),
                }
            )
            construct_map.append(
                {
                    "construct": f"conditional_edges.{ce['source']}.{pred}",
                    "status": "NON-TRANSFERABLE",
                    "ir_field": "lossy_field_ledger",
                }
            )

    compile_spec = graph["compile"]
    human = []
    for nid in compile_spec.get("interrupt_before") or []:
        human.append(
            {
                "before_stage": nid,
                "kind": "interrupt_before",
                "source_anchor": _anchor("interrupt-before", quotes),
            }
        )
        construct_map.append(
            {
                "construct": f"compile.interrupt_before.{nid}",
                "status": "MAPPED",
                "ir_field": "human_checkpoints[kind=interrupt_before]",
            }
        )
    for nid in compile_spec.get("interrupt_after") or []:
        human.append(
            {
                "after_stage": nid,
                "kind": "interrupt_after",
                "source_anchor": _anchor("interrupt-before", quotes),
            }
        )
        construct_map.append(
            {
                "construct": f"compile.interrupt_after.{nid}",
                "status": "MAPPED",
                "ir_field": "human_checkpoints[kind=interrupt_after]",
            }
        )

    ckpt = compile_spec.get("checkpointer")
    construct_map.append(
        {
            "construct": "compile.checkpointer.mechanism",
            "status": "MAPPED",
            "ir_field": "resume.thread_checkpoint",
        }
    )
    construct_map.append(
        {
            "construct": f"compile.checkpointer.class={ckpt}",
            "status": "NON-TRANSFERABLE",
            "ir_field": "lossy_field_ledger",
        }
    )
    ledger.append(
        {
            "source_construct": f"checkpointer class {ckpt}",
            "status": "NON-TRANSFERABLE",
            "ir_field": "resume.thread_checkpoint",
            "reason": (
                "The InMemorySaver / PostgresSaver / SqliteSaver classes are "
                "LangGraph types. The transferable mechanism is thread_id plus "
                "a JSON snapshot of (state, pending stages). Importing the "
                "class would create a second control plane."
            ),
            "source_anchor": _anchor("compile-checkpointer", quotes),
        }
    )

    for extra in (
        {
            "source_construct": "interrupt() inside a node",
            "status": "NON-TRANSFERABLE",
            "reason": (
                "Dynamic interrupt() is not interrupt_before. On resume the "
                "node restarts from the beginning; estate IR human checkpoints "
                "are compile-time breakpoints that run the paused stage once."
            ),
            "source_anchor": _anchor("dynamic-interrupt-restart", quotes),
        },
        {
            "source_construct": "add_messages reducer",
            "status": "NON-TRANSFERABLE",
            "reason": "Requires LangChain Message objects and ID-aware merge; not an IR concat.",
            "source_anchor": _anchor("add-messages", quotes),
        },
        {
            "source_construct": "Pregel same-superstep parallel nodes",
            "status": "NON-TRANSFERABLE",
            "reason": (
                "Published Pregel semantics run parallel recipients in one "
                "super-step. This estate control plane walks stages sequentially. "
                "The worked graph is a line, so measured stage order still matches."
            ),
            "source_anchor": _anchor("pregel-superstep", quotes),
        },
        {
            "source_construct": "langgraph Store (cross-thread)",
            "status": "NON-TRANSFERABLE",
            "reason": "Long-term cross-thread memory is not thread-scoped resume.",
            "source_anchor": _anchor("compile-checkpointer", quotes),
        },
    ):
        extra.setdefault("ir_field", None)
        ledger.append(extra)
        construct_map.append(
            {
                "construct": extra["source_construct"],
                "status": "NON-TRANSFERABLE",
                "ir_field": "lossy_field_ledger",
            }
        )

    ir = {
        "ir_version": IR_VERSION,
        "id": graph["id"],
        "source_anchor": {
            "graph_id": graph["id"],
            "runtime_imported": False,
        },
        "entry": START,
        "exit": END,
        "state_channels": channels,
        "stages": stages,
        "edges": edges,
        "gates": gates,
        "human_checkpoints": human,
        "resume": {
            "mechanism": "thread_checkpoint",
            "thread_id_field": "thread_id",
            "source_anchor": _anchor("thread-id", quotes),
        },
        "stopping": {"on": "edge_to___end__", "source_anchor": _anchor("add-conditional-edges", quotes)},
        "lossy_field_ledger": ledger,
        "note": (
            "WFA-0044 WorkflowIR artifact is absent on this worktree. This dialect "
            "matches the catalog IR surface and is explicitly not a second LangGraph."
        ),
    }
    return {"ir": ir, "construct_map": construct_map, "lossy_field_ledger": ledger}
