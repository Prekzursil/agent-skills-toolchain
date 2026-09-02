"""Bare M-NN extractor with mechanical namespace verdicts. Guessing is banned."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from namespaces import holders

TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])M-(\d{1,2})(?!\d)")
FENCE_RE = re.compile(r"^```")
DISCRIMINATORS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"option-universe", re.I), "option-universe"),
    (re.compile(r"\boption\b", re.I), "option-universe"),
    (re.compile(r"\bmechanism\b", re.I), "architecture-mech"),
    (re.compile(r"\bMECH\b"), "architecture-mech"),
    (re.compile(r"\bharness\b", re.I), "wave3-deep-research"),
    (re.compile(r"mission[-\s]grade", re.I), "wave1-register"),
]
WINDOW = 100


def _strip_inline_ticks(line: str) -> str:
    chars = list(line)
    in_tick = False
    for i, ch in enumerate(chars):
        if ch == "`":
            in_tick = not in_tick
            chars[i] = " "
            continue
        if in_tick:
            chars[i] = " "
    return "".join(chars)


def _mention_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(">") and "collision" in stripped.lower():
        return True
    return False


def extract_path(path: Path, *, rel: str | None = None) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return extract_text(text, rel or path.as_posix())


def extract_text(text: str, rel: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_fence = False
    for line_no, raw in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(raw.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _mention_line(raw):
            continue
        line = _strip_inline_ticks(raw)
        for match in TOKEN_RE.finditer(line):
            number = int(match.group(1))
            start = max(0, match.start() - WINDOW)
            end = min(len(line), match.end() + WINDOW)
            window = line[start:end]
            rows.append(_verdict(rel, line_no, number, window, match.group(0)))
    return rows


def _verdict(
    rel: str, line_no: int, number: int, window: str, raw_token: str
) -> dict[str, Any]:
    token = f"M-{number}"
    holding = holders(number)
    hits: list[str] = []
    for pattern, ns in DISCRIMINATORS:
        if pattern.search(window) and ns in holding and ns not in hits:
            hits.append(ns)
    if len(hits) == 1:
        verdict = "RESOLVES-ONE"
        resolved = hits[0]
    elif len(hits) > 1:
        verdict = "RESOLVES-MANY"
        resolved = None
    elif len(holding) == 1:
        verdict = "RESOLVES-ONE"
        resolved = holding[0]
    elif len(holding) == 0:
        verdict = "RESOLVES-NONE"
        resolved = None
    else:
        verdict = "UNDECIDABLE"
        resolved = None
    row: dict[str, Any] = {
        "token": token,
        "token_number": number,
        "raw_token": raw_token,
        "path": rel,
        "line": line_no,
        "verdict": verdict,
        "candidate_namespaces": holding,
        "discriminators": hits,
        "window": window,
    }
    if resolved is not None:
        row["resolved_namespace"] = resolved
    return row


def extract_tree(paths: list[Path], *, root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
        rows.extend(extract_path(path, rel=rel))
    return rows
