"""Provenance-carry IR: every node kind requires a non-empty anchor and licence_class.

This is the WFA-0057 subset of the vendor-neutral workflow IR (WFA-0044 is not
on disk). It is a typed document, not an execution runtime: there is no
scheduler, no state store, and no entrypoint that runs a workflow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft7Validator

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "ir_schema.json"
NODE_SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
NODE_VALIDATOR = Draft7Validator(NODE_SCHEMA)

NODE_KINDS: tuple[str, ...] = tuple(NODE_SCHEMA["properties"]["kind"]["enum"])

LICENCE_RANK: dict[str, int] = {
    "public-domain": 0,
    "cc0": 0,
    "mit": 1,
    "bsd-2": 1,
    "bsd-3": 2,
    "apache-2.0": 2,
    "mpl-2.0": 3,
    "lgpl-2.1": 4,
    "gpl-3.0": 5,
    "agpl-3.0": 6,
    "proprietary": 7,
}


class ProvenanceError(ValueError):
    def __init__(self, code: str, message: str, **ctx: Any) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.ctx = ctx


def _field_code(node: dict[str, Any], field: str) -> str | None:
    if field not in node:
        return f"{field}-missing"
    val = node[field]
    if not isinstance(val, str):
        return f"{field}-not-string"
    if val == "" or not val.strip():
        return f"{field}-empty"
    return None


def classify_node(node: dict[str, Any]) -> list[str]:
    """Return hard-reject codes. Missing and empty are both hard rejects."""
    codes: list[str] = []
    if not isinstance(node, dict):
        return ["node-not-object"]
    kind = node.get("kind")
    if kind not in NODE_KINDS:
        codes.append("kind-unknown" if kind is not None else "kind-missing")
    for field in ("id", "anchor", "licence_class"):
        code = _field_code(node, field)
        if code:
            codes.append(code)
    return codes


def schema_errors(node: dict[str, Any]) -> list[str]:
    """JSON-Schema 2020-adjacent (draft-07) messages. Empty list = schema-valid."""
    return [err.message for err in NODE_VALIDATOR.iter_errors(node)]


def schema_rejects(node: dict[str, Any]) -> bool:
    return bool(schema_errors(node)) or bool(classify_node(node))


def make_node(
    kind: str,
    node_id: str,
    anchor: str,
    licence_class: str,
    **extra: Any,
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "kind": kind,
        "id": node_id,
        "anchor": anchor,
        "licence_class": licence_class,
    }
    node.update(extra)
    codes = classify_node(node)
    if codes:
        raise ProvenanceError(codes[0], "; ".join(codes), node_id=node_id, kind=kind)
    if schema_errors(node):
        raise ProvenanceError(
            "schema-invalid",
            "; ".join(schema_errors(node)),
            node_id=node_id,
            kind=kind,
        )
    return node


def most_restrictive(classes: Iterable[str]) -> str:
    items = [c.strip() for c in classes if isinstance(c, str) and c.strip()]
    if not items:
        raise ProvenanceError("licence-missing", "no licence classes to combine")
    unknown = sorted({c for c in items if c not in LICENCE_RANK})
    if unknown:
        raise ProvenanceError(
            "licence-unclassified",
            "unclassified licence class cannot default: " + ",".join(unknown),
            unknown=unknown,
        )
    return max(items, key=lambda c: LICENCE_RANK[c])


def iter_candidate_nodes(obj: Any) -> Iterable[dict[str, Any]]:
    """Walk nested dict/list; yield dicts that look like IR nodes (have kind+id)."""
    if isinstance(obj, dict):
        if "kind" in obj and "id" in obj:
            yield obj
        for value in obj.values():
            yield from iter_candidate_nodes(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_candidate_nodes(item)


def ir_nodes(obj: Any) -> list[dict[str, Any]]:
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for node in iter_candidate_nodes(obj):
        if node.get("kind") not in NODE_KINDS:
            continue
        marker = id(node)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(node)
    return out
