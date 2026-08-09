"""Probe: enumerate the councilspec schema surface a preset author must respect.

Prints, for every path in the schema: required keys, additionalProperties posture,
and every enum/pattern constraint. Used to author presets 17-32 without guessing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "platform" / "schema" / "councilspec.schema.json"


def walk(node, path, out, defs):
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        ref = node["$ref"]
        out.append((path, "REF", ref))
        return
    for kw in ("allOf", "anyOf", "oneOf"):
        if kw in node:
            for i, sub in enumerate(node[kw]):
                walk(sub, f"{path}.{kw}[{i}]", out, defs)
    if "enum" in node:
        out.append((path, "enum", node["enum"]))
    if "pattern" in node:
        out.append((path, "pattern", node["pattern"]))
    if "const" in node:
        out.append((path, "const", node["const"]))
    if "required" in node:
        out.append((path, "required", node["required"]))
    if node.get("additionalProperties") is False:
        out.append((path, "closed", True))
    if "properties" in node:
        out.append((path, "props", sorted(node["properties"].keys())))
        for k, v in node["properties"].items():
            walk(v, f"{path}.{k}", out, defs)
    if "items" in node:
        walk(node["items"], f"{path}[]", out, defs)
    if "$defs" in node:
        for k, v in node["$defs"].items():
            walk(v, f"$defs.{k}", out, defs)


def main() -> int:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    out: list = []
    walk(schema, "$", out, schema.get("$defs", {}))
    want = sys.argv[1] if len(sys.argv) > 1 else None
    for path, kind, val in out:
        if want and want not in path:
            continue
        s = json.dumps(val)
        if len(s) > 900:
            s = s[:900] + " ...TRUNC"
        print(f"{path:70s} {kind:9s} {s}")
    print(f"-- {len(out)} constraint records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
