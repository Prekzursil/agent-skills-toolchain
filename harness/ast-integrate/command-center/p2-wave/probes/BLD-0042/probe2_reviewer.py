#!/usr/bin/env python3
"""Probe 2: independent reviewer mutates two reported unexercised defaults."""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import census as C  # noqa: E402
import constants as K  # noqa: E402
from fixtures import planted_defaults as P  # noqa: E402

ART = REPO / K.OUT_REL
SRC = HERE / "fixtures" / "planted_defaults.py"


def rewrite_default(source: str, func_name: str, new_value: object) -> str:
    tree = ast.parse(source)

    class Rewriter(ast.NodeTransformer):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
            if node.name == func_name:
                if node.args.defaults:
                    node.args.defaults[-1] = ast.Constant(new_value)
            self.generic_visit(node)
            return node

    new_tree = Rewriter().visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


def exec_module(source: str, name: str) -> dict:
    ns: dict = {"__name__": name}
    exec(compile(source, name, "exec"), ns)  # noqa: S102 — scratch reviewer harness
    return ns


def main() -> int:
    if not ART.is_file():
        print("FAILED:BLD-0042-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if K.SENTINEL not in text:
        print("FAILED:BLD-0042-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:BLD-0042-probe2 self-declared {doc.get('state')}")
        return 1

    measured = C.run_census()
    planted = (measured.get("known") or {}).get("planted") or {}
    for needed in ("planted_never_omitted", "planted_empty_test_only", "planted_exercised"):
        row = planted.get(needed) or {}
        if needed != "planted_exercised" and row.get("classification") != "UNEXERCISED":
            print(f"FAILED:BLD-0042-probe2 {needed} not UNEXERCISED {row}")
            return 1
        if needed == "planted_exercised" and row.get("classification") != "EXERCISED":
            print(f"FAILED:BLD-0042-probe2 {needed} not EXERCISED {row}")
            return 1

    src = SRC.read_text(encoding="utf-8")
    mutated = rewrite_default(src, "planted_never_omitted", 100)
    mutated = rewrite_default(mutated, "planted_empty_test_only", 50)
    with tempfile.TemporaryDirectory(prefix="bld0042-rev-") as tmp:
        path = Path(tmp) / "planted_defaults.py"
        path.write_text(mutated + "\n", encoding="utf-8")
        ns = exec_module(mutated, "planted_mutated_unexercised")
        ns["run_planted_assertions"]()
        ns["run_empty_test_only"]()
    print("unexercised_mutation_stays_green=True funcs=['planted_never_omitted','planted_empty_test_only']")

    red_src = rewrite_default(src, "planted_exercised", P.PLANTED_EXERCISED_DEFAULT + 1)
    ns_red = exec_module(red_src, "planted_mutated_exercised")
    threw = False
    try:
        ns_red["run_planted_assertions"]()
    except AssertionError:
        threw = True
    if not threw:
        print("FAILED:BLD-0042-probe2 harness vacuous; exercised mutation stayed green")
        return 1
    print("exercised_mutation_turns_red=True harness_not_vacuous=True")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        print(f"FAILED:BLD-0042-probe2 receipt reviewer {reviewer}")
        return 1
    print("SUCCESS:BLD-0042-probe2 reviewer mutated two unexercised defaults; suite stayed green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
