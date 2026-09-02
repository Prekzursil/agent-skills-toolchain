"""Stdlib collector/runner: unittest trees plus live pytest-suite import attempts.

Does not require pytest. A missing pytest on the live command-center suite is a
collection_error, not a pass and not a failure.
"""
from __future__ import annotations

import ast
import importlib.util
import io
import subprocess
import sys
import traceback
import unittest
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_TESTS = REPO / "tools" / "command-center" / "tests"


def _nid(test: unittest.TestCase, filename: str) -> str:
    parts = test.id().split(".")
    if len(parts) >= 2:
        cls, method = parts[-2], parts[-1]
        return f"{filename}::{cls}::{method}"
    return f"{filename}::{test.id()}"


def _iter_tests(suite: unittest.TestSuite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def ast_test_ids(path: Path) -> list[str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    ids: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            ids.append(f"{path.name}::{node.name}")
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    ids.append(f"{path.name}::{node.name}::{item.name}")
    return ids


def _load_module(path: Path):
    name = f"cnf0051_{path.stem}_{abs(hash(str(path))) % 10_000_000}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run_unittest_tree(root: Path) -> list[dict[str, Any]]:
    """Collect and run every test_*.py under root. Syntax/import failures are collection_error."""
    members: list[dict[str, Any]] = []
    files = sorted(p for p in root.rglob("test_*.py") if p.is_file())
    if not files:
        raise FileNotFoundError(f"no test_*.py under {root}")
    loader = unittest.TestLoader()
    for path in files:
        try:
            mod = _load_module(path)
        except Exception as exc:
            diagnostic = f"{type(exc).__name__}: {exc}"
            try:
                ids = ast_test_ids(path)
            except SyntaxError:
                ids = [f"{path.name}::<collection>"]
            if not ids:
                ids = [f"{path.name}::<collection>"]
            for tid in ids:
                members.append(
                    {
                        "id": tid,
                        "outcome": "collection_error",
                        "diagnostic": diagnostic,
                    }
                )
            continue
        suite = loader.loadTestsFromModule(mod)
        tests = list(_iter_tests(suite))
        if not tests:
            members.append(
                {
                    "id": f"{path.name}::<collection>",
                    "outcome": "collection_error",
                    "diagnostic": "loader returned zero tests",
                }
            )
            continue
        buf = io.StringIO()
        runner = unittest.TextTestRunner(stream=buf, verbosity=0)
        result = runner.run(suite)
        failed_ids = {_nid(t, path.name) for t, _ in result.failures}
        error_ids = {_nid(t, path.name) for t, _ in result.errors}
        skipped_ids = {_nid(t, path.name) for t, _ in result.skipped}
        for test in tests:
            tid = _nid(test, path.name)
            if tid in failed_ids:
                outcome = "failed"
            elif tid in error_ids:
                outcome = "error"
            elif tid in skipped_ids:
                outcome = "skipped"
            else:
                outcome = "passed"
            members.append({"id": tid, "outcome": outcome})
    members.sort(key=lambda m: m["id"])
    return members


def attempt_pytest(tests_dir: Path) -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        str(tests_dir),
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "command": " ".join(cmd),
            "returncode": 124,
            "stderr_tail": "TIMEOUT",
        }
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    available = proc.returncode == 0 and "ModuleNotFoundError" not in text
    return {
        "available": available,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "stderr_tail": text[-1500:],
    }


def collect_live_suite(tests_dir: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    tests_dir = tests_dir or LIVE_TESTS
    pytest_meta = attempt_pytest(tests_dir)
    members: list[dict[str, Any]] = []
    files = sorted(p for p in tests_dir.glob("test_*.py") if p.is_file())
    import_diagnostics: list[dict[str, str]] = []
    for path in files:
        try:
            ids = ast_test_ids(path)
        except SyntaxError as exc:
            members.append(
                {
                    "id": f"{path.name}::<collection>",
                    "outcome": "collection_error",
                    "diagnostic": f"SyntaxError: {exc}",
                }
            )
            continue
        try:
            _load_module(path)
            diagnostic = (
                "imported without pytest runner; not executed"
                if pytest_meta["available"]
                else "ModuleNotFoundError: pytest (suite cannot collect)"
            )
        except Exception as exc:
            diagnostic = f"{type(exc).__name__}: {exc}"
            import_diagnostics.append({"path": path.name, "diagnostic": diagnostic})
        if not ids:
            ids = [f"{path.name}::<collection>"]
        for tid in ids:
            members.append(
                {
                    "id": f"live/{tid}",
                    "outcome": "collection_error",
                    "diagnostic": diagnostic,
                }
            )
    members.sort(key=lambda m: m["id"])
    meta = {
        "tests_dir": str(tests_dir.relative_to(REPO)).replace("\\", "/"),
        "pytest": pytest_meta,
        "files": [p.name for p in files],
        "import_diagnostics": import_diagnostics[:12],
        "classification": "collection-error",
        "note": (
            "A suite that cannot collect is not a suite that passed. "
            "Per-id rows are collection_error, not failed and not passed."
        ),
    }
    return members, meta


def domain_payload(doc: dict) -> dict:
    """Domain fields live under report (receipt_core additionalProperties is false)."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    out = dict(report)
    for key in ("before", "after", "controls", "symmetric_difference"):
        if key in doc and doc[key] is not None:
            out[key] = doc[key]
    return out


def format_exc() -> str:
    return traceback.format_exc()[-500:]
