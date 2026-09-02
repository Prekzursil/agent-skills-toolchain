"""Strict JSON codec: RFC 8259 only. Trailing commas, comments, and NaN fail."""
from __future__ import annotations

import json
from typing import Any


class StrictJSONError(ValueError):
    """Raised when input is not RFC 8259 JSON."""

    def __init__(self, message: str, *, kind: str = "json", line: int = 1, column: int = 1) -> None:
        super().__init__(message)
        self.kind = kind
        self.line = int(line)
        self.column = int(column)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "line": self.line,
            "column": self.column,
            "message": str(self),
        }


class DuplicateKeyError(StrictJSONError):
    """Duplicate object keys are errors, never last-wins.

    The message names the key, the object path and BOTH competing values so
    the owner's first intent is never silently discarded.
    """

    def __init__(
        self,
        key: str,
        first: Any = None,
        second: Any = None,
        *,
        path: str = "$",
        line: int = 1,
        column: int = 1,
    ) -> None:
        super().__init__(
            f"duplicate key {key!r} at {path}: first={first!r} second={second!r}",
            kind="json",
            line=line,
            column=column,
        )
        self.key = key
        self.first = first
        self.second = second
        self.path = path

    @property
    def first_value(self) -> Any:
        """Value of the earlier member (owner intent)."""
        return self.first

    @property
    def second_value(self) -> Any:
        """Value of the later member (what last-wins would keep)."""
        return self.second

    def reports_both_values(self) -> bool:
        """True when the error text carries both competing values."""
        message = str(self)
        return repr(self.first) in message and repr(self.second) in message

    def to_dict(self) -> dict:
        out = super().to_dict()
        out.update({"key": self.key, "path": self.path, "first": self.first, "second": self.second})
        return out


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise DuplicateKeyError(key, out[key], value)
        out[key] = value
    return out


def loads_strict(text: Any, *args: Any, **kwargs: Any) -> Any:
    return parse_strict(text, *args, **kwargs)


def _pos(text: str, idx: int) -> tuple[int, int]:
    line = text.count("\n", 0, idx) + 1
    last = text.rfind("\n", 0, idx)
    col = idx - last
    return line, col


def locate_json5_isms(text: str) -> list[dict[str, Any]]:
    raw = str(text)
    hits: list[dict[str, Any]] = []
    i = 0
    n = len(raw)
    in_str = False
    quote = ""
    escape = False
    while i < n:
        c = raw[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_str = False
            i += 1
            continue
        if c in "'\"":
            in_str = True
            quote = c
            i += 1
            continue
        if c == "/" and i + 1 < n and raw[i + 1] == "/":
            line, col = _pos(raw, i)
            hits.append({"kind": "line-comment", "line": line, "column": col})
            nl = raw.find("\n", i)
            i = n if nl < 0 else nl
            continue
        if c == "/" and i + 1 < n and raw[i + 1] == "*":
            line, col = _pos(raw, i)
            hits.append({"kind": "block-comment", "line": line, "column": col})
            end = raw.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if c == "," :
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            if j < n and raw[j] in "}]":
                line, col = _pos(raw, i)
                hits.append({"kind": "trailing-comma", "line": line, "column": col})
        i += 1
    return hits


def strip_json5(text: str) -> str:
    raw = str(text)
    out: list[str] = []
    i = 0
    n = len(raw)
    in_str = False
    quote = ""
    escape = False
    while i < n:
        c = raw[i]
        if in_str:
            out.append(c)
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_str = False
            i += 1
            continue
        if c in "'\"":
            in_str = True
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and raw[i + 1] == "/":
            nl = raw.find("\n", i)
            i = n if nl < 0 else nl
            continue
        if c == "/" and i + 1 < n and raw[i + 1] == "*":
            end = raw.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if c == ",":
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            if j < n and raw[j] in "}]":
                i += 1
                continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_strict(text: Any, *args: Any, **kwargs: Any) -> Any:
    if isinstance(text, (bytes, bytearray)):
        raw = text.decode("utf-8")
    elif text is None and args:
        raw = args[0]
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        else:
            raw = str(raw)
    else:
        raw = str(text)
    hits = locate_json5_isms(raw)
    if hits:
        h = hits[0]
        raise StrictJSONError(
            f"json5 {h['kind']} at {h['line']}:{h['column']}",
            kind=str(h["kind"]),
            line=int(h["line"]),
            column=int(h["column"]),
        )
    try:
        return json.loads(raw, object_pairs_hook=_reject_duplicates)
    except DuplicateKeyError:
        raise
    except json.JSONDecodeError as exc:
        raise StrictJSONError(str(exc), kind="json", line=exc.lineno, column=exc.colno) from exc


def emit_strict(obj: Any, *args: Any, **kwargs: Any) -> str:
    return json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


__all__ = [
    "DuplicateKeyError",
    "StrictJSONError",
    "emit_strict",
    "loads_strict",
    "locate_json5_isms",
    "parse_strict",
    "strip_json5",
]
