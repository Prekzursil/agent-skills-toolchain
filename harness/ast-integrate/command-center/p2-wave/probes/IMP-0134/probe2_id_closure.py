#!/usr/bin/env python3
"""Probe 2: AST-enumerated VIOLATION_* constants == documented set.

Computed set equality, not eyeballed. Planted undocumented id turns the
comparison red (detector control). Weakening the unknown-key check would
make probe 1 go red; here we prove the closure detector itself fires.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.validate import DOCUMENTED_VIOLATION_IDS  # noqa: E402

VALIDATE = REPO / "tools" / "agentspec" / "agentspec" / "validate.py"
REQUIRED = frozenset(
    {
        "param-missing-required",
        "param-type-mismatch",
        "param-out-of-enum",
        "param-unknown-key",
    }
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0134-probe2 {msg}")
    return 1


def ast_violation_constants(source: str) -> set[str]:
    tree = ast.parse(source)
    ids: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id.startswith("VIOLATION_"):
                ids.add(node.value.value)
    return ids


def ast_documented_literals(source: str) -> set[str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "DOCUMENTED_VIOLATION_IDS" not in names:
            continue
        call = node.value
        if isinstance(call, ast.Call) and call.args:
            arg = call.args[0]
            if isinstance(arg, ast.Set):
                out: set[str] = set()
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        out.add(elt.value)
                return out
    raise RuntimeError("DOCUMENTED_VIOLATION_IDS literal set not found")


def main() -> int:
    source = VALIDATE.read_text(encoding="utf-8")
    const_ids = ast_violation_constants(source)
    doc_ast = ast_documented_literals(source)
    doc_runtime = set(DOCUMENTED_VIOLATION_IDS)

    if const_ids != doc_ast:
        return fail(f"AST constants {sorted(const_ids)} != AST documented {sorted(doc_ast)}")
    if const_ids != doc_runtime:
        return fail(
            f"AST constants {sorted(const_ids)} != runtime documented {sorted(doc_runtime)}"
        )
    if not REQUIRED <= const_ids:
        return fail(f"missing required param ids: {sorted(REQUIRED - const_ids)}")
    if len(const_ids) != len(doc_runtime):
        return fail("cardinality mismatch")

    # Detector control: plant an undocumented constant; equality must break.
    planted = source.replace(
        'VIOLATION_PARAM_UNKNOWN_KEY = "param-unknown-key"',
        'VIOLATION_PARAM_UNKNOWN_KEY = "param-unknown-key"\n'
        'VIOLATION_PARAM_PLANTED = "param-planted-undocumented"',
        1,
    )
    if planted == source:
        return fail("could not plant undocumented id")
    planted_ids = ast_violation_constants(planted)
    if planted_ids == doc_runtime:
        return fail("planted undocumented id did not turn closure red")
    extra = planted_ids - doc_runtime
    if extra != {"param-planted-undocumented"}:
        return fail(f"unexpected planted delta {extra!r}")

    with tempfile.TemporaryDirectory(prefix="imp0134-p2-") as tmp:
        mutant = Path(tmp) / "validate_mutant.py"
        mutant.write_text(planted, encoding="utf-8")
        reparse = ast_violation_constants(mutant.read_text(encoding="utf-8"))
        if reparse == doc_runtime:
            return fail("mutant file still matched documented set")

    payload = {
        "probe": "probe2_id_closure",
        "ast_constants": sorted(const_ids),
        "documented_runtime": sorted(doc_runtime),
        "documented_ast": sorted(doc_ast),
        "equal": True,
        "planted_turns_red": True,
        "planted_extra": sorted(extra),
        "required_subset": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"closure equal={const_ids == doc_runtime} "
        f"n={len(const_ids)} planted_red=True"
    )
    print("SUCCESS:IMP-0134-probe2 AST id-constant closure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
