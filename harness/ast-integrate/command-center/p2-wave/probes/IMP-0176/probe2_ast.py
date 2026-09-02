#!/usr/bin/env python3
"""Probe 2: detection reads the predicate tree, not the prose (AST assertion).

Walks detect.py and trees.py. Fails if those modules subscript/get a prose
field, import keyword_control, or never mention the tree operators/fields.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

PROSE_KEYS = frozenset(
    {
        "description",
        "prose",
        "notes",
        "narrative",
        "title",
        "blurb",
        "summary",
        "text",
        "comment",
        "label",
        "body",
    }
)
REQUIRED_TREE_KEYS = frozenset(
    {"op", "axis", "symbol", "polarity", "children", "stop_tree", "tool_tree"}
)
DETECT_FILES = ("detect.py", "trees.py")


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0176-probe2 {msg}")
    return 1


def string_keys_from_ast(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Return (subscript_or_get_keys, all_string_constants)."""
    used: set[str] = set()
    constants: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            constants.add(node.value)
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                used.add(sl.value)
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if name == "get" and node.args:
                arg0 = node.args[0]
                if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                    used.add(arg0.value)
    return used, constants


def imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def main() -> int:
    used_all: set[str] = set()
    const_all: set[str] = set()
    imports_all: set[str] = set()
    for rel in DETECT_FILES:
        path = HERE / rel
        if not path.is_file():
            return fail(f"{rel} missing")
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        used, constants = string_keys_from_ast(tree)
        used_all |= used
        const_all |= constants
        imports_all |= imported_names(tree)
        print(f"ast {rel} keys={sorted(used)}")

    prose_hits = sorted(used_all & PROSE_KEYS)
    print(f"prose_key_reads={prose_hits}")
    if prose_hits:
        return fail(f"detector reads prose keys {prose_hits}")

    missing = sorted(REQUIRED_TREE_KEYS - used_all - const_all)
    print(f"tree_keys_present={sorted(REQUIRED_TREE_KEYS & (used_all | const_all))}")
    if missing:
        return fail(f"detector never names tree keys {missing}")

    if "keyword_control" in imports_all:
        return fail("detect.py/trees.py import the prose keyword control")
    if "re" in imports_all:
        return fail("detector imports re (keyword-matching hazard)")

    # Behavioral companion: swapping only description cannot be observed by
    # detect.detect_pair because those keys are not read. Confirmed by loading
    # two clones that differ only in description.
    sys.path.insert(0, str(HERE))
    import detect as D  # noqa: E402
    import json

    fixtures = json.loads((HERE / "fixtures" / "components.json").read_text(encoding="utf-8"))
    index = {c["id"]: c for c in fixtures["components"]}
    a = index["lookalike-prose-unanimity-egress"]
    b = index["lookalike-prose-forbid-airgap"]
    left = dict(a)
    left["description"] = "Requires unanimity and forbids air-gapped egress policy."
    right = dict(b)
    right["description"] = "Forbids unanimity; air-gapped; no egress."
    r1 = D.detect_pair(a, b)
    r2 = D.detect_pair(left, right)
    print(
        f"description_mutant same_verdict={r1['conflict'] == r2['conflict']} "
        f"conflict={r1['conflict']}"
    )
    if r1["conflict"] or r2["conflict"]:
        return fail("look-alike trees flagged after description-only mutation")
    if r1["stop"] != r2["stop"] or r1["tool"] != r2["tool"]:
        return fail("description-only mutation changed structural hits")

    print(
        "ast_no_prose_reads=True tree_fields_named=True "
        "no_regex=True description_mutant_silent=True"
    )
    print("SUCCESS:IMP-0176-probe2 AST assertion: trees, not prose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
