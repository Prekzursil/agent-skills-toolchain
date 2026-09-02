"""Portable strict and lenient JSON parsers for TST-0121.

Strict path: json.loads (RFC 8259). Duplicate keys last-wins (CPython).
Lenient path: comments, trailing commas, and single-quoted strings are
tolerated; duplicate keys first-wins so a value disagreement is observable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParseOutcome:
    accepted: bool
    value: Any = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "value": self.value if self.accepted else None,
            "error": None if self.accepted else (self.error or "reject"),
        }


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def parse_strict(text: str) -> ParseOutcome:
    try:
        return ParseOutcome(True, json.loads(text), None)
    except Exception as exc:
        return ParseOutcome(False, None, f"{type(exc).__name__}: {exc}")


def _first_wins(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in pairs:
        if key not in out:
            out[key] = val
    return out


def _copy_double_quoted(src: str, i: int) -> tuple[str, int]:
    n = len(src)
    start = i
    i += 1
    while i < n:
        ch = src[i]
        if ch == "\\":
            if i + 1 >= n:
                raise ValueError("unterminated escape in double-quoted string")
            i += 2
            continue
        if ch == '"':
            return src[start : i + 1], i + 1
        if ch in "\n\r":
            raise ValueError("unterminated double-quoted string")
        i += 1
    raise ValueError("unterminated double-quoted string")


def _single_quoted_as_json(src: str, i: int) -> tuple[str, int]:
    n = len(src)
    i += 1
    chunks = ['"']
    while i < n:
        ch = src[i]
        if ch == "\\":
            if i + 1 >= n:
                raise ValueError("unterminated escape in single-quoted string")
            nxt = src[i + 1]
            if nxt == "'":
                chunks.append("'")
            elif nxt == '"':
                chunks.append('\\"')
            else:
                chunks.append("\\")
                chunks.append(nxt)
            i += 2
            continue
        if ch == "'":
            chunks.append('"')
            return "".join(chunks), i + 1
        if ch == '"':
            chunks.append('\\"')
            i += 1
            continue
        if ch in "\n\r":
            raise ValueError("unterminated single-quoted string")
        chunks.append(ch)
        i += 1
    raise ValueError("unterminated single-quoted string")


def strip_comments_and_single_quotes(src: str) -> str:
    n = len(src)
    i = 0
    out: list[str] = []
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == '"':
            piece, i = _copy_double_quoted(src, i)
            out.append(piece)
            continue
        if ch == "'":
            piece, i = _single_quoted_as_json(src, i)
            out.append(piece)
            continue
        if ch == "/" and nxt == "/":
            i += 2
            while i < n and src[i] not in "\n\r":
                i += 1
            continue
        if ch == "/" and nxt == "*":
            i += 2
            closed = False
            while i < n:
                if src[i] == "*" and i + 1 < n and src[i + 1] == "/":
                    i += 2
                    closed = True
                    break
                i += 1
            if not closed:
                raise ValueError("unterminated block comment")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def strip_trailing_commas(src: str) -> str:
    n = len(src)
    i = 0
    out: list[str] = []
    while i < n:
        ch = src[i]
        if ch == '"':
            piece, i = _copy_double_quoted(src, i)
            out.append(piece)
            continue
        if ch == ",":
            j = i + 1
            while j < n and src[j] in " \t\r\n":
                j += 1
            if j < n and src[j] in "}]":
                i += 1
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def lenient_normalize(text: str) -> str:
    return strip_trailing_commas(strip_comments_and_single_quotes(text))


def parse_lenient(text: str) -> ParseOutcome:
    try:
        normalized = lenient_normalize(text)
        value = json.loads(normalized, object_pairs_hook=_first_wins)
        return ParseOutcome(True, value, None)
    except Exception as exc:
        return ParseOutcome(False, None, f"{type(exc).__name__}: {exc}")


def classify(text: str) -> dict[str, Any]:
    """Return a finding dict, or accepted=agreeing with kind=None."""
    strict = parse_strict(text)
    lenient = parse_lenient(text)
    row: dict[str, Any] = {
        "input": text,
        "strict": strict.as_dict(),
        "lenient": lenient.as_dict(),
        "kind": None,
    }
    if strict.accepted != lenient.accepted:
        row["kind"] = "accept-reject"
        return row
    if strict.accepted and lenient.accepted:
        if canonical(strict.value) != canonical(lenient.value):
            row["kind"] = "value"
            return row
    return row


def is_disagreement(row: dict[str, Any]) -> bool:
    return row.get("kind") in {"accept-reject", "value"}
