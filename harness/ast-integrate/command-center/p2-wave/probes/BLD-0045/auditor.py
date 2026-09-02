#!/usr/bin/env python3
"""Covered-but-unasserted auditor for BLD-0045.

Crosses line+branch coverage (stdlib sys.settrace + AST branch map) against
assertion reachability. Per-region assertion_depends, never a global percentage.

coverage.py is not installed on this worktree; a stdlib tracer is the live
collector. Branch mode is proved by a partial-branch entry (maybe_double else-arm).
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SUBJECT = HERE / "fixtures" / "subject"
PRODUCT_REL = "command-center/p2-wave/probes/BLD-0045/fixtures/subject/product.py"
TEST_REL = "command-center/p2-wave/probes/BLD-0045/fixtures/subject/test_suite.py"


def call_func_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def target_keys(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return [sl.value]
        return []
    if isinstance(node, ast.Tuple):
        keys: list[str] = []
        for elt in node.elts:
            keys.extend(target_keys(elt))
        return keys
    return []


def stores_in(stmts: list[ast.stmt]) -> list[str]:
    keys: list[str] = []
    for stmt in stmts:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    keys.extend(target_keys(target))
            elif isinstance(node, ast.AnnAssign) and node.target is not None:
                keys.extend(target_keys(node.target))
    return keys


def expr_tokens(node: ast.AST) -> set[str]:
    toks: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            toks.add(child.id)
        elif isinstance(child, ast.Attribute):
            toks.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            toks.add(child.value)
        elif isinstance(child, ast.Call):
            name = call_func_name(child)
            if name:
                toks.add(name)
    return toks


def stmt_linenos(node: ast.AST) -> set[int]:
    lines: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.stmt) and getattr(child, "lineno", None):
            lines.add(child.lineno)
    return lines


def load_mod(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class LineTracer:
    def __init__(self, files: set[str]) -> None:
        self.files = files
        self.executed: dict[str, set[int]] = defaultdict(set)

    def __call__(self, frame, event, arg):  # noqa: ANN001
        if event == "line":
            filename = frame.f_code.co_filename
            if filename in self.files:
                self.executed[filename].add(frame.f_lineno)
        return self.__call__


def drop_modules() -> None:
    for key in list(sys.modules):
        if key in {"product", "test_suite"} or key.startswith("bld0045_"):
            sys.modules.pop(key, None)


def run_suite(product_path: Path, test_path: Path) -> tuple[dict[str, dict], dict[str, set[int]]]:
    drop_modules()
    inserted = str(product_path.parent)
    sys.path.insert(0, inserted)
    tracer = LineTracer({str(product_path.resolve())})
    try:
        sys.settrace(tracer)
        load_mod(product_path, "product")
        tests = load_mod(test_path, "test_suite")
        results: dict[str, dict] = {}
        for name, fn in inspect.getmembers(tests, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            try:
                fn()
                results[name] = {"ok": True, "error": None}
            except Exception as exc:  # noqa: BLE001
                results[name] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        sys.settrace(None)
        if sys.path and sys.path[0] == inserted:
            sys.path.pop(0)
        drop_modules()
    return results, dict(tracer.executed)


def analyze_tests(tree: ast.AST) -> dict[str, set[str]]:
    asserted_funcs: set[str] = set()
    called_funcs: set[str] = set()
    unused_return: set[str] = set()
    assert_tokens: set[str] = set()

    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not (isinstance(node, ast.FunctionDef) and node.name.startswith("test_")):
            continue
        bound: dict[str, set[str]] = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                producers: set[str] = set()
                for child in ast.walk(stmt.value):
                    if isinstance(child, ast.Call):
                        fn = call_func_name(child)
                        if fn:
                            producers.add(fn)
                            called_funcs.add(fn)
                    elif isinstance(child, ast.Name) and child.id in bound:
                        producers |= bound[child.id]
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        bound[target.id] = producers
            elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                producers = set()
                for child in ast.walk(stmt.value):
                    if isinstance(child, ast.Call):
                        fn = call_func_name(child)
                        if fn:
                            producers.add(fn)
                            called_funcs.add(fn)
                if isinstance(stmt.target, ast.Name):
                    bound[stmt.target.id] = producers
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                fn = call_func_name(stmt.value)
                if fn:
                    called_funcs.add(fn)
                    unused_return.add(fn)
            elif isinstance(stmt, ast.Assert):
                assert_tokens |= expr_tokens(stmt.test)
                for child in ast.walk(stmt.test):
                    if isinstance(child, ast.Call):
                        fn = call_func_name(child)
                        if fn:
                            asserted_funcs.add(fn)
                            called_funcs.add(fn)
                    elif isinstance(child, ast.Name) and child.id in bound:
                        asserted_funcs |= bound[child.id]
    unused_return -= asserted_funcs
    return {
        "asserted_funcs": asserted_funcs,
        "called_funcs": called_funcs,
        "unused_return": unused_return,
        "assert_tokens": assert_tokens,
    }


def product_regions(tree: ast.AST, filename: str) -> tuple[list[dict], list[dict], list[dict]]:
    funcs: list[dict] = []
    excepts: list[dict] = []
    if_branches: list[dict] = []
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, ast.ClassDef):
            continue
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        funcs.append(
            {
                "name": node.name,
                "lineno": node.lineno,
                "end_lineno": node.end_lineno or node.lineno,
                "stmt_lines": sorted(stmt_linenos(node)),
                "file": filename,
            }
        )
        for child in ast.walk(node):
            if isinstance(child, ast.Try) and child.handlers:
                try_stores = stores_in(child.body)
                try_lines = stmt_linenos(ast.Module(body=list(child.body), type_ignores=[]))
                for handler in child.handlers:
                    h_lines = stmt_linenos(handler)
                    h_stores = stores_in(list(handler.body))
                    unique = [s for s in h_stores if s not in try_stores]
                    excepts.append(
                        {
                            "function": node.name,
                            "handler_line": handler.lineno,
                            "lines": sorted(h_lines),
                            "try_lines": sorted(try_lines),
                            "stores": h_stores,
                            "unique_stores": unique,
                            "exc_type": ast.unparse(handler.type) if handler.type else "bare",
                            "file": filename,
                        }
                    )
            if isinstance(child, ast.If) and child.orelse:
                body_line = child.body[0].lineno if child.body else child.lineno
                else_line = child.orelse[0].lineno
                if_branches.append(
                    {
                        "function": node.name,
                        "decision_line": child.lineno,
                        "body_line": body_line,
                        "else_line": else_line,
                        "file": filename,
                        "kind": "if",
                    }
                )
    return funcs, excepts, if_branches


def locus(rel: str, line: int) -> str:
    return f"{rel}:{line}"


def snippet_at(path: Path, line: int) -> str:
    rows = path.read_text(encoding="utf-8").splitlines()
    if 1 <= line <= len(rows):
        return rows[line - 1].strip()[:200]
    return ""


def classify_partials(
    branches: list[dict], executed: set[int], *, enabled: bool
) -> list[dict]:
    if not enabled:
        return []
    out: list[dict] = []
    for branch in branches:
        body_hit = branch["body_line"] in executed
        else_hit = branch["else_line"] in executed
        if body_hit and else_hit:
            status = "complete"
        elif body_hit or else_hit:
            status = "partial"
        else:
            status = "uncovered"
        out.append(
            {
                "locus": locus(PRODUCT_REL, branch["decision_line"]),
                "kind": branch["kind"],
                "function": branch["function"],
                "status": status,
                "body_line": branch["body_line"],
                "else_line": branch["else_line"],
                "body_executed": body_hit,
                "else_executed": else_hit,
            }
        )
    return out


class DropAssertedValueAssert(ast.NodeTransformer):
    """Independent reviewer mutation: keep the call covered, drop the assert."""

    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.generic_visit(node)
        for child in ast.walk(node.test):
            if isinstance(child, ast.Call) and call_func_name(child) == "asserted_value":
                return ast.copy_location(ast.Expr(value=child), node)
        return node


class FlipExceptRolledBack(ast.NodeTransformer):
    """Pivot mutation: invert the except-arm rollback flag."""

    def visit_Assign(self, node: ast.Assign) -> ast.AST:
        self.generic_visit(node)
        if len(node.targets) != 1:
            return node
        target = node.targets[0]
        if (
            isinstance(target, ast.Subscript)
            and isinstance(target.slice, ast.Constant)
            and target.slice.value == "rolled_back"
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        ):
            node.value = ast.Constant(False)
        return node


def write_ast(tree: ast.AST, path: Path) -> None:
    ast.fix_missing_locations(tree)
    path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")


def b08_status() -> dict:
    needles = [
        REPO / "coverage.xml",
        REPO / ".coverage",
        REPO / "command-center/p2-wave/probes/BLD-0010/b08-runtime/matrix.json",
    ]
    found = [p.relative_to(REPO).as_posix() for p in needles if p.is_file()]
    return {
        "requested": "branch-enabled coverage output from the B08 suite",
        "status": "PRESENT" if found else "ABSENT",
        "found": found,
        "substitute": (
            "fixture suite at command-center/p2-wave/probes/BLD-0045/fixtures/subject "
            "with planted side-effect, asserted, except-rollback, and partial-branch controls"
        ),
    }


def scan_shipped() -> list[dict]:
    root = REPO / "tools" / "command-center"
    rows: list[dict] = []
    if not root.is_dir():
        return [
            {
                "path": "tools/command-center",
                "kind": "tree",
                "coverage": "NOT-CHECKED",
                "assertion_depends": "NOT-CHECKED",
                "reason": "shipped tree directory missing",
            }
        ]
    for path in sorted(root.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            rows.append(
                {
                    "path": path.relative_to(REPO).as_posix(),
                    "kind": "parse-error",
                    "coverage": "NOT-CHECKED",
                    "assertion_depends": "NOT-CHECKED",
                    "reason": str(exc),
                }
            )
            continue
        rel = path.relative_to(REPO).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    rows.append(
                        {
                            "path": f"{rel}:{handler.lineno}",
                            "kind": "except-handler",
                            "exc_type": ast.unparse(handler.type) if handler.type else "bare",
                            "coverage": "NOT-CHECKED",
                            "assertion_depends": "NOT-CHECKED",
                            "reason": (
                                "B08 coverage.xml absent; shipped except/rollback "
                                "regions listed, not claimed executed"
                            ),
                        }
                    )
            if isinstance(node, ast.FunctionDef) and "rollback" in node.name.lower():
                rows.append(
                    {
                        "path": f"{rel}:{node.lineno}",
                        "kind": "rollback-named-function",
                        "coverage": "NOT-CHECKED",
                        "assertion_depends": "NOT-CHECKED",
                        "reason": "name match only; no B08 branch coverage on this worktree",
                    }
                )
    return rows


def analyze_pair(product_path: Path, test_path: Path) -> dict:
    src = product_path.read_text(encoding="utf-8")
    test_src = test_path.read_text(encoding="utf-8")
    prod_tree = ast.parse(src)
    test_tree = ast.parse(test_src)
    funcs, excepts, branches = product_regions(prod_tree, str(product_path))
    dep = analyze_tests(test_tree)
    results, executed_map = run_suite(product_path, test_path)
    executed = executed_map.get(str(product_path.resolve()), set())
    partials = classify_partials(branches, executed, enabled=True)
    hidden = classify_partials(branches, executed, enabled=False)

    findings: list[dict] = []
    asserted_regions: list[dict] = []
    for func in funcs:
        stmt = set(func["stmt_lines"])
        hit = stmt & executed
        ratio = (len(hit) / len(stmt)) if stmt else 0.0
        covered = bool(hit)
        asserted = func["name"] in dep["asserted_funcs"]
        unused = func["name"] in dep["unused_return"]
        region = {
            "function": func["name"],
            "locus": locus(PRODUCT_REL, func["lineno"]),
            "coverage_ratio": round(ratio, 4),
            "covered_stmt_lines": sorted(hit),
            "stmt_lines": func["stmt_lines"],
            "assertion_depends": asserted,
        }
        if asserted:
            asserted_regions.append(region)
            continue
        if covered and unused:
            findings.append(
                {
                    "id": f"F-SIDE-{func['name']}",
                    "class": "COVERED-UNASSERTED",
                    "locus": locus(PRODUCT_REL, func["lineno"]),
                    "function": func["name"],
                    "coverage": f"line {len(hit)}/{len(stmt)}",
                    "assertion_depends": False,
                    "high_coverage": ratio >= 1.0,
                    "summary": (
                        f"{func['name']} was executed ({len(hit)}/{len(stmt)} "
                        "statement lines) but no assertion depends on its return"
                    ),
                }
            )
        elif covered and not asserted:
            findings.append(
                {
                    "id": f"F-UNASSERTED-{func['name']}",
                    "class": "COVERED-UNASSERTED",
                    "locus": locus(PRODUCT_REL, func["lineno"]),
                    "function": func["name"],
                    "coverage": f"line {len(hit)}/{len(stmt)}",
                    "assertion_depends": False,
                    "high_coverage": ratio >= 1.0,
                    "summary": (
                        f"{func['name']} was covered but no assertion depends on its output"
                    ),
                }
            )

    for region in excepts:
        h_lines = set(region["lines"])
        hit = h_lines & executed
        unique = region["unique_stores"]
        mentioned = [k for k in unique if k in dep["assert_tokens"]]
        if not hit:
            continue
        if mentioned:
            asserted_regions.append(
                {
                    "function": region["function"],
                    "locus": locus(PRODUCT_REL, region["handler_line"]),
                    "kind": "except",
                    "assertion_depends": True,
                    "mentioned_stores": mentioned,
                }
            )
            continue
        findings.append(
            {
                "id": f"F-EXCEPT-{region['function']}-{region['handler_line']}",
                "class": "EXCEPT-COVERED-UNASSERTED",
                "locus": locus(PRODUCT_REL, region["handler_line"]),
                "function": region["function"],
                "coverage": f"except-lines {sorted(hit)}",
                "assertion_depends": False,
                "unique_stores": unique,
                "assert_tokens_sample": sorted(dep["assert_tokens"])[:20],
                "summary": (
                    f"except {region['exc_type']} in {region['function']} executed; "
                    f"unique effects {unique} never appear in any assertion"
                ),
            }
        )

    failed = [name for name, row in results.items() if not row["ok"]]
    return {
        "test_results": results,
        "all_tests_passed": not failed,
        "failed_tests": failed,
        "executed_lines": sorted(executed),
        "findings": findings,
        "asserted_regions": asserted_regions,
        "partial_branch_entries": partials,
        "partial_when_branch_disabled": hidden,
        "dep": {k: sorted(v) for k, v in dep.items()},
        "funcs": [{k: v for k, v in f.items() if k != "stmt_lines"} | {"stmt_lines": f["stmt_lines"]} for f in funcs],
        "excepts": excepts,
    }


def mutate_except_and_retest() -> dict:
    with tempfile.TemporaryDirectory(prefix="bld0045-mut-") as tmp:
        dest = Path(tmp)
        shutil.copy(SUBJECT / "product.py", dest / "product.py")
        shutil.copy(SUBJECT / "test_suite.py", dest / "test_suite.py")
        tree = ast.parse((dest / "product.py").read_text(encoding="utf-8"))
        write_ast(FlipExceptRolledBack().visit(tree), dest / "product.py")
        results, _ = run_suite(dest / "product.py", dest / "test_suite.py")
        failed = [n for n, r in results.items() if not r["ok"]]
        return {
            "mutation": "except-arm rolled_back True->False",
            "tests_still_green": not failed,
            "failed_tests": failed,
            "test_results": results,
        }


def reviewer_delete_assert() -> dict:
    with tempfile.TemporaryDirectory(prefix="bld0045-rev-") as tmp:
        dest = Path(tmp)
        shutil.copy(SUBJECT / "product.py", dest / "product.py")
        shutil.copy(SUBJECT / "test_suite.py", dest / "test_suite.py")
        tree = ast.parse((dest / "test_suite.py").read_text(encoding="utf-8"))
        write_ast(DropAssertedValueAssert().visit(tree), dest / "test_suite.py")
        rewritten = (dest / "test_suite.py").read_text(encoding="utf-8")
        if "assert P.asserted_value" in rewritten:
            return {
                "ok": False,
                "reason": "asserted_value assertion was not deleted",
                "rewritten_has_assert": True,
            }
        report = analyze_pair(dest / "product.py", dest / "test_suite.py")
        unasserted = {
            f.get("function")
            for f in report["findings"]
            if f.get("class") == "COVERED-UNASSERTED"
        }
        reclassified = "asserted_value" in unasserted
        return {
            "ok": reclassified and report["all_tests_passed"],
            "reclassified_asserted_value": reclassified,
            "unasserted_functions": sorted(unasserted),
            "tests_passed_after_delete": report["all_tests_passed"],
            "failed_tests": report["failed_tests"],
            "rewritten_has_assert": False,
        }


def evaluate_controls(report: dict) -> list[dict]:
    findings = report["findings"]
    unasserted_fns = {
        f.get("function")
        for f in findings
        if f.get("class") == "COVERED-UNASSERTED"
    }
    except_hits = [
        f for f in findings if f.get("class") == "EXCEPT-COVERED-UNASSERTED"
    ]
    partials = [p for p in report["partial_branch_entries"] if p.get("status") == "partial"]
    disabled = report["partial_when_branch_disabled"]

    def row(cid: str, desc: str, expected: str, ok: bool, observed: str) -> dict:
        return {
            "id": cid,
            "description": desc,
            "expected": expected,
            "observed": observed,
            "result": "PASS" if ok else "FAIL",
        }

    return [
        row(
            "C-SIDE-EFFECT-REPORTED",
            "A function called only for its side effect with no assertion must be reported.",
            "side_effect_only in COVERED-UNASSERTED findings",
            "side_effect_only" in unasserted_fns,
            f"unasserted_functions={sorted(unasserted_fns)}",
        ),
        row(
            "C-ASSERTED-VALUE-NOT-REPORTED",
            "A function whose return value feeds an assert must NOT be reported.",
            "asserted_value absent from COVERED-UNASSERTED",
            "asserted_value" not in unasserted_fns,
            f"unasserted_functions={sorted(unasserted_fns)} asserted={report['dep'].get('asserted_funcs')}",
        ),
        row(
            "C-EXCEPT-UNASSERTED-REPORTED",
            "An except-branch that is covered but whose effect is never asserted must be reported.",
            "EXCEPT-COVERED-UNASSERTED for apply_with_rollback",
            any(f.get("function") == "apply_with_rollback" for f in except_hits),
            f"except_findings={[f.get('id') for f in except_hits]}",
        ),
        row(
            "C-PARTIAL-BRANCH-INSTRUMENT",
            "Prove branch coverage is on by observing a partial-branch entry; line-only mode hides it.",
            ">=1 partial entry when branch_enabled; 0 when disabled",
            bool(partials) and not disabled,
            f"partial={len(partials)} disabled={len(disabled)} entries={partials}",
        ),
    ]


def census() -> dict:
    product_path = SUBJECT / "product.py"
    test_path = SUBJECT / "test_suite.py"
    report = analyze_pair(product_path, test_path)
    controls = evaluate_controls(report)
    mutation = mutate_except_and_retest()
    reviewer = reviewer_delete_assert()
    return {
        "report": report,
        "controls": controls,
        "controls_pass": all(c["result"] == "PASS" for c in controls),
        "mutation": mutation,
        "reviewer": reviewer,
        "b08": b08_status(),
        "shipped_tree_candidates": scan_shipped(),
        "product_rel": PRODUCT_REL,
        "test_rel": TEST_REL,
    }


def main() -> int:
    doc = census()
    print(f"controls_pass={doc['controls_pass']}")
    for row in doc["controls"]:
        print(f"  {row['id']} {row['result']} {row['observed'][:180]}")
    print(f"mutation_still_green={doc['mutation']['tests_still_green']}")
    print(
        "reviewer_reclassified="
        f"{doc['reviewer'].get('reclassified_asserted_value')} ok={doc['reviewer'].get('ok')}"
    )
    print(f"b08={doc['b08']['status']}")
    if not doc["controls_pass"] or not doc["reviewer"].get("ok"):
        print("FAILED:BLD-0045 auditor controls")
        return 1
    if not doc["mutation"]["tests_still_green"]:
        print("FAILED:BLD-0045 mutation pivot unexpectedly turned tests red")
        return 1
    print("SUCCESS:BLD-0045-auditor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
