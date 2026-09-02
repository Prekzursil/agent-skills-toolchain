#!/usr/bin/env python3
"""AST tautological-test census for BLD-0041.

Retry policy of the unit: regex first is a known miss (comments, strings,
`assert True` inside a docstring). This module inspects assert nodes via
ast, then:
  * treats `raise AssertionError` as a real oracle (not NO_ASSERTION)
  * executes simple tests under sys.settrace for unreachable-assert coverage
  * measures JSON fixture cardinality at runtime for the empty-input class
    (never by reading the fixture file name)
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLANTED = HERE / "fixtures" / "scratch"
PROBE_TREE = (REPO / "command-center" / "p2-wave" / "probes").resolve()

SKIP_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "node_modules",
    "_deps",
}

REASON_ORDER = (
    "EMPTY_PARAMETRIZE",
    "EMPTY_BENCHMARK_INPUT",
    "NO_ASSERTION",
    "UNREACHABLE_ASSERTION",
    "EMPTY_LOOP",
    "ASSERT_TRUE",
    "ASSERT_LITERAL",
)

ASSERT_HELPERS = {
    "assertEqual",
    "assertNotEqual",
    "assertTrue",
    "assertFalse",
    "assertIs",
    "assertIsNot",
    "assertIsNone",
    "assertIsNotNone",
    "assertIn",
    "assertNotIn",
    "assertRaises",
    "assertRaisesRegex",
    "assertWarns",
    "assertWarnsRegex",
    "assertAlmostEqual",
    "assertGreater",
    "assertLess",
    "assertRegex",
    "fail",
    "raises",
    "warns",
    "deprecated_call",
    "xfail",
}


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def snippet_at(path: Path, line: int) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    lines = text.splitlines()
    if line < 1 or line > len(lines):
        return ""
    return lines[line - 1].strip()[:200]


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def discover_test_files(root: Path, *, exclude_probe_trees: bool) -> list[Path]:
    out: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        base = Path(dirpath)
        if exclude_probe_trees and _is_under(base, PROBE_TREE):
            dirnames[:] = []
            continue
        for name in filenames:
            if not name.endswith(".py"):
                continue
            if not (name.startswith("test_") or name.endswith("_test.py")):
                continue
            out.append(base / name)
    out.sort()
    return out


def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_parametrize(dec: ast.AST) -> ast.Call | None:
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    name = getattr(func, "attr", None) or getattr(func, "id", None)
    if name == "parametrize":
        return dec
    return None


def _literal_len(node: ast.AST) -> int | None:
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return len(node.elts)
    if isinstance(node, ast.Dict):
        return len(node.keys)
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)):
        return len(node.value)
    if isinstance(node, ast.Call):
        name = _call_name(node)
        if name in {"list", "tuple", "set", "dict", "frozenset"}:
            if not node.args and not node.keywords:
                return 0
            if len(node.args) == 1:
                inner = _literal_len(node.args[0])
                return inner
        if name == "range":
            vals: list[int] = []
            for arg in node.args:
                if isinstance(arg, ast.UnaryOp) and isinstance(arg.op, ast.USub):
                    if isinstance(arg.operand, ast.Constant) and isinstance(
                        arg.operand.value, int
                    ):
                        vals.append(-arg.operand.value)
                        continue
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                    vals.append(arg.value)
                else:
                    return None
            if len(vals) == 1:
                return max(vals[0], 0)
            if len(vals) == 2:
                return max(vals[1] - vals[0], 0)
            if len(vals) == 3:
                start, stop, step = vals
                if step == 0:
                    return None
                n = (stop - start + (step - (1 if step > 0 else -1))) // step
                return max(n, 0)
    return None


def _module_sequence_lens(tree: ast.AST) -> dict[str, int]:
    sizes: dict[str, int] = {}
    if not isinstance(tree, ast.Module):
        return sizes
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        n = _literal_len(node.value)
        if n is None:
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                sizes[target.id] = n
    return sizes


def _parametrize_count(fn: ast.AST, sizes: dict[str, int]) -> int | None:
    """Product of parametrize list lengths. 0 means never collected.

    None means the function is not parametrized.
    """
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    product = 1
    found = False
    for dec in fn.decorator_list:
        call = _is_parametrize(dec)
        if call is None or len(call.args) < 2:
            continue
        found = True
        values = call.args[1]
        n = _literal_len(values)
        if n is None and isinstance(values, ast.Name):
            n = sizes.get(values.id)
        if n is None:
            return None
        product *= n
    if not found:
        return None
    return product


def _iter_test_functions(tree: ast.AST):
    if not isinstance(tree, ast.Module):
        return
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                yield node.name, node
        elif isinstance(node, ast.ClassDef):
            class_ok = node.name.startswith("Test")
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name.startswith("test_"):
                    yield f"{node.name}::{item.name}", item
                elif class_ok and item.name.startswith("test"):
                    yield f"{node.name}::{item.name}", item


def _is_assert_helper_call(node: ast.AST) -> bool:
    name = _call_name(node)
    return name in ASSERT_HELPERS if name else False


def _truthy_constant(node: ast.AST) -> bool | None:
    if not isinstance(node, ast.Constant):
        return None
    try:
        return bool(node.value) and node.value is not False
    except Exception:
        return None


def _collect_asserts(fn: ast.AST) -> list[ast.Assert]:
    return [n for n in ast.walk(fn) if isinstance(n, ast.Assert)]


def _collect_helper_calls(fn: ast.AST) -> list[ast.Call]:
    out: list[ast.Call] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and _is_assert_helper_call(n):
            out.append(n)
    return out


def _exception_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _exception_name(node.func)
    return None


def _raise_is_assertion(node: ast.AST) -> bool:
    if not isinstance(node, ast.Raise) or node.exc is None:
        return False
    return _exception_name(node.exc) == "AssertionError"


def _collect_assertion_raises(fn: ast.AST) -> list[ast.Raise]:
    return [n for n in ast.walk(fn) if _raise_is_assertion(n)]


def _empty_loop_nodes(fn: ast.AST, sizes: dict[str, int]) -> list[ast.AST]:
    empty: list[ast.AST] = []
    for n in ast.walk(fn):
        if isinstance(n, ast.For):
            length = _literal_len(n.iter)
            if length is None and isinstance(n.iter, ast.Name):
                length = sizes.get(n.iter.id)
            if length == 0:
                empty.append(n)
        elif isinstance(n, ast.While):
            if isinstance(n.test, ast.Constant) and not n.test.value:
                empty.append(n)
    return empty


def _node_in(child: ast.AST, parents: list[ast.AST]) -> bool:
    for parent in parents:
        for n in ast.walk(parent):
            if n is child:
                return True
    return False


def _dead_if_nodes(fn: ast.AST) -> list[ast.If]:
    dead: list[ast.If] = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.If):
            continue
        t = n.test
        if isinstance(t, ast.Constant) and not t.value:
            dead.append(n)
            continue
        if isinstance(t, ast.Constant) and t.value == 0:
            dead.append(n)
    return dead


def _load_arg_constants(fn: ast.AST) -> list[str]:
    names: list[str] = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.Call):
            continue
        if _call_name(n) != "_load":
            continue
        if n.args and isinstance(n.args[0], ast.Constant):
            val = n.args[0].value
            if isinstance(val, str):
                names.append(val)
    return names


def _calls_bench(fn: ast.AST) -> bool:
    for n in ast.walk(fn):
        name = _call_name(n)
        if name and name.startswith("bench_"):
            return True
    return False


def measure_json_input_size(path: Path) -> int:
    """Runtime cardinality. The file name is not consulted."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("items", "inputs", "rows", "data", "cases"):
            val = data.get(key)
            if isinstance(val, list):
                return len(val)
        return len(data)
    if hasattr(data, "__len__"):
        return len(data)
    return 0


def execute_under_coverage(path: Path, func_name: str) -> set[int]:
    """Run a zero-arg test and return source lines that actually ran."""
    src = path.read_text(encoding="utf-8")
    resolved = str(path.resolve())
    ns: dict[str, Any] = {
        "__name__": f"bld0041_{path.stem}",
        "__file__": resolved,
    }
    code = compile(src, resolved, "exec")
    try:
        exec(code, ns)
    except Exception:
        return set()
    fn = ns.get(func_name)
    if not callable(fn):
        return set()
    hits: set[int] = set()
    target = str(path.resolve())

    def tracer(frame, event, arg):
        if event == "line":
            fn_path = os.path.abspath(frame.f_code.co_filename)
            if fn_path == target:
                hits.add(int(frame.f_lineno))
        return tracer

    sys.settrace(tracer)
    try:
        fn()
    except Exception:
        # A planted tautology must not raise. If it does, coverage is still useful.
        pass
    finally:
        sys.settrace(None)
    return hits


def _module_imports_pytest(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for alias in n.names:
                if alias.name == "pytest" or alias.name.startswith("pytest."):
                    return True
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith(
            "pytest"
        ):
            return True
    return False


def _can_exec(fn: ast.AST, tree: ast.AST) -> bool:
    if _module_imports_pytest(tree):
        return False
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if any(_is_parametrize(d) is not None for d in fn.decorator_list):
        return False
    args = fn.args
    if len(args.args) != 0 or args.vararg or args.kwarg:
        return False
    if args.posonlyargs or args.kwonlyargs:
        return False
    return True


def _classify_one(
    path: Path,
    test_id: str,
    fn: ast.AST,
    sizes: dict[str, int],
    tree: ast.AST,
    *,
    origin: str,
    run_coverage: bool,
    measure_benchmarks: bool,
) -> dict | None:
    rel_path = rel(path)
    param_n = _parametrize_count(fn, sizes)
    asserts = _collect_asserts(fn)
    helpers = _collect_helper_calls(fn)
    raises = _collect_assertion_raises(fn)
    empty_loops = _empty_loop_nodes(fn, sizes)
    dead_ifs = _dead_if_nodes(fn)
    coverage_hits: set[int] | None = None
    func_name = fn.name if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) else test_id
    if run_coverage and _can_exec(fn, tree):
        coverage_hits = execute_under_coverage(path, func_name)

    fixture_sizes: list[tuple[str, int]] = []
    if measure_benchmarks:
        for name in _load_arg_constants(fn):
            fpath = path.parent / name
            if fpath.is_file():
                fixture_sizes.append((name, measure_json_input_size(fpath)))

    is_bench = func_name.startswith("test_bench") or _calls_bench(fn)
    empty_fixtures = [(n, s) for n, s in fixture_sizes if s == 0]

    def finding(reason: str, line: int, extra: dict | None = None) -> dict:
        row = {
            "test_id": f"{rel_path}::{func_name}",
            "function": func_name,
            "path": rel_path,
            "line": int(line),
            "reason_class": reason,
            "snippet": snippet_at(path, int(line)) or func_name,
            "origin": origin,
        }
        if extra:
            row.update(extra)
        return row

    lineno = getattr(fn, "lineno", 1)

    if param_n == 0:
        return finding("EMPTY_PARAMETRIZE", lineno)

    if is_bench and empty_fixtures:
        fname, size = empty_fixtures[0]
        return finding(
            "EMPTY_BENCHMARK_INPUT",
            lineno,
            {
                "measured_input_size": size,
                "fixture_path": rel(path.parent / fname),
                "fixture_basename": fname,
                "fixture_name_not_consulted": True,
                "measurement": "len(json.loads(fixture_bytes))",
            },
        )

    real_helpers = helpers
    if not asserts and not real_helpers and not raises:
        return finding("NO_ASSERTION", lineno)

    # Partition asserts into tautological / dead vs possibly-real.
    tautological_true: list[ast.Assert] = []
    tautological_literal: list[ast.Assert] = []
    in_empty_loop: list[ast.Assert] = []
    unreachable: list[ast.Assert] = []
    real: list[ast.Assert] = []
    in_empty_loop_raises: list[ast.Raise] = []
    unreachable_raises: list[ast.Raise] = []
    real_raises: list[ast.Raise] = []

    for a in asserts:
        if _node_in(a, empty_loops):
            in_empty_loop.append(a)
            continue
        if _node_in(a, dead_ifs):
            unreachable.append(a)
            continue
        if coverage_hits is not None and a.lineno not in coverage_hits:
            unreachable.append(a)
            continue
        t = a.test
        if isinstance(t, ast.Constant) and t.value is True:
            tautological_true.append(a)
            continue
        truthy = _truthy_constant(t)
        if truthy is True and t.value is not True:
            tautological_literal.append(a)
            continue
        real.append(a)

    for node in raises:
        if _node_in(node, empty_loops):
            in_empty_loop_raises.append(node)
            continue
        if _node_in(node, dead_ifs):
            unreachable_raises.append(node)
            continue
        # A passing run does not execute `if not ok: raise AssertionError`.
        # Coverage of the raise line is not a tautology signal; only a
        # statically dead branch or empty iterator is.
        real_raises.append(node)

    if real_helpers:
        # pytest.raises / unittest helpers can fail. Not a tautology.
        return None
    if real or real_raises:
        return None

    remaining = (
        (unreachable, "UNREACHABLE_ASSERTION"),
        (unreachable_raises, "UNREACHABLE_ASSERTION"),
        (in_empty_loop, "EMPTY_LOOP"),
        (in_empty_loop_raises, "EMPTY_LOOP"),
        (tautological_true, "ASSERT_TRUE"),
        (tautological_literal, "ASSERT_LITERAL"),
    )
    for group, reason in remaining:
        if group:
            node = group[0]
            extra = {}
            if reason == "UNREACHABLE_ASSERTION" and coverage_hits is not None:
                extra = {
                    "assert_line": node.lineno,
                    "assert_line_covered": False,
                    "coverage_method": "sys.settrace",
                    "executed_lines": sorted(coverage_hits),
                }
            return finding(reason, node.lineno, extra)
    return None


def census_files(
    files: list[Path],
    *,
    origin: str,
    run_coverage: bool,
    measure_benchmarks: bool,
) -> list[dict]:
    findings: list[dict] = []
    for path in files:
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        sizes = _module_sequence_lens(tree)
        for test_id, fn in _iter_test_functions(tree):
            row = _classify_one(
                path,
                test_id,
                fn,
                sizes,
                tree,
                origin=origin,
                run_coverage=run_coverage,
                measure_benchmarks=measure_benchmarks,
            )
            if row is not None:
                findings.append(row)
    findings.sort(key=lambda r: (r["path"], r["line"], r["test_id"]))
    return findings


def count_tests(files: list[Path]) -> tuple[int, list[str]]:
    n = 0
    ids: list[str] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for test_id, fn in _iter_test_functions(tree):
            n += 1
            func = fn.name if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) else test_id
            ids.append(f"{rel(path)}::{func}")
    return n, ids


def distribution(findings: list[dict], tests_scanned: int) -> dict:
    dist = {k: 0 for k in (
        "NO_ASSERTION",
        "ASSERT_TRUE",
        "ASSERT_LITERAL",
        "EMPTY_LOOP",
        "EMPTY_PARAMETRIZE",
        "EMPTY_BENCHMARK_INPUT",
        "UNREACHABLE_ASSERTION",
    )}
    for row in findings:
        key = row["reason_class"]
        if key in dist:
            dist[key] += 1
    dist["tests_scanned"] = tests_scanned
    dist["flagged"] = len(findings)
    return dist


def live_files() -> list[Path]:
    return discover_test_files(REPO, exclude_probe_trees=True)


def planted_files() -> list[Path]:
    return discover_test_files(PLANTED, exclude_probe_trees=False)


def live_census() -> dict:
    files = live_files()
    scanned, ids = count_tests(files)
    findings = census_files(
        files, origin="live", run_coverage=False, measure_benchmarks=True
    )
    return {
        "tests_scanned": scanned,
        "test_ids": ids,
        "flagged": len(findings),
        "files": [rel(p) for p in files],
        "findings": findings,
        "distribution": distribution(findings, scanned),
        "benchmarks_present": any(
            Path(p).name.lower().find("bench") >= 0 for p in files
        ),
        "routing_benchmark_yml": (
            REPO / ".github" / "workflows" / "routing-benchmark.yml"
        ).is_file(),
    }


def planted_census() -> dict:
    files = planted_files()
    scanned, ids = count_tests(files)
    findings = census_files(
        files, origin="planted-control", run_coverage=True, measure_benchmarks=True
    )
    return {
        "tests_scanned": scanned,
        "test_ids": ids,
        "flagged": len(findings),
        "files": [rel(p) for p in files],
        "findings": findings,
        "distribution": distribution(findings, scanned),
    }


def _by_function(findings: list[dict]) -> dict[str, dict]:
    return {row["function"]: row for row in findings}


def run_planted_controls() -> dict:
    planted = planted_census()
    by_fn = _by_function(planted["findings"])
    well = (
        "test_c4_well_formed" not in by_fn
        and "test_c5_raise_assertion_error" not in by_fn
    )
    trap = "test_regex_trap_comment" not in by_fn
    named_full = "test_bench_named_empty_but_full" not in by_fn

    c1 = by_fn.get("test_c1_no_assert")
    c2 = by_fn.get("test_c2_unreachable_assert")
    c3 = by_fn.get("test_c3_bench_full_corpus")

    c2_uncovered = False
    if c2 is not None:
        c2_uncovered = c2.get("assert_line_covered") is False and c2.get(
            "assert_line"
        )
        if not c2_uncovered:
            taut = PLANTED / "execable" / "test_tautologies.py"
            hits = execute_under_coverage(taut, "test_c2_unreachable_assert")
            tree = ast.parse(taut.read_text(encoding="utf-8"))
            assert_line = None
            for n in ast.walk(tree):
                if isinstance(n, ast.FunctionDef) and n.name == "test_c2_unreachable_assert":
                    for a in ast.walk(n):
                        if isinstance(a, ast.Assert):
                            assert_line = a.lineno
            c2_uncovered = bool(assert_line) and assert_line not in hits
            if c2 is not None:
                c2["assert_line"] = assert_line
                c2["assert_line_covered"] = (
                    False if c2_uncovered else True
                )
                c2["executed_lines"] = sorted(hits)
                c2["coverage_method"] = "sys.settrace"

    c3_ok = (
        c3 is not None
        and c3["reason_class"] == "EMPTY_BENCHMARK_INPUT"
        and c3.get("measured_input_size") == 0
        and c3.get("fixture_name_not_consulted") is True
        and str(c3.get("fixture_basename") or "") == "full_corpus.json"
    )

    controls = [
        {
            "id": "T-NO-ASSERT-PLANTED",
            "result": "PASS"
            if c1 is not None and c1["reason_class"] == "NO_ASSERTION"
            else "FAIL",
            "evidence": (
                f"{c1['path']}:{c1['line']}" if c1 else "test_c1_no_assert not flagged"
            ),
        },
        {
            "id": "T-UNREACHABLE-COVERAGE",
            "result": "PASS"
            if c2 is not None
            and c2["reason_class"] == "UNREACHABLE_ASSERTION"
            and c2_uncovered
            else "FAIL",
            "evidence": (
                f"assert_line={c2.get('assert_line')} covered={c2.get('assert_line_covered')} "
                f"hits={c2.get('executed_lines')}"
                if c2
                else "test_c2_unreachable_assert not flagged"
            ),
        },
        {
            "id": "T-EMPTY-BENCH-RUNTIME-SIZE",
            "result": "PASS" if c3_ok and named_full else "FAIL",
            "evidence": (
                f"full_corpus.json measured_input_size={c3.get('measured_input_size') if c3 else None}; "
                f"filename_trap_not_flagged={named_full}; "
                f"method=len(json.loads(fixture_bytes))"
            ),
        },
        {
            "id": "T-NEGATIVE-WELL-FORMED",
            "result": "PASS" if well and trap else "FAIL",
            "evidence": (
                "test_c4_well_formed_flagged="
                f"{'test_c4_well_formed' in by_fn}; "
                "raise_assertionerror_flagged="
                f"{'test_c5_raise_assertion_error' in by_fn}; "
                f"regex_trap_flagged={not trap}"
            ),
        },
    ]
    return {
        "planted": planted,
        "controls": controls,
        "all_pass": all(c["result"] == "PASS" for c in controls),
        "by_function": {k: v["reason_class"] for k, v in by_fn.items()},
    }
