#!/usr/bin/env python3
"""Probe 2: collapsing attempt-limit and impossibility into one path goes red.

Live source must define and call two distinct emitters. A mutant that
makes both emitters return the same type fails the discrimination check.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "agentspec"
sys.path.insert(0, str(PKG))

from agentspec.repair_loop import (  # noqa: E402
    AttemptLimitTerminal,
    ProvedImpossibleTerminal,
    run_fixture,
)

UNIT = "IMP-0139"
SRC = PKG / "agentspec" / "repair_loop.py"
FIXTURES = HERE / "fixtures"

COLLAPSE_TAIL = '''

class CollapsedFail:
    record_type = "repair_failed"
    node_id = ""
    attempts_used = 0
    max_attempts = 0
    last_failure = "collapsed"
    exhausted = True
    proof = {}
    settling_experiment_id = ""


def emit_attempt_limit(node, attempts_used, last_failure):
    fail = CollapsedFail()
    fail.record_type = "repair_failed"
    return fail


def emit_proved_impossible(node, attempts_used, proof):
    fail = CollapsedFail()
    fail.record_type = "repair_failed"
    return fail
'''


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _fn_map(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _callees(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


def live_ast_ok(source: str) -> tuple[bool, str]:
    tree = ast.parse(source)
    fns = _fn_map(tree)
    need = ("emit_attempt_limit", "emit_proved_impossible", "run_repair_loop")
    missing = [n for n in need if n not in fns]
    if missing:
        return False, f"missing {missing}"
    if fns["emit_attempt_limit"] is fns["emit_proved_impossible"]:
        return False, "emitters are the same AST node"
    run_calls = _callees(fns["run_repair_loop"])
    if "emit_attempt_limit" not in run_calls:
        return False, "run_repair_loop does not call emit_attempt_limit"
    if "emit_proved_impossible" not in run_calls:
        return False, "run_repair_loop does not call emit_proved_impossible"
    shared = _callees(fns["emit_attempt_limit"]) & _callees(
        fns["emit_proved_impossible"]
    )
    # dataclass constructors are fine; a shared helper that both use is not
    banned = {n for n in shared if n.startswith("emit_") or n.startswith("_collapsed")}
    if banned:
        return False, f"emitters share helper {sorted(banned)}"
    return True, "distinct-emitters"


def discriminate(run) -> tuple[bool, str]:
    limited = run(_load("attempt_limit.json"))
    impossible = run(_load("impossibility.json"))
    if type(limited) is type(impossible):
        return False, f"same type {type(limited).__name__}"
    if not isinstance(limited, AttemptLimitTerminal):
        return False, f"limit type {type(limited).__name__}"
    if not isinstance(impossible, ProvedImpossibleTerminal):
        return False, f"impossible type {type(impossible).__name__}"
    if limited.record_type == impossible.record_type:
        return False, "record_type collided"
    return True, "discriminated"


def load_mutant(source: str):
    with tempfile.TemporaryDirectory(prefix="imp0139-mutant-") as tmp:
        path = Path(tmp) / "repair_loop_mutant.py"
        rewritten = (
            source.replace("from .impossibility", "from agentspec.impossibility")
            .replace("from .spec", "from agentspec.spec")
            + COLLAPSE_TAIL
        )
        path.write_text(rewritten, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("imp0139_mutant", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("mutant spec failed")
        # Mutant imports agentspec.impossibility / spec; PKG is already on path.
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod


def main() -> int:
    source = SRC.read_text(encoding="utf-8")
    ast_ok, ast_why = live_ast_ok(source)
    live_ok, live_why = discriminate(run_fixture)

    mutant = load_mutant(source)
    mutant_ok, mutant_why = True, "mutant-still-discriminates"
    try:
        m_ok, m_why = discriminate(mutant.run_fixture)
        mutant_ok, mutant_why = m_ok, m_why
    except Exception as exc:  # noqa: BLE001
        # A type-error from the collapsed emitter still counts as discrimination
        # going red, which is the required mutation outcome.
        mutant_ok, mutant_why = False, f"mutant-raised:{type(exc).__name__}"

    mutation_goes_red = ast_ok and live_ok and not mutant_ok
    report = {
        "probe": "probe2-mutation-discrimination",
        "unit_id": UNIT,
        "live_ast_ok": ast_ok,
        "live_ast_why": ast_why,
        "live_discriminated": live_ok,
        "live_why": live_why,
        "mutant_discriminated": mutant_ok,
        "mutant_why": mutant_why,
        "mutation_goes_red": mutation_goes_red,
        "pass": mutation_goes_red,
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    if not mutation_goes_red:
        print(f"FAILED:{UNIT}-probe2 mutation did not turn discrimination red")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe2 live emitters distinct; "
        "collapsed path fails discrimination"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
