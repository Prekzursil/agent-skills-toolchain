"""Dump the CouncilSpec schema surface: every property path, type, enum, required flag.

Read-only probe. Used to author protocol instances against the real contract instead of
guessing field names. Run from the repo root.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "platform" / "schema" / "councilspec.schema.json"


def resolve(node: dict, defs: dict) -> dict:
    seen = 0
    while "$ref" in node and seen < 10:
        ref = node["$ref"]
        key = ref.split("/")[-1]
        if key not in defs:  # self-ref "#" or an unknown target: stop unrolling
            return {"type": f"<recursive-ref {ref}>"}
        node = defs[key]
        seen += 1
    return node


def walk(node: dict, defs: dict, path: str, out: list, depth: int = 0) -> None:
    if depth > 7:
        return
    node = resolve(node, defs)
    for combo in ("oneOf", "anyOf", "allOf"):
        if combo in node:
            for i, sub in enumerate(node[combo]):
                walk(sub, defs, f"{path}[{combo}{i}]", out, depth + 1)
    if "enum" in node:
        out.append((path, "enum", node["enum"]))
    elif node.get("type") == "object" or "properties" in node:
        req = node.get("required", [])
        addl = node.get("additionalProperties", None)
        out.append((path, "object", {"required": req, "additionalProperties": addl}))
        for name, sub in (node.get("properties") or {}).items():
            walk(sub, defs, f"{path}.{name}", out, depth + 1)
    elif node.get("type") == "array":
        items = node.get("items")
        out.append(
            (
                path,
                "array",
                {
                    "minItems": node.get("minItems"),
                    "maxItems": node.get("maxItems"),
                    "uniqueItems": node.get("uniqueItems"),
                },
            )
        )
        if isinstance(items, dict):
            walk(items, defs, f"{path}[]", out, depth + 1)
    else:
        out.append(
            (
                path,
                node.get("type", "?"),
                {
                    k: v
                    for k, v in node.items()
                    if k
                    in ("minimum", "maximum", "pattern", "const", "minLength", "format")
                },
            )
        )


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    defs = schema.get("$defs", {})
    out: list = []
    walk(schema, defs, "$", out)
    for path, kind, extra in out:
        print(f"{path}\t{kind}\t{json.dumps(extra, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
