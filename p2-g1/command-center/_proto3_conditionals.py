"""Print every if/then/else conditional in the CouncilSpec schema, with its JSON pointer.

Read-only diagnostic for authoring conformant instances.
"""

from __future__ import annotations

import json
from pathlib import Path

SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "platform"
    / "schema"
    / "councilspec.schema.json"
)


def walk(node, ptr="#"):
    if isinstance(node, dict):
        if "if" in node:
            print(f"--- {ptr}")
            print("    IF   " + json.dumps(node.get("if"), sort_keys=True))
            if "then" in node:
                print("    THEN " + json.dumps(node.get("then"), sort_keys=True))
            if "else" in node:
                print("    ELSE " + json.dumps(node.get("else"), sort_keys=True))
        for k, v in node.items():
            walk(v, f"{ptr}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{ptr}/{i}")


if __name__ == "__main__":
    walk(json.loads(SCHEMA.read_text(encoding="utf-8")))
