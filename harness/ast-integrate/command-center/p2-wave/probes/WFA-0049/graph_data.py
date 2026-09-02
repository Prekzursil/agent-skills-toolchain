"""Load the worked graph fixture and published quotes."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
GRAPH_PATH = HERE / "fixtures" / "worked-graph.json"
QUOTES_PATH = HERE / "fixtures" / "published-quotes.json"

START = "__start__"
END = "__end__"


def load_graph() -> dict:
    return json.loads(GRAPH_PATH.read_text(encoding="utf-8"))


def load_quotes() -> dict:
    return json.loads(QUOTES_PATH.read_text(encoding="utf-8"))


def node_by_id(graph: dict, nid: str) -> dict:
    for n in graph["nodes"]:
        if n["id"] == nid:
            return n
    raise KeyError(nid)


def route_key(state: dict, predicate_id: str) -> str:
    if predicate_id != "topic_contains_urgent":
        raise ValueError(f"unnamed predicate {predicate_id} is not in the named catalog")
    topic = str(state.get("topic") or "")
    return "urgent" if "urgent" in topic.lower() else "normal"
