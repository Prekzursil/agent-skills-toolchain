"""Capability-map coverage checker.

Answers one question mechanically: for each capability the spec requires of the DSL, does a
JSON Pointer resolve in the schema, does a pointer resolve to non-empty content in a
document that actually VALIDATES, and is at least one mutation registered that proves the
constraint is enforced? Anything short of all three is reported as a named gap.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import mutations as _mutations
from . import schemas

EXAMPLES_DIR = Path(__file__).resolve().parent / "examples"


class PointerError(LookupError):
    """A JSON Pointer did not resolve."""


def resolve_pointer(doc: Any, pointer: str) -> Any:
    """Minimal RFC 6901 pointer resolution (no external dependency)."""
    if pointer in ("", "/"):
        return doc
    if not pointer.startswith("/"):
        raise PointerError(f"pointer must start with '/': {pointer!r}")
    cur = doc
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if token not in cur:
                raise PointerError(f"key {token!r} missing while resolving {pointer!r}")
            cur = cur[token]
        elif isinstance(cur, list):
            if not token.lstrip("-").isdigit():
                raise PointerError(
                    f"array index expected, got {token!r} in {pointer!r}"
                )
            idx = int(token)
            if idx >= len(cur):
                raise PointerError(
                    f"index {idx} out of range while resolving {pointer!r}"
                )
            cur = cur[idx]
        else:
            raise PointerError(
                f"cannot descend into {type(cur).__name__} at {token!r} in {pointer!r}"
            )
    return cur


def load_capability_map() -> dict[str, Any]:
    return json.loads(schemas.CAPABILITY_MAP_PATH.read_text(encoding="utf-8"))


def check_coverage() -> dict[str, Any]:
    """Verify every capability's schema pointer, example pointer and mutation coverage."""
    cmap = load_capability_map()
    dsl_schema = schemas.load_all()[schemas.WORKFLOW_ID]
    wf_validator = schemas.workflow_validator()

    example_cache: dict[str, Any] = {}
    example_valid: dict[str, list[str]] = {}

    rows: list[dict[str, Any]] = []
    for cap in cmap["capabilities"]:
        row: dict[str, Any] = {
            "id": cap["id"],
            "mandated": bool(cap.get("mandated")),
            "schema_pointer": cap["schema_pointer"],
            "example": cap["example"],
            "example_pointer": cap["example_pointer"],
            "mutations": cap.get("mutations", []),
            "gaps": [],
        }

        try:
            node = resolve_pointer(dsl_schema, cap["schema_pointer"])
            if not node:
                row["gaps"].append("schema pointer resolves to an empty value")
        except PointerError as exc:
            row["gaps"].append(f"schema pointer unresolved: {exc}")

        name = cap["example"]
        if name not in example_cache:
            path = EXAMPLES_DIR / name
            if not path.is_file():
                example_cache[name] = None
                example_valid[name] = [f"example file missing: {path}"]
            else:
                doc = json.loads(path.read_text(encoding="utf-8"))
                example_cache[name] = doc
                example_valid[name] = schemas.error_summary(
                    wf_validator.iter_errors(doc)
                )
        doc = example_cache[name]
        if doc is None:
            row["gaps"].append(f"example {name} missing")
        else:
            if example_valid[name]:
                row["gaps"].append(
                    f"example {name} does not validate: {example_valid[name][0]}"
                )
            try:
                value = resolve_pointer(doc, cap["example_pointer"])
                if value in (None, {}, [], ""):
                    row["gaps"].append("example pointer resolves to an empty value")
            except PointerError as exc:
                row["gaps"].append(f"example pointer unresolved: {exc}")

        unknown = [m for m in row["mutations"] if m not in _mutations.MUTATION_IDS]
        if unknown:
            row["gaps"].append(f"unregistered mutation id(s): {unknown}")
        if not row["mutations"]:
            row["gaps"].append("no mutation registered - capability is UNPROVEN")

        row["covered"] = not row["gaps"]
        rows.append(row)

    mandated = [r for r in rows if r["mandated"]]
    return {
        "capability_map": str(schemas.CAPABILITY_MAP_PATH),
        "capabilities": len(rows),
        "mandated": len(mandated),
        "mandated_covered": sum(1 for r in mandated if r["covered"]),
        "all_covered": sum(1 for r in rows if r["covered"]),
        "uncovered": [
            {"id": r["id"], "gaps": r["gaps"]} for r in rows if not r["covered"]
        ],
        "rows": rows,
    }
