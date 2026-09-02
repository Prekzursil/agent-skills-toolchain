#!/usr/bin/env python3
"""AST census of vacuous tests (C23 / TST-0348).

Use, not mention: only ast.Assert, assertion-call nodes, and raise AssertionError
count as asserting. A string or comment that contains the word "assert" does not.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

CLASSES = (
    "no_assertion",
    "assert_constant",
    "assert_own_mock",
    "swallowed_failure",
)

MOCK_CTORS = frozenset(
    {
        "Mock",
        "MagicMock",
        "AsyncMock",
        "NonCallableMock",
        "PropertyMock",
        "create_autospec",
    }
)
PATCH_NAMES = frozenset({"patch", "object"})
PYTEST_HELPERS = frozenset({"raises", "warns", "deprecated_call", "fail"})
BROAD_EXC = frozenset({"Exception", "BaseException", "AssertionError"})
BUILTINS = frozenset(
    {
        "abs",
        "all",
        "any",
        "bool",
        "bytes",
        "callable",
        "chr",
        "complex",
        "dict",
        "dir",
        "enumerate",
        "filter",
        "float",
        "format",
        "frozenset",
        "getattr",
        "globals",
        "hasattr",
        "hash",
        "hex",
        "id",
        "int",
        "isinstance",
        "issubclass",
        "iter",
        "len",
        "list",
        "locals",
        "map",
        "max",
        "min",
        "next",
        "object",
        "oct",
        "open",
        "ord",
        "print",
        "property",
        "range",
        "repr",
        "reversed",
        "round",
        "set",
        "setattr",
        "sorted",
        "str",
        "sum",
        "super",
        "tuple",
        "type",
        "vars",
        "zip",
        "classmethod",
        "staticmethod",
    }
)


def basename(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def is_constant_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.Name) and node.id in {"True", "False", "None"}:
        return True
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(is_constant_expr(elt) for elt in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub, ast.Not)
    ):
        return is_constant_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return is_constant_expr(node.left) and is_constant_expr(node.right)
    if isinstance(node, ast.BoolOp):
        return all(is_constant_expr(v) for v in node.values)
    if isinstance(node, ast.Compare):
        return is_constant_expr(node.left) and all(
            is_constant_expr(c) for c in node.comparators
        )
    return False


def const_value(node: ast.AST):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id == "True":
        return True
    if isinstance(node, ast.Name) and node.id == "False":
        return False
    if isinstance(node, ast.Name) and node.id == "None":
        return None
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = const_value(node.operand)
        if isinstance(v, (int, float)):
            return -v
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        v = const_value(node.operand)
        if v is not None or isinstance(node.operand, ast.Constant):
            return not v
    if isinstance(node, (ast.Tuple, ast.List)):
        return tuple(const_value(elt) for elt in node.elts)
    return None


def compare_holds(node: ast.Compare) -> bool | None:
    if not is_constant_expr(node):
        return None
    left = const_value(node.left)
    cur = left
    for op, comp in zip(node.ops, node.comparators):
        right = const_value(comp)
        try:
            if isinstance(op, ast.Eq):
                ok = cur == right
            elif isinstance(op, ast.NotEq):
                ok = cur != right
            elif isinstance(op, ast.Is):
                ok = cur is right
            elif isinstance(op, ast.IsNot):
                ok = cur is not right
            elif isinstance(op, ast.Lt):
                ok = cur < right
            elif isinstance(op, ast.LtE):
                ok = cur <= right
            elif isinstance(op, ast.Gt):
                ok = cur > right
            elif isinstance(op, ast.GtE):
                ok = cur >= right
            elif isinstance(op, ast.In):
                ok = cur in right
            elif isinstance(op, ast.NotIn):
                ok = cur not in right
            else:
                return None
        except TypeError:
            return None
        if not ok:
            return False
        cur = right
    return True


def is_assertion_call(node: ast.Call) -> bool:
    name = basename(node.func)
    if name.startswith("assert"):
        return True
    if name in PYTEST_HELPERS:
        return True
    if name == "fail":
        return True
    return False


def is_assertion_error_raise(node: ast.Raise) -> bool:
    exc = node.exc
    if exc is None:
        return False
    if isinstance(exc, ast.Call):
        return basename(exc.func) == "AssertionError"
    return basename(exc) == "AssertionError"


def assertion_sites(fn: ast.AST) -> list[ast.AST]:
    sites: list[ast.AST] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            sites.append(node)
        elif isinstance(node, ast.Call) and is_assertion_call(node):
            sites.append(node)
        elif isinstance(node, ast.Raise) and is_assertion_error_raise(node):
            sites.append(node)
        elif isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and is_assertion_call(ctx):
                    sites.append(ctx)
    return sites


def mock_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if basename(node.value.func) in MOCK_CTORS:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        names.add(target.id)
        if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Call):
            if basename(node.value.func) in MOCK_CTORS and isinstance(
                node.target, ast.Name
            ):
                names.add(node.target.id)
        if isinstance(node, ast.With):
            for item in node.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and basename(ctx.func) in {
                    "patch",
                    *PATCH_NAMES,
                }:
                    if isinstance(item.optional_vars, ast.Name):
                        names.add(item.optional_vars.id)
    for dec in fn.decorator_list:
        call = dec if isinstance(dec, ast.Call) else None
        if call is None:
            continue
        if basename(call.func) in {"patch", *PATCH_NAMES}:
            args = [a.arg for a in fn.args.args if a.arg not in {"self", "cls"}]
            if args:
                names.add(args[-1])
    return names


def mock_configured(fn: ast.AST, mocks: set[str]) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr in {
                "return_value",
                "side_effect",
            }:
                if expr_from_mock(target.value, mocks):
                    return True
    return False


def expr_from_mock(node: ast.AST, mocks: set[str]) -> bool:
    if isinstance(node, ast.Name):
        return node.id in mocks
    if isinstance(node, ast.Attribute):
        return expr_from_mock(node.value, mocks)
    if isinstance(node, ast.Call):
        return expr_from_mock(node.func, mocks)
    if isinstance(node, ast.Subscript):
        return expr_from_mock(node.value, mocks)
    return False


def has_sut_call(fn: ast.AST, mocks: set[str]) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = basename(node.func)
        if is_assertion_call(node):
            continue
        if name in MOCK_CTORS or name in {"patch", *PATCH_NAMES}:
            continue
        if name in BUILTINS:
            continue
        if expr_from_mock(node.func, mocks):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in mocks:
            continue
        return True
    return False


def site_is_constant_pass(site: ast.AST) -> bool:
    if isinstance(site, ast.Assert):
        test = site.test
        if isinstance(test, ast.Compare):
            held = compare_holds(test)
            return held is True
        if is_constant_expr(test):
            val = const_value(test)
            return bool(val)
        return False
    if isinstance(site, ast.Call):
        name = basename(site.func)
        args = site.args
        if name in {"assertTrue", "assert_"} and args and is_constant_expr(args[0]):
            return bool(const_value(args[0]))
        if name == "assertFalse" and args and is_constant_expr(args[0]):
            return not bool(const_value(args[0]))
        if name in {"assertEqual", "assertEquals"} and len(args) >= 2:
            if is_constant_expr(args[0]) and is_constant_expr(args[1]):
                return const_value(args[0]) == const_value(args[1])
        if name == "assertIs" and len(args) >= 2:
            if is_constant_expr(args[0]) and is_constant_expr(args[1]):
                return const_value(args[0]) is const_value(args[1])
        if name == "assertIsNone" and args and is_constant_expr(args[0]):
            return const_value(args[0]) is None
        if name in {"assertTrue", "assert_"} and args:
            if isinstance(args[0], ast.Compare):
                held = compare_holds(args[0])
                return held is True
    return False


def site_is_own_mock(site: ast.AST, mocks: set[str]) -> bool:
    if not mocks:
        return False
    if isinstance(site, ast.Assert):
        test = site.test
        if isinstance(test, ast.Compare):
            return expr_from_mock(test.left, mocks) or any(
                expr_from_mock(c, mocks) for c in test.comparators
            )
        return expr_from_mock(test, mocks)
    if isinstance(site, ast.Call):
        name = basename(site.func)
        if name.startswith("assert") and isinstance(site.func, ast.Attribute):
            if expr_from_mock(site.func.value, mocks):
                return True
        for arg in site.args:
            if expr_from_mock(arg, mocks):
                return True
    return False


def handler_types(handler: ast.ExceptHandler) -> set[str]:
    names: set[str] = set()
    node = handler.type
    if node is None:
        return {"BaseException"}
    if isinstance(node, ast.Tuple):
        elts = node.elts
    else:
        elts = [node]
    for elt in elts:
        n = basename(elt)
        if n:
            names.add(n)
    return names


def handler_swallows(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise):
            return False
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            if is_assertion_call(stmt.value):
                return False
            if basename(stmt.value.func) == "fail":
                return False
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            continue
        if isinstance(stmt, (ast.Return, ast.Continue, ast.Break)):
            continue
        return False
    return True


def _fn_from_body(body: list) -> ast.FunctionDef:
    return ast.FunctionDef(
        name="_",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
    )


def swallowed(fn: ast.AST) -> list[ast.Try]:
    found: list[ast.Try] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        try_has_assert = bool(assertion_sites(_fn_from_body(node.body)))
        for handler in node.handlers:
            types = handler_types(handler)
            if not (types & BROAD_EXC) and "BaseException" not in types:
                continue
            if not handler_swallows(handler):
                continue
            if try_has_assert or "AssertionError" in types:
                found.append(node)
                break
    return found


def is_test_function(node: ast.AST, parent: ast.AST | None) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    if not node.name.startswith("test_"):
        return False
    if parent is None:
        return True
    if isinstance(parent, (ast.Module, ast.ClassDef)):
        return True
    return False


def iter_test_functions(tree: ast.AST) -> Iterable[tuple[str, ast.AST, ast.AST]]:
    for parent in ast.walk(tree):
        body = getattr(parent, "body", None)
        if not isinstance(body, list):
            continue
        if not isinstance(parent, (ast.Module, ast.ClassDef)):
            continue
        for node in body:
            if is_test_function(node, parent):
                owner = parent.name if isinstance(parent, ast.ClassDef) else ""
                yield node.name, owner, node


def relpath(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def body_lines(node: ast.AST) -> int:
    start = getattr(node, "lineno", 1) or 1
    end = getattr(node, "end_lineno", start) or start
    return max(1, end - start + 1)


def classify_function(fn: ast.AST, mocks: set[str]) -> list[str]:
    sites = assertion_sites(fn)
    classes: list[str] = []
    if swallowed(fn):
        classes.append("swallowed_failure")
    if not sites:
        if "swallowed_failure" not in classes:
            classes.append("no_assertion")
        return classes
    if sites and all(site_is_constant_pass(s) for s in sites):
        classes.append("assert_constant")
        return classes
    if (
        mocks
        and mock_configured(fn, mocks)
        and all(site_is_own_mock(s, mocks) for s in sites)
        and not has_sut_call(fn, mocks)
    ):
        classes.append("assert_own_mock")
    return classes


def scan_source(source: str, path: str) -> list[dict]:
    tree = ast.parse(source, filename=path)
    findings: list[dict] = []
    for name, owner, fn in iter_test_functions(tree):
        mocks = mock_names(fn) if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) else set()
        classes = classify_function(fn, mocks)
        rec = {
            "test": f"{owner}.{name}" if owner else name,
            "name": name,
            "owner": owner or None,
            "file": path,
            "line": int(getattr(fn, "lineno", 1) or 1),
            "end_line": int(getattr(fn, "end_lineno", 1) or 1),
            "body_lines": body_lines(fn),
            "assertion_sites": len(assertion_sites(fn)),
            "classes": classes,
            "vacuous": bool(classes),
        }
        findings.append(rec)
    return findings


def scan_file(path: Path, repo: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    return scan_source(text, relpath(path, repo))


def iter_test_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        if path.name == "conftest.py":
            continue
        files.append(path)
    return files


def scan_roots(roots: list[Path], repo: Path) -> list[dict]:
    out: list[dict] = []
    for root in roots:
        for path in iter_test_files(root):
            try:
                out.extend(scan_file(path, repo))
            except SyntaxError:
                continue
    return out


def loc(rec: dict) -> str:
    return f"{rec['file']}:{rec['line']}"


def partition(findings: list[dict]) -> dict:
    by_class = {c: [] for c in CLASSES}
    for rec in findings:
        for c in rec["classes"]:
            by_class[c].append(rec)
    union = [rec for rec in findings if rec["vacuous"]]
    return {
        "n_tests": len(findings),
        "n_vacuous": len(union),
        "n_genuine": len(findings) - len(union),
        "by_class": {
            c: {
                "count": len(rows),
                "file_line": [loc(r) for r in rows],
                "tests": [
                    {
                        "id": r["test"],
                        "file": r["file"],
                        "line": r["line"],
                        "file_line": loc(r),
                        "body_lines": r["body_lines"],
                        "assertion_sites": r["assertion_sites"],
                    }
                    for r in rows
                ],
            }
            for c, rows in by_class.items()
        },
        "union_file_line": [loc(r) for r in union],
        "findings": findings,
    }


def live_roots(repo: Path) -> list[Path]:
    return [
        repo / "tools" / "command-center" / "tests",
        repo / "tools" / "marketplace" / "tests",
    ]


def fixture_root(here: Path) -> Path:
    return here / "fixtures"


def production_coverage_status(repo: Path) -> dict:
    candidates = [
        repo / ".coverage",
        repo / "coverage.xml",
        repo / "htmlcov" / "index.html",
    ]
    present = []
    for path in candidates:
        if path.exists():
            try:
                present.append(path.resolve().relative_to(repo.resolve()).as_posix())
            except ValueError:
                present.append(path.as_posix())
    return {
        "status": "NOT-CHECKED",
        "reason": (
            "no program .coverage or coverage.xml on this worktree; BLD-0002 "
            "scratch coverage.xml is a fixture for a different unit and is not "
            "the headline figure for this corpus"
        ),
        "candidates": [
            ".coverage",
            "coverage.xml",
            "htmlcov/index.html",
        ],
        "present": present,
        "headline_pct": None,
    }


def coverage_recompute(findings: list[dict]) -> dict:
    n = len(findings)
    vacuous = [r for r in findings if r["vacuous"]]
    n_v = len(vacuous)
    w_all = sum(int(r["body_lines"]) for r in findings)
    w_keep = sum(int(r["body_lines"]) for r in findings if not r["vacuous"])
    test_excl = round(100.0 * (n - n_v) / n, 4) if n else 0.0
    line_excl = round(100.0 * w_keep / w_all, 4) if w_all else 0.0
    return {
        "n_tests": n,
        "n_vacuous": n_v,
        "n_genuine": n - n_v,
        "headline_pct": 100.0,
        "headline_meaning": (
            "every collected test is counted in the green / coverage-contribution "
            "metric; vacuous tests inflate that headline"
        ),
        "excluding_vacuous_pct": test_excl,
        "the_number_that_matters": test_excl,
        "headline_body_line_weight": w_all,
        "excluding_vacuous_body_line_weight": w_keep,
        "excluding_vacuous_line_weight_pct": line_excl,
        "side_by_side": {
            "headline_pct": 100.0,
            "excluding_vacuous_pct": test_excl,
        },
    }
