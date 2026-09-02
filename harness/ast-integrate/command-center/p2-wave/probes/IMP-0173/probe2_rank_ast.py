#!/usr/bin/env python3
"""Probe 2: ranking function does not read repetition count (AST + param assertion).

Catalog tests_required[1] / evidence_requirement (2): rank is computed from
independent evidence and decision impact, NOT from how many sources repeated
the idea. Assert the count field is absent from the ranking function's inputs.

Independent of probe1 (reconstruction). Also a both-states control: a mutant
ranking function that takes `count` must be flagged.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collapse as C  # noqa: E402

SRC = HERE / "collapse.py"
MUTANT_TAKES_COUNT = """
def rank_row(independent_evidence, decision_impact, count):
    return float(count) * 10.0 + float(independent_evidence)
"""
MUTANT_READS_COUNT_KEY = """
def rank_row(independent_evidence, decision_impact, row):
    return float(row["repetition_count"]) + float(independent_evidence)
"""


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0173-probe2 {msg}")
    return 1


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def ranking_def(tree: ast.AST, name: str = "rank_row") -> ast.FunctionDef | None:
    for node in tree.body if isinstance(tree, ast.Module) else ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def param_names(fn: ast.FunctionDef) -> list[str]:
    args = list(fn.args.posonlyargs) + list(fn.args.args) + list(fn.args.kwonlyargs)
    names = [a.arg for a in args]
    if fn.args.vararg:
        names.append(fn.args.vararg.arg)
    if fn.args.kwarg:
        names.append(fn.args.kwarg.arg)
    return names


def body_reads_forbidden(fn: ast.FunctionDef, forbidden: frozenset[str]) -> list[str]:
    hits: list[str] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id in forbidden:
            hits.append(f"name:{node.id}")
        if isinstance(node, ast.Attribute) and node.attr in forbidden:
            hits.append(f"attr:{node.attr}")
        if isinstance(node, ast.Subscript):
            sl = node.slice
            key = _const_str(sl)
            index_ty = getattr(ast, "Index", None)
            if key is None and index_ty is not None and isinstance(sl, index_ty):
                key = _const_str(sl.value)
            if key in forbidden:
                hits.append(f"key:{key}")
    return hits


def inspect_rank_function(source: str, *, name: str = "rank_row") -> dict:
    tree = ast.parse(source)
    fn = ranking_def(tree, name)
    if fn is None:
        return {"found": False, "forbidden_params": [], "forbidden_body": [], "params": []}
    params = param_names(fn)
    forbidden = C.FORBIDDEN_RANK_INPUTS
    return {
        "found": True,
        "params": params,
        "forbidden_params": [p for p in params if p in forbidden],
        "forbidden_body": body_reads_forbidden(fn, forbidden),
    }


def calls_rank_row_without_count(tree: ast.AST) -> dict:
    calls = 0
    bad_kwargs: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        called = None
        if isinstance(fn, ast.Name) and fn.id == "rank_row":
            called = "rank_row"
        elif isinstance(fn, ast.Attribute) and fn.attr == "rank_row":
            called = "rank_row"
        if called is None:
            continue
        calls += 1
        for kw in node.keywords:
            if kw.arg in C.FORBIDDEN_RANK_INPUTS:
                bad_kwargs.append(kw.arg or "")
    return {"calls": calls, "bad_kwargs": bad_kwargs}


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    live = inspect_rank_function(src)
    tree = ast.parse(src)
    calls = calls_rank_row_without_count(tree)
    sig = inspect.signature(C.rank_row)
    sig_names = list(sig.parameters)

    mutant_param = inspect_rank_function(MUTANT_TAKES_COUNT)
    mutant_key = inspect_rank_function(MUTANT_READS_COUNT_KEY)

    report = {
        "live": live,
        "signature": sig_names,
        "calls": calls,
        "mutant_takes_count": mutant_param,
        "mutant_reads_key": mutant_key,
    }
    print(json.dumps(report, sort_keys=True))

    if not live["found"]:
        return fail("rank_row-missing")
    if live["forbidden_params"]:
        return fail(f"rank_row-params-include-count {live['forbidden_params']}")
    if live["forbidden_body"]:
        return fail(f"rank_row-body-reads-count {live['forbidden_body']}")
    if any(p in C.FORBIDDEN_RANK_INPUTS for p in sig_names):
        return fail(f"inspect.signature-includes-count {sig_names}")
    required = {"independent_evidence", "decision_impact"}
    if not required.issubset(set(live["params"])):
        return fail(f"rank_row-missing-required-inputs {live['params']}")
    if calls["calls"] < 1:
        return fail("collapse-never-calls-rank_row")
    if calls["bad_kwargs"]:
        return fail(f"rank_row-called-with-count-kw {calls['bad_kwargs']}")

    # Both-states: detector must fire on the known-broken mutants.
    if not mutant_param["forbidden_params"]:
        return fail("detector-silent-on-count-parameter-mutant")
    if not mutant_key["forbidden_body"]:
        return fail("detector-silent-on-repetition_count-subscript-mutant")

    # Adversarial: raising repetition_count must not change rank_row's output.
    base = C.rank_row(independent_evidence=0.91, decision_impact=0.8, cross_domain=0.4)
    # There is no count argument to vary; the live collapse of C-A2 (count=99)
    # must still lose to C-A1 (count=1).
    candidates = C.load_candidates(HERE / "fixtures" / "candidates.json")
    graph = C.collapse_duplicates(candidates)
    a1 = next(r for r in graph["rows"] if r["id"] == "C-A1")
    a2 = next(r for r in graph["rows"] if r["id"] == "C-A2")
    if a2["rank"] >= a1["rank"]:
        return fail("echo-count-raised-rank")
    if a1["canonical_id"] != "C-A1" or a2["canonical_id"] != "C-A1":
        return fail("repetition-won-canonical")
    if a1["rank"] != base:
        return fail("fixture-A1-rank-mismatch")

    # Clone C-A1 ten times with soaring repetition_count; winner rank stays base.
    clones = []
    for i in range(10):
        row = json.loads(json.dumps(candidates[0]))
        row["id"] = f"C-ECHO-{i}"
        row["repetition_count"] = 1000 + i
        row["independent_evidence"] = 0.05
        row["decision_impact"] = 0.05
        clones.append(row)
    g2 = C.collapse_duplicates(candidates + clones)
    winner = next(r for r in g2["rows"] if r["id"] == "C-A1")
    if winner["rank"] != base:
        return fail("N-echoes-changed-canonical-rank")
    echoes_aliased = [
        r for r in g2["rows"] if r["id"].startswith("C-ECHO-") and r["status"] == "aliased"
    ]
    if len(echoes_aliased) != 10:
        return fail(f"echo-clones-not-aliased n={len(echoes_aliased)}")

    print(
        "rank_inputs="
        + ",".join(sig_names)
        + f" calls={calls['calls']} mutant_param_hits={mutant_param['forbidden_params']}"
        + f" mutant_key_hits={mutant_key['forbidden_body']}"
    )
    print("SUCCESS:IMP-0173-probe2 ranking AST/param assertion: count absent from inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
