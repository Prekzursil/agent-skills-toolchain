"""Context-aware path-token extractor.

Citations are taken from markdown code fences, inline backticks, markdown
link targets, and JSON string values. Prose is not a citation context: a
slash in a sentence is use-vs-mention, not a filesystem path.

A naive whole-file regex (extract_naive) is kept as the known-broken
detector so the control can fire on the bad state.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

PATH_TOKEN_RE = re.compile(
    r"(?:"
    r"(?:[A-Za-z]:[\\/](?:[^\\/:*?\"<>|\s]+[\\/])*[^\\/:*?\"<>|\s]+)"
    r"|(?:~(?:/[A-Za-z0-9_.-]+)+)"
    r"|(?:/(?:home|Users|opt|root|tmp|var|usr|etc|mnt)(?:/[A-Za-z0-9_.-]+)+)"
    r"|(?:(?:\./|\.\./)?(?:[A-Za-z0-9_.-]+/){1,}[A-Za-z0-9_.-]+)"
    r")"
)
FENCE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
TILDE_FENCE_RE = re.compile(r"~~~[^\n]*\n(.*?)~~~", re.S)
TICK_RE = re.compile(r"`([^`\n]{1,500})`")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
URL_RE = re.compile(r"https?://[^\s)\]\"']+", re.I)
EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")
EXT_ONLY_RE = re.compile(r"^\.[A-Za-z0-9]{1,8}$")
TRAIL_PUNCT_RE = re.compile(r"[.,;:)\]}>]+$")
DATE_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}")
SECRET_PREFIXES = ("sk-", "ghp_", "github_pat_", "xox", "glpat-", "crv1_", "AKIA")
KNOWN_ROOTS = frozenset(
    {
        "command-center",
        "tools",
        "blueprints",
        "platform",
        ".github",
        "ci",
        "docs",
        "tests",
        "agents",
        "skills",
        "hooks",
        "schema",
        "receipts",
        "audit",
        "confirmation",
        "research",
        "adversarial",
        "synthesis",
        "wfa",
        "phase3",
        "phase4",
        "config",
        "design",
        ".cursor",
        ".quality",
        "quality",
        "fixtures",
        "probes",
        "command-center",
    }
)
KNOWN_BASENAMES = frozenset(
    {
        "README",
        "README.md",
        "SKILL.md",
        "AGENTS.md",
        "CLAUDE.md",
        "Makefile",
        "LICENSE",
        "CHANGELOG.md",
        "RUNBOOK.md",
    }
)


def _clean_token(raw: str) -> str:
    tok = raw.strip().strip("\"'`")
    tok = TRAIL_PUNCT_RE.sub("", tok)
    tok = tok.replace("\\", "/")
    while "//" in tok:
        tok = tok.replace("//", "/")
    return tok


def looks_like_path(token: str) -> bool:
    tok = _clean_token(token)
    if not tok or len(tok) < 3 or len(tok) > 4096:
        return False
    if "://" in tok or tok.startswith("git@"):
        return False
    if tok.startswith("http:") or tok.startswith("https:"):
        return False
    if any(tok.startswith(p) for p in SECRET_PREFIXES):
        return False
    if " " in tok or "*" in tok or "<" in tok or ">" in tok:
        return False
    if DATE_RE.match(tok):
        return False
    if tok.startswith("--"):
        return False
    parts_raw = [p for p in tok.split("/") if p]
    if any(p == "..." or p.startswith("--") for p in parts_raw):
        return False
    if re.match(r"^[A-Za-z]:/", tok) or tok.startswith("~/") or (
        tok.startswith("/") and not tok.startswith("//")
    ):
        return "/" in tok[1:] or tok.startswith("~/")
    if "/" not in tok:
        return False
    parts = [p for p in tok.split("/") if p and p not in (".", "..")]
    if len(parts) < 2:
        return False
    if all(p.isdigit() for p in parts):
        return False
    if all(EXT_ONLY_RE.match(p) for p in parts):
        return False
    last = parts[-1]
    if EXT_RE.search(last):
        return True
    if parts[0] in KNOWN_ROOTS:
        return True
    if last in KNOWN_BASENAMES:
        return True
    if len(parts) >= 3:
        return True
    return False


def tokens_in(text: str) -> list[str]:
    masked = URL_RE.sub(" ", text or "")
    found: list[str] = []
    seen: set[str] = set()
    for m in PATH_TOKEN_RE.finditer(masked):
        tok = _clean_token(m.group(0))
        if not looks_like_path(tok):
            continue
        if tok not in seen:
            seen.add(tok)
            found.append(tok)
    return found


def _line_at(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _covered(index: int, spans: list[tuple[int, int]]) -> bool:
    for a, b in spans:
        if a <= index < b:
            return True
    return False


def extract_markdown(text: str, source: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fence_spans: list[tuple[int, int]] = []
    for cre in (FENCE_RE, TILDE_FENCE_RE):
        for m in cre.finditer(text):
            fence_spans.append((m.start(), m.end()))
            body = m.group(1)
            base = m.start(1)
            for tok in tokens_in(body):
                idx = body.find(tok) if tok in body else body.find(tok.replace("/", "\\"))
                line = _line_at(text, base + (idx if idx >= 0 else 0))
                rows.append(
                    {
                        "path": tok,
                        "file": source,
                        "line": line,
                        "kind": "fence",
                    }
                )
    for m in TICK_RE.finditer(text):
        if _covered(m.start(), fence_spans):
            continue
        inner = m.group(1)
        for tok in tokens_in(inner):
            rows.append(
                {
                    "path": tok,
                    "file": source,
                    "line": _line_at(text, m.start()),
                    "kind": "backtick",
                }
            )
    for m in LINK_RE.finditer(text):
        if _covered(m.start(), fence_spans):
            continue
        href = (m.group(1) or "").strip()
        if href.startswith("#") or href.startswith("mailto:"):
            continue
        if URL_RE.match(href):
            continue
        tok = _clean_token(href.split()[0] if href else "")
        if looks_like_path(tok):
            rows.append(
                {
                    "path": tok,
                    "file": source,
                    "line": _line_at(text, m.start()),
                    "kind": "md-link",
                }
            )
    return rows


def extract_naive(text: str, source: str) -> list[dict[str, Any]]:
    """Known-broken: whole-file regex, including prose slashes."""
    rows: list[dict[str, Any]] = []
    masked = URL_RE.sub(" ", text or "")
    for m in PATH_TOKEN_RE.finditer(masked):
        tok = _clean_token(m.group(0))
        if not looks_like_path(tok):
            continue
        rows.append(
            {
                "path": tok,
                "file": source,
                "line": _line_at(text, m.start()),
                "kind": "naive-whole-file",
            }
        )
    return rows


def _walk_json(obj: Any, source: str, rows: list[dict[str, Any]], loc: str) -> None:
    if isinstance(obj, str):
        if len(obj) > 800:
            return
        if any(obj.startswith(p) for p in SECRET_PREFIXES):
            return
        for tok in tokens_in(obj):
            rows.append(
                {
                    "path": tok,
                    "file": source,
                    "line": 1,
                    "kind": "json-string",
                    "json_path": loc,
                }
            )
        return
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_json(item, source, rows, f"{loc}[{i}]")
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            _walk_json(val, source, rows, f"{loc}.{key}")


def extract_json_text(text: str, source: str) -> list[dict[str, Any]]:
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []
    rows: list[dict[str, Any]] = []
    _walk_json(obj, source, rows, "$")
    return rows


def extract_file(path: Path, repo: Path, text: str) -> list[dict[str, Any]]:
    try:
        source = path.relative_to(repo).as_posix()
    except ValueError:
        source = str(path)
    suffix = path.suffix.lower()
    rows: list[dict[str, Any]] = []
    if suffix in {".md", ".markdown", ".mdc"}:
        rows.extend(extract_markdown(text, source))
        # JSON-shaped .md (design council receipts saved with .md suffix)
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            rows.extend(extract_json_text(text, source))
    elif suffix == ".json":
        rows.extend(extract_json_text(text, source))
        if not rows:
            # unparseable json: still take fenced/tick-like quoted strings
            rows.extend(extract_markdown(text, source))
    else:
        rows.extend(extract_markdown(text, source))
    return rows


def paths_of(rows: Iterable[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        p = str(row.get("path") or "")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out
