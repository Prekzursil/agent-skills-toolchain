"""A11 dissent-survival trace: every minority id must be reachable from the parent."""
from __future__ import annotations

from typing import Any, Mapping

A11_KIND = "a11.dissent-survival-trace.v1"


def reachable_ids(doc: Any) -> set[str]:
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            ident = node.get("id")
            if ident:
                found.add(str(ident))
            payload = node.get("payload")
            if isinstance(payload, Mapping) and payload.get("id"):
                found.add(str(payload["id"]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return found


def a11_rows(doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, Mapping):
            if node.get("kind") == A11_KIND:
                rows.append(dict(node))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    return rows
