#!/usr/bin/env python3
"""Suppressed-failure census: regex surfaces plus Python AST for except:pass.

Live tree scan skips this unit's own probe dir so detector strings are not
counted as uses (catalog use-vs-mention control). JUSTIFIED requires a
documented reason AND an expiry; otherwise UNACCOUNTED.
"""
from __future__ import annotations

import ast
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

SKIP_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
    }
)
SKIP_SUFFIX = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".woff",
        ".woff2",
        ".pdf",
        ".zip",
        ".gz",
        ".whl",
    }
)
MAX_BYTES = 2_000_000
SHELL_EXT = frozenset({".yml", ".yaml", ".sh", ".bash", ".zsh", ".ps1", ".psm1"})
YAML_EXT = frozenset({".yml", ".yaml"})
PS_EXT = frozenset({".ps1", ".psm1"})
PY_EXT = frozenset({".py"})

OR_TRUE_RE = re.compile(r"(?:\|\|\s*true\b|\|\|\s*:)")
CONTINUE_ON_ERROR_RE = re.compile(
    r"(?m)^[ \t]*continue-on-error:[ \t]*(true|True|yes|on)\b"
)
SILENTLY_RE = re.compile(
    r"(?i)(?:-ErrorAction|-EA)\s+SilentlyContinue|"
    r"\$ErrorActionPreference\s*=\s*['\"]SilentlyContinue['\"]"
)
EXIT_ZERO_RE = re.compile(r"(?i)--exit-zero\b|--exitzero\b|--exit_zero\b")
STDERR_RE = re.compile(r"2>\s*/dev/null|2>\s*\$null\b")
SKIP_MARK_RE = re.compile(
    r"pytest\.mark\.(skip(?:if)?|xfail)\b|@unittest\.skip(?:If|Unless)?\b"
)
EXPIRY_RE = re.compile(
    r"(?i)\b(?:expir(?:y|es|ation)|sunset)\s*[:=]\s*\S+"
    r"|\buntil\s+\d{4}-\d{2}-\d{2}"
    r"|\bremove[- ]after\b[^\n]{0,40}"
    r"|\b\d{4}-\d{2}-\d{2}\b"
)
DECORATIVE_RE = re.compile(
    r"(?i)^(best effort|legacy|n/?a|ignore|don't care|dont care|decorative|todo)\b"
)
FALSIFIABLE_RE = re.compile(
    r"(?i)\b(?:until|when|if|because|until\s+\d{4}|issue|bug|ci job|windows|"
    r"crlf|tracked|#\d+|expires?)\b|\d{4}-\d{2}-\d{2}"
)
OWN_UNIT_PARTS = ("command-center", "p2-wave", "probes", "BLD-0023")
MENTION_DOC_EXT = frozenset({".md", ".rst", ".txt"})


@dataclass
class Finding:
    path: str
    line: int
    construct: str
    snippet: str
    surrounding: str
    classification: str
    reason: str | None
    expiry: str | None
    surface: str
    detector: str

    def as_row(self, fid: str) -> dict:
        d = asdict(self)
        d["id"] = fid
        d["summary"] = (
            f"{self.construct} at {self.path}:{self.line} "
            f"class={self.classification}"
        )
        return d


def _rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_own_unit(root: Path, path: Path) -> bool:
    parts = Path(_rel(root, path)).parts
    return parts[:4] == OWN_UNIT_PARTS


def iter_files(root: Path, skip_own_unit: bool = True) -> Iterator[Path]:
    root = root.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        if skip_own_unit and _is_own_unit(root, p):
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield p


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _snippet(lines: list[str], idx: int) -> str:
    if idx < 0 or idx >= len(lines):
        return ""
    s = lines[idx].rstrip()
    return s[:240]


def _surrounding(lines: list[str], idx: int, radius: int = 2) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    return "\n".join(lines[lo:hi])[:800]


def _comment_window(lines: list[str], idx: int, end_idx: int | None = None) -> str:
    bits: list[str] = []
    last = idx if end_idx is None else max(idx, end_idx)
    for k in range(idx, min(last + 1, len(lines))):
        same = lines[k]
        if "#" in same:
            bits.append(same.split("#", 1)[1].strip())
    j = idx - 1
    seen = 0
    while j >= 0 and seen < 8:
        raw = lines[j].strip()
        if not raw:
            j -= 1
            continue
        if raw.startswith("#"):
            bits.append(raw.lstrip("# ").strip())
            seen += 1
            j -= 1
            continue
        break
    return "\n".join(reversed(bits))


def classify_from_comments(comment_text: str) -> tuple[str, str | None, str | None]:
    text = (comment_text or "").strip()
    expiry = None
    m = EXPIRY_RE.search(text)
    if m:
        expiry = m.group(0).strip()[:80]
    reason = text if text and not DECORATIVE_RE.match(text) else (text or None)
    if text and DECORATIVE_RE.match(text.split("\n")[-1].strip()):
        reason = text
    if reason and expiry:
        return "JUSTIFIED", reason[:400], expiry
    if not reason:
        reason = None
    return "UNACCOUNTED", reason, expiry


def reason_is_falsifiable(reason: str | None) -> bool:
    if not reason or not reason.strip():
        return False
    if DECORATIVE_RE.match(reason.strip()):
        return False
    return bool(FALSIFIABLE_RE.search(reason))


def _add(
    out: list[Finding],
    *,
    rel: str,
    line: int,
    construct: str,
    snippet: str,
    surrounding: str,
    comments: str,
    surface: str,
    detector: str,
) -> None:
    klass, reason, expiry = classify_from_comments(comments)
    out.append(
        Finding(
            path=rel,
            line=line,
            construct=construct,
            snippet=snippet,
            surrounding=surrounding,
            classification=klass,
            reason=reason,
            expiry=expiry,
            surface=surface,
            detector=detector,
        )
    )


def scan_python_ast(root: Path, path: Path) -> list[Finding]:
    rel = _rel(root, path)
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    lines = src.splitlines()
    found: list[Finding] = []

    class V(ast.NodeVisitor):
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            body = node.body or []
            if not body or not all(isinstance(n, ast.Pass) for n in body):
                self.generic_visit(node)
                return
            construct = None
            if node.type is None:
                construct = "bare-except-pass"
            elif isinstance(node.type, ast.Name) and node.type.id in {
                "Exception",
                "BaseException",
            }:
                construct = "bare-except-pass"
            if construct:
                idx = max(0, int(node.lineno) - 1)
                end = max(int(n.lineno) for n in body) - 1
                _add(
                    found,
                    rel=rel,
                    line=int(node.lineno),
                    construct=construct,
                    snippet=_snippet(lines, idx),
                    surrounding=_surrounding(lines, idx),
                    comments=_comment_window(lines, idx, end),
                    surface="python",
                    detector="ast",
                )
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            name = _call_name(node)
            if name in {"warnings.filterwarnings", "warnings.simplefilter"}:
                idx = max(0, int(node.lineno) - 1)
                _add(
                    found,
                    rel=rel,
                    line=int(node.lineno),
                    construct="warning-filter",
                    snippet=_snippet(lines, idx),
                    surrounding=_surrounding(lines, idx),
                    comments=_comment_window(lines, idx),
                    surface="python",
                    detector="ast",
                )
            self.generic_visit(node)

    V().visit(tree)
    return found


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    if isinstance(func, ast.Name):
        return func.id
    return ""


def scan_text_regex(root: Path, path: Path) -> list[Finding]:
    rel = _rel(root, path)
    suffix = path.suffix.lower()
    if suffix in MENTION_DOC_EXT:
        return []
    try:
        lines = _lines(path)
    except OSError:
        return []
    found: list[Finding] = []
    text_join = "\n".join(lines)

    def hit(i: int, construct: str, surface: str) -> None:
        _add(
            found,
            rel=rel,
            line=i + 1,
            construct=construct,
            snippet=_snippet(lines, i),
            surrounding=_surrounding(lines, i),
            comments=_comment_window(lines, i),
            surface=surface,
            detector="regex",
        )

    if suffix in YAML_EXT:
        for m in CONTINUE_ON_ERROR_RE.finditer(text_join):
            i = text_join[: m.start()].count("\n")
            if _line_is_comment(lines, i):
                continue
            hit(i, "continue-on-error", "yaml")
    if suffix in SHELL_EXT or suffix in YAML_EXT:
        for i, line in enumerate(lines):
            if _line_is_comment(lines, i):
                continue
            if OR_TRUE_RE.search(line):
                hit(i, "or-true", "shell" if suffix not in YAML_EXT else "yaml")
            if STDERR_RE.search(line):
                hit(i, "stderr-redirect", "shell" if suffix not in YAML_EXT else "yaml")
            if EXIT_ZERO_RE.search(line):
                hit(i, "exit-zero-flag", "shell" if suffix not in YAML_EXT else "yaml")
    if suffix in PS_EXT:
        for i, line in enumerate(lines):
            if _line_is_comment(lines, i, ps=True):
                continue
            if SILENTLY_RE.search(line):
                hit(i, "erroraction-silentlycontinue", "powershell")
    return found


def scan_skip_markers(root: Path, path: Path) -> list[Finding]:
    """AUD-0055 owns skip/xfail reason validity. Record hits as deferred."""
    if path.suffix.lower() != ".py":
        return []
    rel = _rel(root, path)
    try:
        lines = _lines(path)
    except OSError:
        return []
    found: list[Finding] = []
    for i, line in enumerate(lines):
        if _line_is_comment(lines, i):
            continue
        if SKIP_MARK_RE.search(line):
            found.append(
                Finding(
                    path=rel,
                    line=i + 1,
                    construct="skip-or-xfail",
                    snippet=_snippet(lines, i),
                    surrounding=_surrounding(lines, i),
                    classification="DEFERRED-AUD-0055",
                    reason="owned by AUD-0055 skip/xfail reason census",
                    expiry=None,
                    surface="python-test",
                    detector="regex",
                )
            )
    return found


def _line_is_comment(lines: list[str], i: int, ps: bool = False) -> bool:
    if i < 0 or i >= len(lines):
        return True
    s = lines[i].lstrip()
    if not s:
        return True
    if s.startswith("#"):
        return True
    if ps and s.startswith((";", "<#")):
        return True
    return False


def scan_tree(
    root: Path,
    *,
    skip_own_unit: bool = True,
    include_deferred_skip: bool = False,
) -> list[Finding]:
    root = root.resolve()
    out: list[Finding] = []
    for path in iter_files(root, skip_own_unit=skip_own_unit):
        suffix = path.suffix.lower()
        if suffix in PY_EXT:
            out.extend(scan_python_ast(root, path))
            if include_deferred_skip:
                out.extend(scan_skip_markers(root, path))
        if suffix in SHELL_EXT or suffix in YAML_EXT or suffix in PS_EXT:
            out.extend(scan_text_regex(root, path))
    out.sort(key=lambda f: (f.path, f.line, f.construct))
    return out


def scan_paths(root: Path, paths: Iterable[Path]) -> list[Finding]:
    root = root.resolve()
    out: list[Finding] = []
    for path in paths:
        path = path.resolve()
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in PY_EXT:
            out.extend(scan_python_ast(root, path))
        if suffix in SHELL_EXT or suffix in YAML_EXT or suffix in PS_EXT:
            out.extend(scan_text_regex(root, path))
        if suffix in MENTION_DOC_EXT:
            out.extend(scan_text_regex(root, path))
    out.sort(key=lambda f: (f.path, f.line, f.construct))
    return out


def counts(findings: list[Finding]) -> dict:
    by_construct: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for f in findings:
        by_construct[f.construct] = by_construct.get(f.construct, 0) + 1
        by_class[f.classification] = by_class.get(f.classification, 0) + 1
    return {
        "total": len(findings),
        "by_construct": by_construct,
        "by_classification": by_class,
    }
