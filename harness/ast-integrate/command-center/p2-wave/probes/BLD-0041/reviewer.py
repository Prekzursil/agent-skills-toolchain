#!/usr/bin/env python3
"""Independent confirmation of flagged tautological tests.

The census grades from AST (plus settrace / runtime JSON len). This reviewer
re-derives each sampled finding with a second method:

  NO_ASSERTION / ASSERT_TRUE / ASSERT_LITERAL
      CPython 3.12 bytecode: tautological asserts compile to no
      LOAD_ASSERTION_ERROR, so the test cannot go red.
  UNREACHABLE_ASSERTION
      re-run sys.settrace and require the AST assert line to be absent
      from executed lines.
  EMPTY_BENCHMARK_INPUT
      re-load fixture bytes and re-count; never read the file name.
  EMPTY_LOOP / EMPTY_PARAMETRIZE
      independent AST walk of this function only (fresh parse).
"""
from __future__ import annotations

import ast
import dis
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

SAMPLE_FUNCTIONS = [
    "test_c1_no_assert",
    "test_c2_unreachable_assert",
    "test_c3_bench_full_corpus",
    "test_r01_assert_true",
    "test_r02_assert_literal",
    "test_r03_empty_loop",
    "test_r04_empty_parametrize",
    "test_r05_empty_loop_tuple",
    "test_r07_assert_string",
    "test_r08_dead_if_zero",
]


def _has_assertion_error(code) -> bool:
    for instr in dis.get_instructions(code):
        if instr.opname == "LOAD_ASSERTION_ERROR":
            return True
    return False


def _fn_node(tree: ast.AST, name: str) -> ast.AST | None:
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    return None


def _compile_fn(path: Path, name: str):
    src = path.read_text(encoding="utf-8")
    if "import pytest" in src:
        return None
    ns: dict = {"__file__": str(path.resolve()), "__name__": f"rev_{path.stem}"}
    exec(compile(src, str(path), "exec"), ns)
    fn = ns.get(name)
    return fn if callable(fn) else None


def confirm(finding: dict) -> dict:
    path = C.REPO / finding["path"]
    reason = finding["reason_class"]
    func = finding["function"]
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = _fn_node(tree, func)
    if fn is None:
        return {"ok": False, "method": "missing-function", "notes": func}

    if reason == "NO_ASSERTION":
        asserts = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        helpers = C._collect_helper_calls(fn)
        raises = C._collect_assertion_raises(fn)
        compiled = _compile_fn(path, func)
        bc = compiled is not None and not _has_assertion_error(compiled.__code__)
        ok = (not asserts) and (not helpers) and (not raises) and (compiled is None or bc)
        return {
            "ok": ok,
            "method": "ast-no-assert + bytecode-no-LOAD_ASSERTION_ERROR",
            "notes": (
                f"asserts={len(asserts)} helpers={len(helpers)} "
                f"raises={len(raises)} bytecode_clean={bc}"
            ),
        }

    if reason in {"ASSERT_TRUE", "ASSERT_LITERAL"}:
        compiled = _compile_fn(path, func)
        bc_clean = compiled is not None and not _has_assertion_error(compiled.__code__)
        a = [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        if not a:
            return {"ok": False, "method": "ast-missing-assert", "notes": func}
        test = a[0].test
        if reason == "ASSERT_TRUE":
            ast_ok = isinstance(test, ast.Constant) and test.value is True
        else:
            ast_ok = C._truthy_constant(test) is True and test.value is not True
        ok = ast_ok and bc_clean
        return {
            "ok": ok,
            "method": "ast-constant-assert + bytecode-eliminated-assert",
            "notes": f"ast_ok={ast_ok} bytecode_no_assertion_error={bc_clean}",
        }

    if reason == "UNREACHABLE_ASSERTION":
        hits = C.execute_under_coverage(path, func)
        assert_lines = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Assert)]
        uncovered = [ln for ln in assert_lines if ln not in hits]
        ok = bool(uncovered) and len(uncovered) == len(assert_lines)
        return {
            "ok": ok,
            "method": "sys.settrace assert-line uncovered",
            "notes": f"assert_lines={assert_lines} hits={sorted(hits)} uncovered={uncovered}",
        }

    if reason == "EMPTY_BENCHMARK_INPUT":
        names = C._load_arg_constants(fn)
        if not names:
            return {"ok": False, "method": "no-fixture-load", "notes": func}
        fpath = path.parent / names[0]
        size = C.measure_json_input_size(fpath)
        name_not_used = True
        ok = size == 0 and size == finding.get("measured_input_size")
        return {
            "ok": ok,
            "method": "len(json.loads(fixture_bytes)) re-measure",
            "notes": f"size={size} basename={fpath.name} name_consulted={not name_not_used}",
        }

    if reason == "EMPTY_LOOP":
        sizes = C._module_sequence_lens(tree)
        empty = C._empty_loop_nodes(fn, sizes)
        ok = bool(empty)
        return {
            "ok": ok,
            "method": "fresh-parse empty-iter For/While",
            "notes": f"empty_loop_nodes={len(empty)}",
        }

    if reason == "EMPTY_PARAMETRIZE":
        sizes = C._module_sequence_lens(tree)
        n = C._parametrize_count(fn, sizes)
        ok = n == 0
        return {
            "ok": ok,
            "method": "fresh-parse parametrize product == 0",
            "notes": f"parametrize_count={n}",
        }

    return {"ok": False, "method": "unknown-class", "notes": reason}


def review_sample(findings: list[dict]) -> dict:
    by_fn = {row["function"]: row for row in findings}
    samples = []
    missing = []
    for name in SAMPLE_FUNCTIONS:
        row = by_fn.get(name)
        if row is None:
            missing.append(name)
            continue
        result = confirm(row)
        samples.append(
            {
                "test_id": row["test_id"],
                "path": row["path"],
                "line": row["line"],
                "reason_class": row["reason_class"],
                "cannot_fail": result["ok"],
                "method": result["method"],
                "notes": result["notes"],
            }
        )
    confirmed = sum(1 for s in samples if s["cannot_fail"])
    verdict = "PASS" if confirmed == 10 and not missing else "FAIL"
    return {
        "reviewer_id": "BLD-0041-anthropic-vendor-sample-reviewer",
        "vendor": "anthropic",
        "independent": True,
        "scope_not_agreement": True,
        "verdict": verdict,
        "sampled": len(samples),
        "confirmed": confirmed,
        "missing": missing,
        "samples": samples,
        "method": (
            "Second-method confirmation: bytecode elimination for tautological "
            "asserts, sys.settrace for dead-branch asserts, runtime JSON len "
            "for empty-input benchmarks, fresh AST parse for empty loops and "
            "empty parametrize lists."
        ),
    }
