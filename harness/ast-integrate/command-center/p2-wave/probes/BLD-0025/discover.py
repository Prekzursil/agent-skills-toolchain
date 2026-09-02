"""AST census of retry/backoff sites + catalog retry_policy + B08/B09 log presence."""
from __future__ import annotations

import ast
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCAN_RELS = [
    "tools/command-center",
    "command-center/p2-wave/seed-stage",
    "command-center/p2-wave/_measure_one_delivered.py",
    "command-center/p2-wave/_p2lib.py",
    "command-center/p2-wave/_probe_delivered.py",
    "command-center/ready_units.py",
]
SKIP_DIRS = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "probes",
}
NAME_RE = re.compile(r"retry|backoff|max_attempts|TWO_STRIKES|rerun|re-poll", re.I)
B08_CANDIDATES = [
    "coverage.xml",
    "command-center/receipts/B08.json",
    "command-center/_baseline_tests_out.json",
    "command-center/BASELINE-SNAPSHOT.json",
    "command-center/p2-wave/B08.log",
    "command-center/p2-wave/pytest-B08.xml",
]
B09_CANDIDATES = [
    "command-center/receipts/B09.json",
    "command-center/p2-wave/B09.log",
    "command-center/p2-wave/pytest-B09.xml",
]


def _py_files(repo: Path) -> list[Path]:
    out: list[Path] = []
    for rel in SCAN_RELS:
        p = repo / rel
        if p.is_file() and p.suffix == ".py":
            out.append(p)
            continue
        if p.is_dir():
            for child in p.rglob("*.py"):
                if any(part in SKIP_DIRS for part in child.parts):
                    continue
                out.append(child)
    return sorted(set(out))


def _has_continue(node: ast.AST) -> bool:
    return any(isinstance(n, ast.Continue) for n in ast.walk(node))


def _try_except_continue(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Try):
            for h in n.handlers:
                if _has_continue(h) or _has_continue(n):
                    return True
            if _has_continue(n):
                return True
    return False


def _has_sleep(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            func = n.func
            if isinstance(func, ast.Attribute) and func.attr == "sleep":
                return True
            if isinstance(func, ast.Name) and func.id == "sleep":
                return True
    return False


def _rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def scan_python(repo: Path) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for path in _py_files(repo):
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            hits.append(
                {
                    "path": _rel(repo, path),
                    "line": getattr(exc, "lineno", 1) or 1,
                    "kind": "syntax-error",
                    "name": "",
                    "has_try_continue": False,
                    "has_sleep": False,
                }
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if NAME_RE.search(node.name):
                    hits.append(
                        {
                            "path": _rel(repo, path),
                            "line": node.lineno,
                            "kind": "retry-named-fn",
                            "name": node.name,
                            "has_try_continue": _try_except_continue(node),
                            "has_sleep": _has_sleep(node),
                        }
                    )
            if isinstance(node, ast.For):
                if _try_except_continue(node) or (
                    _has_sleep(node) and NAME_RE.search(ast.dump(node)[:400])
                ):
                    hits.append(
                        {
                            "path": _rel(repo, path),
                            "line": node.lineno,
                            "kind": "for-retry-loop",
                            "name": "",
                            "has_try_continue": _try_except_continue(node),
                            "has_sleep": _has_sleep(node),
                        }
                    )
            if isinstance(node, ast.While):
                if _try_except_continue(node) or _has_sleep(node):
                    hits.append(
                        {
                            "path": _rel(repo, path),
                            "line": node.lineno,
                            "kind": "while-retry-or-poll",
                            "name": "",
                            "has_try_continue": _try_except_continue(node),
                            "has_sleep": _has_sleep(node),
                        }
                    )
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "TWO_STRIKES":
                        hits.append(
                            {
                                "path": _rel(repo, path),
                                "line": node.lineno,
                                "kind": "two-strikes-const",
                                "name": "TWO_STRIKES",
                                "has_try_continue": False,
                                "has_sleep": False,
                            }
                        )
    # de-dup same path:line:kind
    seen: set[tuple] = set()
    unique: list[dict[str, Any]] = []
    for h in hits:
        key = (h["path"], h["line"], h["kind"], h.get("name"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
    return unique


def policy_class(text: str) -> str:
    t = (text or "").lower()
    if "must not retry its own instrumentation" in t or "not retried into a pass" in t:
        return "self-no-silent-retry"
    if "no automatic retry" in t or "no blind retry" in t:
        return "no-automatic-retry"
    if "mechanically different" in t:
        return "mechanically-different-probe"
    if "429" in t or "529" in t or "staggered" in t:
        return "staggered-vendor-429"
    if "two strikes" in t:
        return "two-strikes-pivot"
    if not t.strip():
        return "empty"
    return "other"


def catalog_census(repo: Path) -> dict[str, Any]:
    cat_path = repo / "command-center/WORK-UNIT-CATALOG.json"
    data = json.loads(cat_path.read_text(encoding="utf-8"))
    units = data.get("work_units") or []
    classes: Counter[str] = Counter()
    samples: dict[str, str] = {}
    bld0025 = None
    n = 0
    for u in units:
        if not isinstance(u, dict):
            continue
        pol = str(u.get("retry_policy") or "")
        n += 1
        cls = policy_class(pol)
        classes[cls] += 1
        samples.setdefault(cls, pol[:240])
        if u.get("id") == "BLD-0025":
            bld0025 = pol
    return {
        "units_with_retry_policy_field": n,
        "class_counts": dict(sorted(classes.items(), key=lambda kv: (-kv[1], kv[0]))),
        "class_samples": samples,
        "bld0025_retry_policy": bld0025 or "",
        "executable_binding": False,
        "note": (
            "retry_policy is catalog prose. No runner reads the field to drive "
            "HTTP backoff, pytest reruns, or strike counting. Unobservable as a class."
        ),
    }


def missing_logs(repo: Path) -> dict[str, Any]:
    def check(cands: list[str]) -> dict[str, Any]:
        rows = []
        found = False
        for rel in cands:
            p = repo / rel
            rows.append({"path": rel, "present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0})
            found = found or p.is_file()
        return {"present": found, "searched": rows}

    return {"B08": check(B08_CANDIDATES), "B09": check(B09_CANDIDATES)}
