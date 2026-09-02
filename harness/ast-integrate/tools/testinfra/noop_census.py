"""No-op test census (TST-0126): tests that cannot produce a red.

Three shapes, counted separately plus a union of node ids:
  - assertionless: no assert, no self.assert*, no pytest.raises
  - unconditional-skip: pytest.mark.skip, skipif(True), unittest.skip
  - always-xfail: pytest.mark.xfail with no/constant-true condition,
    unittest.expectedFailure

Conditional skips/xfails (skipif(False), runtime expressions, xfail(False),
conditional xfail) can still produce a red and must stay OUT of the buckets.
Method: AST static collection proxy — a helper asserting on the caller's
behalf is invisible to this census (declared residual unknown).
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

SHAPE_ALWAYS_XFAIL = "always-xfail"
SHAPE_ASSERTIONLESS = "assertionless"
SHAPE_UNCONDITIONAL_SKIP = "unconditional-skip"

METHOD = "ast-static-collection-proxy"

_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "_g1_file_to_pkg_bak"}


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _dotted(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _is_const(node: ast.AST | None, value: bool) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _skip_shape(dec: ast.expr) -> bool:
    """True for pytest.mark.skip(...), skipif(<constant True>), unittest.skip."""
    if isinstance(dec, ast.Call):
        name = _dotted(dec.func)
        base = name.rsplit(".", 1)[-1]
        if base == "skip":
            return True
        if base == "skipif":
            cond = dec.args[0] if dec.args else None
            if cond is None:
                for kw in dec.keywords:
                    if kw.arg == "condition":
                        cond = kw.value
            return _is_const(cond, True)
        return False
    base = _dotted(dec).rsplit(".", 1)[-1]
    return base == "skip"


def _xfail_shape(dec: ast.expr) -> bool:
    """True for xfail with no condition or a constant-true condition."""
    if isinstance(dec, ast.Call):
        base = _dotted(dec.func).rsplit(".", 1)[-1]
        if base != "xfail":
            return False
        cond = dec.args[0] if dec.args else None
        if cond is None:
            for kw in dec.keywords:
                if kw.arg == "condition":
                    cond = kw.value
        if cond is None:
            return True  # bare xfail(reason=...) always xfails
        return _is_const(cond, True)
    base = _dotted(dec).rsplit(".", 1)[-1]
    return base in {"xfail", "expectedFailure"}


def _has_assertion(fn: ast.AST) -> bool:
    for sub in ast.walk(fn):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Call):
            name = _dotted(sub.func)
            base = name.rsplit(".", 1)[-1]
            if base.startswith("assert") or base == "raises" or base == "fail":
                return True
        if isinstance(sub, ast.Raise):
            return True
    return False


def _shapes_for(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    shapes: list[str] = []
    if any(_skip_shape(d) for d in fn.decorator_list):
        shapes.append(SHAPE_UNCONDITIONAL_SKIP)
    if any(_xfail_shape(d) for d in fn.decorator_list):
        shapes.append(SHAPE_ALWAYS_XFAIL)
    if not _has_assertion(fn):
        shapes.append(SHAPE_ASSERTIONLESS)
    return shapes


def classify_module(source: str, rel: str = "<module>") -> list[dict[str, Any]]:
    """Rows for every test def in *source*: {"name", "node_id", "shapes"}."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    rows: list[dict[str, Any]] = []

    def visit(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test"):
                    node_id = f"{rel}::{prefix}{node.name}" if prefix else f"{rel}::{node.name}"
                    rows.append(
                        {"name": node.name, "node_id": node_id, "shapes": _shapes_for(node)}
                    )
            elif isinstance(node, ast.ClassDef):
                visit(node.body, f"{prefix}{node.name}::")

    visit(tree.body, "")
    return rows


def census_path(path: Path, rel: str | None = None) -> list[dict[str, Any]]:
    path = Path(path)
    return classify_module(
        path.read_text(encoding="utf-8", errors="replace"), rel or path.name
    )


def _bucketize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assertionless = sorted(r["node_id"] for r in rows if SHAPE_ASSERTIONLESS in r["shapes"])
    skips = sorted(r["node_id"] for r in rows if SHAPE_UNCONDITIONAL_SKIP in r["shapes"])
    xfails = sorted(r["node_id"] for r in rows if SHAPE_ALWAYS_XFAIL in r["shapes"])
    union = sorted(set(assertionless) | set(skips) | set(xfails))
    return {
        "assertionless": assertionless,
        "unconditional_skip": skips,
        "always_xfail": xfails,
        "union": union,
        "assertionless_count": len(assertionless),
        "unconditional_skip_count": len(skips),
        "always_xfail_count": len(xfails),
        "union_count": len(union),
        "tests_collected": len(rows),
    }


def _planted_dir(repo: Path) -> Path:
    return repo / "command-center" / "p2-wave" / "probes" / "TST-0126" / "fixtures"


def census_noop_tests(repo: Path) -> dict[str, Any]:
    """Live census over the repo's test files; planted fixtures kept separate."""
    repo = Path(repo)
    planted_dir = _planted_dir(repo)
    probes_root = repo / "command-center" / "p2-wave"

    live_rows: list[dict[str, Any]] = []
    parse_failures: list[str] = []
    files_scanned = 0
    for path in sorted(repo.rglob("test_*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        # probe fixtures and probe harnesses are not the live suite
        if probes_root in path.parents:
            continue
        rel = path.relative_to(repo).as_posix()
        files_scanned += 1
        try:
            rows = classify_module(path.read_text(encoding="utf-8", errors="replace"), rel)
        except Exception:
            parse_failures.append(rel)
            continue
        live_rows.extend(rows)

    planted_rows: list[dict[str, Any]] = []
    if planted_dir.is_dir():
        for path in sorted(planted_dir.glob("test_*.py")):
            rel = path.relative_to(repo).as_posix()
            planted_rows.extend(
                classify_module(path.read_text(encoding="utf-8", errors="replace"), rel)
            )

    return {
        "method": METHOD,
        "files_scanned": files_scanned,
        "parse_failures": parse_failures,
        "live": _bucketize(live_rows),
        "planted": _bucketize(planted_rows),
    }
