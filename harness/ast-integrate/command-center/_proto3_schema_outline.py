"""Emit a compact outline of the CouncilSpec schema: required keys, enums, nested shapes.

Read-only. Usage: python command-center/_proto3_schema_outline.py [--deep KEY]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "platform"
    / "schema"
    / "councilspec.schema.json"
)


def outline(node, name="<root>", depth=0, maxdepth=3, out=None):
    if out is None:
        out = []
    pad = "  " * depth
    if not isinstance(node, dict):
        return out
    kind = node.get("type")
    bits = []
    if kind:
        bits.append(f"type={kind}")
    if "enum" in node:
        bits.append("enum=" + json.dumps(node["enum"]))
    if "const" in node:
        bits.append("const=" + json.dumps(node["const"]))
    if "$ref" in node:
        bits.append("$ref=" + node["$ref"])
    if node.get("required"):
        bits.append("required=" + json.dumps(node["required"]))
    if node.get("additionalProperties") is False:
        bits.append("addl=FALSE")
    if node.get("unevaluatedProperties") is False:
        bits.append("uneval=FALSE")
    for k in ("minimum", "maximum", "minItems", "pattern", "format", "default"):
        if k in node:
            bits.append(f"{k}={json.dumps(node[k])}")
    for comb in ("oneOf", "anyOf", "allOf"):
        if comb in node:
            bits.append(f"{comb}[{len(node[comb])}]")
    out.append(f"{pad}{name}: " + " ".join(bits))
    if depth >= maxdepth:
        if isinstance(node.get("properties"), dict):
            out.append(f"{pad}  props: " + ", ".join(sorted(node["properties"])))
        return out
    props = node.get("properties")
    if isinstance(props, dict):
        for pk in props:
            outline(props[pk], pk, depth + 1, maxdepth, out)
    items = node.get("items")
    if isinstance(items, dict):
        outline(items, name + "[]", depth + 1, maxdepth, out)
    for comb in ("oneOf", "anyOf", "allOf"):
        for i, sub in enumerate(node.get(comb, [])):
            outline(sub, f"{name}.{comb}[{i}]", depth + 1, maxdepth, out)
    return out


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    args = sys.argv[1:]
    if args and args[0] == "--deep":
        key = args[1]
        depth = int(args[2]) if len(args) > 2 else 6
        node = (
            schema["$defs"][key]
            if key in schema.get("$defs", {})
            else schema["properties"][key]
        )
        print("\n".join(outline(node, key, 0, depth)))
        return 0
    if args and args[0] == "--defs":
        print("DEFS: " + ", ".join(sorted(schema.get("$defs", {}))))
        return 0
    print(f"$id={schema.get('$id')} title={schema.get('title')}")
    print("required=" + json.dumps(schema.get("required")))
    print("addl=" + json.dumps(schema.get("additionalProperties")))
    print("top-level props: " + ", ".join(schema["properties"]))
    print("\n".join(outline(schema, "<root>", 0, 2)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
