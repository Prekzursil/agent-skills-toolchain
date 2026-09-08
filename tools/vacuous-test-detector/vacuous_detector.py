#!/usr/bin/env python3
"""AST detector for vacuous tests that assert nothing (TST-0348 / C23).

Vacuous classes (catalog question_or_target):
  1. no_assertion — test body has no assert statement and no assertion call
  2. constant_assertion — every assert compares only compile-time constants
  3. mock_configured_assertion — asserts only on a mock the same test configured
  4. swallowed_failure — try/except swallows AssertionError/Exception without re-raise

Discipline: scan is AST-based. A string/docstring that merely *mentions* the
word ``assert`` is not counted as asserting (use-versus-mention).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence

REPO = Path(__file__).resolve().parents[2]

VACUOUS_CLASSES = (
    "no_assertion",
    "constant_assertion",
    "mock_configured_assertion",
    "swallowed_failure",
)

ASSERT_METHOD_PREFIXES = (
    "assert",
    "assert_",
)
# unittest / pytest helpers that count as real assertions
ASSERT_CALL_NAMES = frozenset(
    {
        "assertEqual",
        "assertequals",
        "assertnotequal",
        "asserttrue",
        "assertfalse",
        "assertis",
        "assertisnot",
        "assertisin",
        "assertnotin",
        "assertisinstance",
        "assertisnone",
        "assertisnotnone",
        "assertraises",
        "assertraisesregex",
        "assertraisesregexp",
        "assertalmostequal",
        "assertgreater",
        "assertgreaterEqual",
        "assertless",
        "assertlessequal",
        "assertregex",
        "assertnotregex",
        "assertcountEqual",
        "assertlistEqual",
        "assertdictEqual",
        "assertsetequal",
        "asserttupleequal",
        "assertin",
        "assertnotin",
        "fail",
        "pytest.raises",  # dotted handled separately
    }
)

MOCK_CTOR_NAMES = frozenset(
    {
        "Mock",
        "MagicMock",
        "AsyncMock",
        "NonCallableMock",
        "PropertyMock",
        "create_autospec",
    }
)
PATCH_NAMES = frozenset({"patch", "patch.object"})


@dataclass
class Finding:
    path: str
    line: int
    test_name: str
    vacuous_class: str
    detail: str

    def loc(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class ScanReport:
    roots: list[str]
    files_scanned: int = 0
    tests_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)
    class_counts: dict[str, int] = field(default_factory=dict)
    # Coverage recomputation (equal-weight per test; headline assumes all tests
    # contribute; excluding vacuous is the number that matters).
    headline_test_count: int = 0
    vacuous_test_count: int = 0
    non_vacuous_test_count: int = 0
    headline_coverage_pct: float = 100.0
    coverage_excluding_vacuous_pct: float = 100.0

    def finalize(self) -> None:
        counts: Counter[str] = Counter(f.vacuous_class for f in self.findings)
        self.class_counts = {k: counts.get(k, 0) for k in VACUOUS_CLASSES}
        # One finding per (test, class) may duplicate; unique vacuous tests:
        vacuous_tests = {(f.path, f.test_name) for f in self.findings}
        self.headline_test_count = self.tests_scanned
        self.vacuous_test_count = len(vacuous_tests)
        self.non_vacuous_test_count = max(
            self.tests_scanned - self.vacuous_test_count, 0
        )
        # Headline: treat every collected test as contributing 100% weight.
        # Excluding vacuous: only non-vacuous tests remain in the denominator
        # for "tests that assert something"; the percentage that matters is
        # non_vacuous / headline (how much of the reported count is real).
        if self.tests_scanned == 0:
            self.headline_coverage_pct = 0.0
            self.coverage_excluding_vacuous_pct = 0.0
        else:
            self.headline_coverage_pct = 100.0
            self.coverage_excluding_vacuous_pct = round(
                100.0 * self.non_vacuous_test_count / self.tests_scanned, 4
            )

    def to_dict(self) -> dict:
        self.finalize()
        return {
            "roots": self.roots,
            "files_scanned": self.files_scanned,
            "tests_scanned": self.tests_scanned,
            "class_counts": self.class_counts,
            "findings": [asdict(f) for f in self.findings],
            "file_line_list": [f.loc() for f in self.findings],
            "headline_test_count": self.headline_test_count,
            "vacuous_test_count": self.vacuous_test_count,
            "non_vacuous_test_count": self.non_vacuous_test_count,
            "headline_coverage_pct": self.headline_coverage_pct,
            "coverage_excluding_vacuous_pct": self.coverage_excluding_vacuous_pct,
        }


def _is_test_function(node: ast.AST) -> bool:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    name = node.name
    if name.startswith("test_") or name.endswith("_test"):
        return True
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "pytest":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr in {"mark", "fixture"}:
            # @pytest.mark.* on a non-test name is not a test
            pass
        # @pytest.mark.parametrize still needs test_ prefix; leave name rule
    return False


def _attr_chain(node: ast.AST) -> str | None:
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    return _attr_chain(node.func)


def _is_constant_expr(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_constant_expr(elt) for elt in node.elts)
    if isinstance(node, ast.Dict):
        keys = [k for k in node.keys if k is not None]
        return all(_is_constant_expr(k) for k in keys) and all(
            _is_constant_expr(v) for v in node.values
        )
    if isinstance(node, ast.UnaryOp) and isinstance(
        node.op, (ast.UAdd, ast.USub, ast.Not)
    ):
        return _is_constant_expr(node.operand)
    if isinstance(node, ast.BinOp):
        return _is_constant_expr(node.left) and _is_constant_expr(node.right)
    if isinstance(node, ast.Compare):
        if not _is_constant_expr(node.left):
            return False
        return all(_is_constant_expr(c) for c in node.comparators)
    if isinstance(node, ast.Name) and node.id in {"True", "False", "None"}:
        return True
    return False


def _is_assertion_call(node: ast.Call) -> bool:
    name = _call_name(node)
    if name is None:
        return False
    low = name.lower()
    bare = low.rsplit(".", 1)[-1]
    if bare in ASSERT_CALL_NAMES or low in ASSERT_CALL_NAMES:
        return True
    if bare.startswith("assert"):
        return True
    # pytest.raises / pytest.warns as context managers counted elsewhere
    if bare in {"raises", "warns", "deprecated_call"} and (
        low.startswith("pytest.") or name.startswith("pytest.")
    ):
        return True
    return False


def _root_name(node: ast.AST) -> str | None:
    cur = node
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id
    if isinstance(cur, ast.Subscript):
        return _root_name(cur.value)
    if isinstance(cur, ast.Call):
        return _root_name(cur.func)
    return None


class _TestAnalyzer(ast.NodeVisitor):
    """Walk one test function body and classify vacuous patterns."""

    def __init__(self, test_name: str) -> None:
        self.test_name = test_name
        self.assert_stmts: list[ast.Assert] = []
        self.assert_calls: list[ast.Call] = []
        self.has_raises_cm = False
        self.mock_names: set[str] = set()
        self.swallowed: list[ast.ExceptHandler] = []
        self._in_except_pass = False

    def visit_Assert(self, node: ast.Assert) -> None:
        self.assert_stmts.append(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _is_assertion_call(node):
            self.assert_calls.append(node)
        # mock construction / patch
        name = _call_name(node)
        if name:
            bare = name.rsplit(".", 1)[-1]
            if (
                bare in MOCK_CTOR_NAMES
                or name.endswith(".Mock")
                or name.endswith(".MagicMock")
            ):
                # parent Assign handled in visit_Assign
                pass
            if (
                bare == "patch"
                or name.endswith(".patch")
                or name.endswith(".patch.object")
            ):
                pass
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call):
            cname = _call_name(node.value)
            if cname:
                bare = cname.rsplit(".", 1)[-1]
                if bare in MOCK_CTOR_NAMES or bare == "patch":
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            self.mock_names.add(t.id)
                        elif (
                            isinstance(t, ast.Tuple)
                            and bare == "patch"
                            and len(t.elts) >= 1
                        ):
                            # start, stop = patch(...) uncommon; skip
                            pass
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            ctx = item.context_expr
            if isinstance(ctx, ast.Call):
                cname = _call_name(ctx)
                if cname:
                    bare = cname.rsplit(".", 1)[-1]
                    if bare in {"raises", "warns", "deprecated_call"}:
                        self.has_raises_cm = True
                    if (
                        bare == "patch"
                        or cname.endswith(".patch")
                        or bare in MOCK_CTOR_NAMES
                    ):
                        if item.optional_vars is not None:
                            if isinstance(item.optional_vars, ast.Name):
                                self.mock_names.add(item.optional_vars.id)
                            elif isinstance(item.optional_vars, ast.Tuple):
                                for elt in item.optional_vars.elts:
                                    if isinstance(elt, ast.Name):
                                        self.mock_names.add(elt.id)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if self._handler_swallows(node):
            self.swallowed.append(node)
        self.generic_visit(node)

    def _handler_swallows(self, node: ast.ExceptHandler) -> bool:
        """True when handler catches assertion/exception and does not re-raise."""
        if not self._catches_failure(node.type):
            return False
        body = node.body
        if not body:
            return True
        # bare pass / ellipsis / docstring-only
        meaningful = [
            s
            for s in body
            if not (
                isinstance(s, ast.Pass)
                or (
                    isinstance(s, ast.Expr)
                    and isinstance(s.value, ast.Constant)
                    and (s.value.value is ... or isinstance(s.value.value, str))
                )
            )
        ]
        if not meaningful:
            return True
        for stmt in meaningful:
            if isinstance(stmt, ast.Raise):
                return False
            # logger.exception(...) still swallows the test failure
        # If any raise exists anywhere in handler, not swallowed
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Raise):
                return False
        return True

    def _catches_failure(self, typ: ast.AST | None) -> bool:
        if typ is None:
            return True  # bare except
        names: set[str] = set()
        if isinstance(typ, ast.Name):
            names.add(typ.id)
        elif isinstance(typ, ast.Attribute):
            chain = _attr_chain(typ)
            if chain:
                names.add(chain.rsplit(".", 1)[-1])
        elif isinstance(typ, ast.Tuple):
            for elt in typ.elts:
                if isinstance(elt, ast.Name):
                    names.add(elt.id)
                elif isinstance(elt, ast.Attribute):
                    chain = _attr_chain(elt)
                    if chain:
                        names.add(chain.rsplit(".", 1)[-1])
        failureish = {
            "Exception",
            "BaseException",
            "AssertionError",
            "Error",
            "OSError",
            "ValueError",
            "RuntimeError",
        }
        return bool(names & failureish) or typ is None

    def has_any_assertion(self) -> bool:
        return bool(self.assert_stmts or self.assert_calls or self.has_raises_cm)

    def all_asserts_constant(self) -> bool:
        if self.has_raises_cm:
            return False
        if not self.assert_stmts and not self.assert_calls:
            return False
        for a in self.assert_stmts:
            if not _is_constant_expr(a.test):
                return False
        for c in self.assert_calls:
            # assertTrue(True), assertEqual(1, 1), assertEqual("a", "a")
            name = (_call_name(c) or "").rsplit(".", 1)[-1].lower()
            if name in {"assertraises", "assertraisesregex", "assertraisesregexp"}:
                return False
            if not c.args:
                return False
            if name in {"asserttrue", "assertfalse", "assertisnone", "assertisnotnone"}:
                if not _is_constant_expr(c.args[0]):
                    return False
            elif len(c.args) >= 2:
                if not (_is_constant_expr(c.args[0]) and _is_constant_expr(c.args[1])):
                    return False
            else:
                if not _is_constant_expr(c.args[0]):
                    return False
        return True

    def _expr_roots(self, subj: ast.AST) -> set[str]:
        roots: set[str] = set()
        for n in ast.walk(subj):
            if isinstance(n, ast.Name):
                roots.add(n.id)
        rn = _root_name(subj)
        if rn:
            roots.add(rn)
        return roots - {"True", "False", "None"}

    def all_asserts_on_configured_mock(self) -> bool:
        if not self.mock_names:
            return False
        if not self.has_any_assertion():
            return False
        if self.has_raises_cm:
            return False
        # Every assert must reference only mock names from this test.
        subjects: list[ast.AST] = []
        for a in self.assert_stmts:
            subjects.append(a.test)
        for c in self.assert_calls:
            # m.assert_called() / m.assert_called_with(...) — subject is the mock
            subjects.append(c.func)
            subjects.extend(c.args)
            subjects.extend(k.value for k in c.keywords)
        if not subjects:
            return False
        saw_mock_subject = False
        for subj in subjects:
            names = self._expr_roots(subj)
            if not names:
                # pure constant side of a compare — ignore
                if _is_constant_expr(subj):
                    continue
                return False
            if not names <= self.mock_names:
                return False
            if names & self.mock_names:
                saw_mock_subject = True
        return saw_mock_subject


def analyze_test(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int, str]]:
    """Return list of (vacuous_class, line, detail) for one test function."""
    analyzer = _TestAnalyzer(node.name)
    for stmt in node.body:
        analyzer.visit(stmt)
    out: list[tuple[str, int, str]] = []
    line = getattr(node, "lineno", 1) or 1

    if not analyzer.has_any_assertion():
        # Mention-only: string containing "assert" must not count — we never
        # looked at strings as assertions, so this is already AST-correct.
        out.append(
            (
                "no_assertion",
                line,
                "test body has no assert statement and no assertion call",
            )
        )
        # still report swallowed if present (orthogonal)
        if analyzer.swallowed:
            out.append(
                (
                    "swallowed_failure",
                    analyzer.swallowed[0].lineno,
                    "try/except swallows failure without re-raise",
                )
            )
        return out

    if analyzer.all_asserts_constant():
        out.append(
            (
                "constant_assertion",
                line,
                "every assertion compares only compile-time constants",
            )
        )

    if analyzer.all_asserts_on_configured_mock():
        out.append(
            (
                "mock_configured_assertion",
                line,
                f"assertions only exercise mocks configured in-test: {sorted(analyzer.mock_names)}",
            )
        )

    if analyzer.swallowed:
        out.append(
            (
                "swallowed_failure",
                analyzer.swallowed[0].lineno,
                "try/except swallows AssertionError/Exception without re-raise",
            )
        )

    return out


def iter_test_functions(
    tree: ast.AST,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if _is_test_function(node):
            yield node  # type: ignore[misc]
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if _is_test_function(item):
                    yield item  # type: ignore[misc]


def scan_file(path: Path, *, rel_base: Path | None = None) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    rel = str(path.relative_to(rel_base)) if rel_base else str(path)
    findings: list[Finding] = []
    for fn in iter_test_functions(tree):
        for vacuous_class, line, detail in analyze_test(fn):
            findings.append(
                Finding(
                    path=rel.replace("\\", "/"),
                    line=line,
                    test_name=fn.name,
                    vacuous_class=vacuous_class,
                    detail=detail,
                )
            )
    return findings


def iter_python_files(root: Path) -> Iterable[Path]:
    if root.is_file() and root.suffix == ".py":
        yield root
        return
    skip = {
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
    }
    for p in sorted(root.rglob("*.py")):
        if any(part in skip for part in p.parts):
            continue
        yield p


def scan_roots(roots: Sequence[Path], *, repo: Path | None = None) -> ScanReport:
    base = repo or REPO
    report = ScanReport(roots=[str(r) for r in roots])
    seen_tests = 0
    for root in roots:
        root = root if root.is_absolute() else (base / root)
        if not root.exists():
            continue
        for path in iter_python_files(root):
            report.files_scanned += 1
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=str(path))
            except SyntaxError:
                continue
            fns = list(iter_test_functions(tree))
            seen_tests += len(fns)
            rel = str(path.relative_to(base)).replace("\\", "/")
            for fn in fns:
                for vacuous_class, line, detail in analyze_test(fn):
                    report.findings.append(
                        Finding(
                            path=rel,
                            line=line,
                            test_name=fn.name,
                            vacuous_class=vacuous_class,
                            detail=detail,
                        )
                    )
    report.tests_scanned = seen_tests
    report.finalize()
    return report


def detect(target: Path) -> list[str]:
    """detector-self-test compatible API: truthy list of findings under target."""
    base = target if target.is_dir() else target.parent
    findings: list[str] = []
    for path in iter_python_files(target):
        for f in scan_file(path, rel_base=base):
            findings.append(
                f"{f.path}:{f.line}:{f.test_name}:{f.vacuous_class}:{f.detail}"
            )
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "roots",
        nargs="*",
        default=["tools/vacuous-test-detector/fixtures"],
        help="Paths to scan (default: fixture corpus)",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON report on stdout")
    ap.add_argument(
        "--out",
        type=Path,
        help="Write JSON report to this path",
    )
    args = ap.parse_args(argv)
    roots = [Path(r) for r in args.roots]
    report = scan_roots(roots)
    payload = report.to_dict()
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    if args.json or args.out:
        if args.json:
            sys.stdout.write(text)
    else:
        print(
            f"files={report.files_scanned} tests={report.tests_scanned} "
            f"vacuous_tests={report.vacuous_test_count} "
            f"headline_cov={report.headline_coverage_pct}% "
            f"excl_vacuous={report.coverage_excluding_vacuous_pct}%"
        )
        for k, v in report.class_counts.items():
            print(f"  {k}: {v}")
        for f in report.findings:
            print(f"  {f.loc()} {f.test_name} [{f.vacuous_class}] {f.detail}")
    # Exit 0 always for report mode; gate callers inspect counts.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
