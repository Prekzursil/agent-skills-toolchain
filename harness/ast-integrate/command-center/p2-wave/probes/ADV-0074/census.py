"""Probe 2 instrument: which git/forge fields production templates interpolate."""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any, Iterable

from common import (
    CENSUS_ROOTS,
    CENSUS_SKIP_PARTS,
    CENSUS_SUFFIXES,
    FIELD_IDS,
    PLACEHOLDER_ALIASES,
    REPO,
)

MAX_BYTES = 400_000


def _skip(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        rel = str(path)
    blob = "/" + rel
    for part in CENSUS_SKIP_PARTS:
        if part in blob or rel.endswith(part.lstrip("/")):
            return True
    return False


def _iter_files() -> Iterable[Path]:
    for root_name in CENSUS_ROOTS:
        root = REPO / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in CENSUS_SUFFIXES:
                continue
            if _skip(path):
                continue
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _alias_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for field, aliases in PLACEHOLDER_ALIASES.items():
        for alias in aliases:
            out[alias] = field
            out[alias.lower()] = field
    return out


ALIAS_TO_FIELD = _alias_map()
PLACEHOLDER_RE = re.compile(
    r"\{+\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}+"
)
PERCENT_RE = re.compile(
    r"%\(([A-Za-z_][A-Za-z0-9_]*)\)s"
)
GIT_FORMAT_RE = re.compile(
    r"git(?:\s+|.*?)\b(?:log|show|tag)\b[^\"'\n]{0,80}--format=[^\n]*?%(B|s|N|b)\b"
)


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def hits_in_text(text: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {fid: [] for fid in FIELD_IDS}
    for match in PLACEHOLDER_RE.finditer(text):
        name = match.group(1)
        field = ALIAS_TO_FIELD.get(name) or ALIAS_TO_FIELD.get(name.lower())
        if field:
            found[field].append(f"placeholder:{{{name}}}")
    for match in PERCENT_RE.finditer(text):
        name = match.group(1)
        field = ALIAS_TO_FIELD.get(name) or ALIAS_TO_FIELD.get(name.lower())
        if field:
            found[field].append(f"percent:({name})")
    return found


def hits_in_python(text: str) -> dict[str, list[str]]:
    found = hits_in_text(text)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found

    class Visitor(ast.NodeVisitor):
        def visit_Name(self, node: ast.Name) -> None:
            field = ALIAS_TO_FIELD.get(node.id) or ALIAS_TO_FIELD.get(node.id.lower())
            if field and isinstance(node.ctx, ast.Load):
                # Only count names inside f-strings / format calls, not every mention.
                pass
            self.generic_visit(node)

        def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
            for part in node.values:
                if isinstance(part, ast.FormattedValue):
                    _mark_expr(part.value)
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            is_format = isinstance(func, ast.Attribute) and func.attr == "format"
            if is_format:
                for kw in node.keywords:
                    if kw.arg:
                        field = ALIAS_TO_FIELD.get(kw.arg) or ALIAS_TO_FIELD.get(kw.arg.lower())
                        if field:
                            found[field].append(f"str.format:{kw.arg}")
            self.generic_visit(node)

    def _mark_expr(expr: ast.AST) -> None:
        if isinstance(expr, ast.Name):
            field = ALIAS_TO_FIELD.get(expr.id) or ALIAS_TO_FIELD.get(expr.id.lower())
            if field:
                found[field].append(f"f-string:{expr.id}")
        elif isinstance(expr, ast.Attribute):
            field = ALIAS_TO_FIELD.get(expr.attr) or ALIAS_TO_FIELD.get(expr.attr.lower())
            if field:
                found[field].append(f"f-string-attr:{expr.attr}")

    Visitor().visit(tree)
    return found


def census_file(path: Path) -> dict[str, list[str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {fid: [] for fid in FIELD_IDS}
    if path.suffix.lower() == ".py":
        return hits_in_python(text)
    return hits_in_text(text)


def production_census() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    interpolated: dict[str, list[dict[str, str]]] = {fid: [] for fid in FIELD_IDS}
    scanned = 0
    for path in _iter_files():
        scanned += 1
        hits = census_file(path)
        rel = _rel(path)
        any_hit = False
        for field, reasons in hits.items():
            if reasons:
                any_hit = True
                interpolated[field].append(
                    {"path": rel, "reason": reasons[0], "n_reasons": str(len(reasons))}
                )
        if any_hit:
            rows.append({"path": rel, "hits": {k: v for k, v in hits.items() if v}})
    return {
        "scanned_files": scanned,
        "interpolated": interpolated,
        "rows": rows,
        "fields_in_templates": sorted(
            fid for fid, hits in interpolated.items() if hits
        ),
        "fields_absent_from_templates": sorted(
            fid for fid, hits in interpolated.items() if not hits
        ),
    }
