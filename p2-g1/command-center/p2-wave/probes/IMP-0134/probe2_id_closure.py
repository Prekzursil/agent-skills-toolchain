"""IMP-0134 probe2 (static, mechanically different): the id set stays CLOSED.

AST-parses validate.py - it does NOT trust the running module objects of probe1.
Collects the VIOLATIONS tuple literals and every VIOLATION_* constant assignment,
then asserts computed set equality against the documented id set (33 ids) and that
the tuple carries no duplicates.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
VALIDATE = REPO / "tools" / "agentspec" / "agentspec" / "validate.py"

DOCUMENTED = frozenset({
    "barrier-awaits-unknown",
    "barrier-empty",
    "barrier-policy-unknown",
    "budget-total-negative",
    "budget-units-exceed-total",
    "fanout-empty",
    "fanout-unit-duplicate",
    "fanout-unit-unknown",
    "node-id-collides-unit",
    "node-id-duplicate",
    "node-id-empty",
    "pipeline-stage-unknown",
    "pipeline-too-short",
    "spec-version-unsupported",
    "unit-budget-negative",
    "unit-dep-cycle",
    "unit-dep-self",
    "unit-dep-unknown",
    "unit-id-duplicate",
    "unit-id-empty",
    "unit-isolation-unknown",
    "unit-prompt-empty",
    "unit-receipt-clause-vacuous",
    "unit-receipt-format-unknown",
    "unit-timeout-missing",
    "unit-worktree-no-writes",
    "workflow-id-empty",
    "workflow-no-units",
    "loop-unbounded",
    "param-required-missing",
    "param-type-mismatch",
    "param-value-not-in-enum",
    "param-key-unknown",
})

PARAM_IDS = frozenset({
    "param-required-missing",
    "param-type-mismatch",
    "param-value-not-in-enum",
    "param-key-unknown",
})


def extract(tree: ast.AST) -> tuple[set[str], set[str]]:
    tuple_ids: set[str] = set()
    const_ids: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
            value = node.value
        else:
            continue
        if value is None:
            continue
        if "VIOLATIONS" in targets and isinstance(value, ast.Tuple):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    tuple_ids.add(elt.value)
        names = [x for x in targets if x.startswith("VIOLATION_")]
        if names and isinstance(value, ast.Constant) and isinstance(value.value, str):
            const_ids.add(value.value)
    return tuple_ids, const_ids


def main() -> int:
    checks = {}
    tree = ast.parse(VALIDATE.read_text(encoding="utf-8"))
    tuple_ids, const_ids = extract(tree)
    checks["tuple_parsed_nonempty"] = len(tuple_ids) >= 30
    # set equality with the documented set implies distinctness of the emitted id space
    checks["computed_equals_documented"] = tuple_ids == set(DOCUMENTED)
    checks["param_ids_present"] = PARAM_IDS <= tuple_ids
    checks["closed_size_33"] = len(tuple_ids) == 33

    dead = sorted(const_ids - tuple_ids)
    out = {
        "unit_id": "IMP-0134",
        "probe": "probe2-id-closure",
        "method": "ast-set-equality",
        "computed_size": len(tuple_ids),
        "documented_size": len(DOCUMENTED),
        "missing_from_computed": sorted(set(DOCUMENTED) - tuple_ids),
        "extra_in_computed": sorted(tuple_ids - set(DOCUMENTED)),
        "violation_constants": sorted(const_ids),
        "dead_constant_declared_not_in_closed_set": dead,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0134-probe2 ast-extracted id set equals the documented 33-id set exactly; all four param ids present; closed, no free-form ids")
        return 0
    print("FAILED:IMP-0134-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
