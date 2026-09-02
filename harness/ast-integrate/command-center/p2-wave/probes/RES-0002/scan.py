"""Two independent locators for a comparison that maps HTTP 200 to FAILED.

Signal A: line-window regex over hook-shaped source.
Signal B: ast.walk Compare/Return (Python only) — not a second regex.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from constants import (
    FIXTURES,
    HERE,
    HOOK_SUFFIXES,
    LIVE_SCAN_SKIP_PREFIXES,
    REPO,
    SKIP_DIR_NAMES,
    STATUS_NAMES,
)

EQ_200 = re.compile(
    r"if\s+(?:\w+\.)*?(status(?:_code)?|http_status|httpStatus)\s*==\s*200\b"
)
FAILED_TOKEN = re.compile(r"\bFAILED\b")
RETURN_STATUS = re.compile(r"\b(?:return|sys\.exit|process\.exit)\(\s*status\w*\s*\)|\breturn\s+status\b")


def rel_or_abs(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(path)


def skip_live(path: Path) -> bool:
    rel = rel_or_abs(path)
    return any(rel.startswith(prefix) for prefix in LIVE_SCAN_SKIP_PREFIXES)


def hook_shaped(text: str) -> bool:
    lowered = text.lower()
    stdinish = "sys.stdin" in lowered or "stdin" in lowered
    toolish = (
        "tool_response" in lowered
        or "posttooluse" in lowered
        or "tool_name" in lowered
        or "hook_event" in lowered
    )
    return stdinish and toolish


def _if_body_has_failed(lines: list[str], start: int) -> bool:
    if_line = lines[start]
    indent = len(if_line) - len(if_line.lstrip(" "))
    for line in lines[start + 1 :]:
        if not line.strip():
            continue
        cur = len(line) - len(line.lstrip(" "))
        if cur <= indent:
            break
        if FAILED_TOKEN.search(line):
            return True
    return False


def regex_hits(path: Path, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    hits: list[dict[str, Any]] = []
    if not hook_shaped(text):
        return hits
    for idx, line in enumerate(lines):
        if EQ_200.search(line) and _if_body_has_failed(lines, idx):
            hits.append(
                {
                    "signal": "regex",
                    "kind": "eq-200-failed",
                    "path": rel_or_abs(path),
                    "line": idx + 1,
                    "snippet": line.strip()[:160],
                }
            )
        if RETURN_STATUS.search(line) and FAILED_TOKEN.search(text):
            # status-as-exit only if the file treats non-zero HTTP as FAILED
            if "status != 0" in text or "status !=0" in text or "sys.exit(status" in text:
                hits.append(
                    {
                        "signal": "regex",
                        "kind": "status-as-exit",
                        "path": rel_or_abs(path),
                        "line": idx + 1,
                        "snippet": line.strip()[:160],
                    }
                )
    return hits


def _const_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _writes_token(body: list[ast.stmt], token: str) -> bool:
    for node in body:
        for child in ast.walk(node):
            if _const_str(child) == token:
                return True
    return False


def _returns_nonzero(body: list[ast.stmt]) -> bool:
    for node in body:
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            if node.value.value not in (0, None, False):
                return True
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            if node.value.id in STATUS_NAMES or node.value.id == "status":
                return True
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Call)
                and isinstance(child.func, ast.Attribute)
                and child.func.attr == "exit"
            ):
                if child.args and isinstance(child.args[0], ast.Constant):
                    if child.args[0].value not in (0, None):
                        return True
                if child.args and isinstance(child.args[0], ast.Name):
                    return True
    return False


def _returns_zero(body: list[ast.stmt]) -> bool:
    for node in body:
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant):
            if node.value.value in (0, None):
                return True
    return False


def _is_eq_200(test: ast.AST) -> bool:
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    nodes = [test.left, *test.comparators]
    has_200 = any(
        isinstance(n, ast.Constant) and n.value == 200 for n in nodes
    )
    has_other = any(
        not (isinstance(n, ast.Constant) and n.value == 200) for n in nodes
    )
    return has_200 and has_other


def ast_hits(path: Path, text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if path.suffix.lower() != ".py":
        return hits
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return hits
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_eq_200(node.test):
            if _writes_token(node.body, "FAILED") and _returns_nonzero(node.body):
                hits.append(
                    {
                        "signal": "ast",
                        "kind": "eq-200-failed",
                        "path": rel_or_abs(path),
                        "line": int(getattr(node, "lineno", 1)),
                        "snippet": ast.get_source_segment(text, node.test) or "status == 200",
                    }
                )
            elif _writes_token(node.body, "OK") and _returns_zero(node.body):
                hits.append(
                    {
                        "signal": "ast",
                        "kind": "eq-200-ok",
                        "path": rel_or_abs(path),
                        "line": int(getattr(node, "lineno", 1)),
                        "snippet": ast.get_source_segment(text, node.test) or "status == 200",
                    }
                )
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Name):
            if node.value.id in STATUS_NAMES or node.value.id == "status":
                if "FAILED" in text and hook_shaped(text):
                    hits.append(
                        {
                            "signal": "ast",
                            "kind": "status-as-exit",
                            "path": rel_or_abs(path),
                            "line": int(getattr(node, "lineno", 1)),
                            "snippet": ast.get_source_segment(text, node) or "return status",
                        }
                    )
    return hits


def scan_file(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"path": rel_or_abs(path), "error": str(exc), "regex": [], "ast": []}
    return {
        "path": rel_or_abs(path),
        "hook_shaped": hook_shaped(text),
        "regex": regex_hits(path, text),
        "ast": ast_hits(path, text),
    }


def inversion_hits(result: dict[str, Any]) -> list[dict[str, Any]]:
    kinds = {"eq-200-failed", "status-as-exit"}
    out = []
    for hit in list(result.get("regex") or []) + list(result.get("ast") or []):
        if hit.get("kind") in kinds:
            out.append(hit)
    return out


def iter_source_files(root: Path):
    if root.is_file():
        yield root
        return
    if not root.is_dir():
        return
    for dirpath, dirnames, filenames in os_walk_sorted(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in HOOK_SUFFIXES:
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
            except OSError:
                continue
            yield path


def os_walk_sorted(root: Path):
    import os

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        yield dirpath, dirnames, filenames


def scan_roots(roots: list[Path], skip_self: bool) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for root in roots:
        for path in iter_source_files(root):
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            seen.add(key)
            if skip_self and skip_live(path):
                continue
            rows.append(scan_file(path))
    return rows


def fixture_controls() -> dict[str, Any]:
    mapping = {
        "inverted_status_as_exit": FIXTURES / "inverted_status_as_exit.py",
        "inverted_eq_200": FIXTURES / "inverted_eq_200.py",
        "correct_http": FIXTURES / "correct_http.py",
        "noop": FIXTURES / "noop.py",
    }
    out = {}
    for name, path in mapping.items():
        scanned = scan_file(path)
        inv = inversion_hits(scanned)
        regex_inv = [h for h in inv if h.get("signal") == "regex"]
        ast_inv = [h for h in inv if h.get("signal") == "ast"]
        out[name] = {
            "path": rel_or_abs(path),
            "exists": path.is_file(),
            "inversion_hit": bool(inv),
            "regex_hit": bool(regex_inv),
            "ast_hit": bool(ast_inv),
            "hits": inv,
            "ok_hits": [h for h in scanned.get("ast") or [] if h.get("kind") == "eq-200-ok"],
        }
    return out


def live_scan() -> dict[str, Any]:
    from estate import candidate_roots

    roots = [REPO, Path.home() / ".claude", *candidate_roots()]
    rows = scan_roots(roots, skip_self=True)
    inversions = []
    for row in rows:
        for hit in inversion_hits(row):
            inversions.append(hit)
    inversions.sort(key=lambda h: (h.get("path") or "", h.get("line") or 0, h.get("signal") or ""))
    return {
        "files_scanned": len(rows),
        "inversion_hits": inversions,
        "hit_count": len(inversions),
    }


def marker_line(path: Path, marker: str = "INVERSION-COMPARE") -> int | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for idx, line in enumerate(lines, 1):
        if marker in line:
            return idx
    return None
