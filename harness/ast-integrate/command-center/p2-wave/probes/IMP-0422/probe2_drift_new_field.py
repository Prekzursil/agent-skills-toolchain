#!/usr/bin/env python3
"""Probe 2: drift — a new unit field neither adapter supports appears automatically.

No documentation file is edited. The register is a walk of unit.keys(), so an
unknown key leaks on both vendors. Both-states: the unmodified unit has no such
row; the mutated unit does.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ADAPTERS = REPO / "tools" / "work-unit-adapters"
sys.path.insert(0, str(ADAPTERS))

from dispatch import dispatch_same_unit, load_catalog_unit  # noqa: E402

NEW_FIELD = "brand_new_unsupported_knob"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0422-probe2 {msg}")
    return 1


def iterates_items(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "emit_leak_register":
            dumped = ast.dump(node)
            if "items" in dumped and "For" in dumped:
                return True
    return False


def main() -> int:
    if not iterates_items(ADAPTERS / "register.py"):
        return fail("emit_leak_register AST does not iterate unit items")

    live = load_catalog_unit("IMP-0422", REPO)
    good = dispatch_same_unit("IMP-0422", repo=REPO, unit=live)
    good_names = {row["field"] for row in good["fields"]}
    if NEW_FIELD in good_names:
        return fail("control unit already contains the planted field")

    mutant = dict(live)
    mutant[NEW_FIELD] = {"invented": True, "vendor": "neither"}
    bad = dispatch_same_unit("IMP-0422", repo=REPO, unit=mutant)
    by_field = {row["field"]: row for row in bad["fields"]}
    row = by_field.get(NEW_FIELD)
    if row is None:
        return fail("planted field missing from mutant register (doc-shaped closed list?)")
    if row["claude"]["status"] != "leaked":
        return fail(f"claude did not leak planted field: {row['claude']}")
    if row["codex"]["status"] != "leaked":
        return fail(f"codex did not leak planted field: {row['codex']}")
    if "emit_leak_register" not in row["claude"]["filled_by"]:
        return fail("claude planted row not adapter-filled")
    if "emit_leak_register" not in row["codex"]["filled_by"]:
        return fail("codex planted row not adapter-filled")

    # Documentation was not edited: schema/docs do not name the planted field.
    schema = (REPO / "command-center" / "schema" / "abstraction-leak.schema.json").read_text(
        encoding="utf-8"
    )
    if NEW_FIELD in schema:
        return fail("planted field was added to the schema (documentation edit)")

    payload = {
        "pass": True,
        "probe": "probe2-drift-new-field",
        "unit_id": "IMP-0422",
        "control_absent": True,
        "mutant_present": True,
        "claude_status": row["claude"]["status"],
        "codex_status": row["codex"]["status"],
        "no_schema_edit": True,
        "planted_field": NEW_FIELD,
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"control_absent=True mutant_leaked both adapters field={NEW_FIELD}")
    print("SUCCESS:IMP-0422-probe2 drift: new unsupported field appears without a doc edit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
