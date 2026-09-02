"""Token-level JSON key inventory (TST-0182 signal b).

``json.loads`` builds a ``dict`` while it parses, so a repeated member is
collapsed last-wins before any caller can see it.  This module scans the JSON
*source text* with its own tokenizer and recursive-descent walker.  It never
constructs a dict for an object: every member is recorded as a separate
:class:`KeyOccurrence` with the JSONPath of the object that owns it, so the
count of a key at a path is the number of times the key is written in the
text, and duplicates keep both values in document order.

The scanner is deliberately independent of :mod:`json` and of
:mod:`plugin.strict_json` so that it can act as a second signal next to the
validator error.

Paths use a small JSONPath dialect: ``$`` is the root object, ``$.author`` the
object stored under the member ``author``, ``$.plugins[0]`` the first array
element, and keys that are not identifiers are bracketed as ``$["odd key"]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

__all__ = [
    "KeyOccurrence",
    "KeyScan",
    "KeyScanError",
    "ROOT_PATH",
    "child_path",
    "count_key_occurrences",
    "scan_keys",
]

ROOT_PATH = "$"
_WHITESPACE = " \t\n\r"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")
_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
}


class KeyScanError(ValueError):
    """Raised when the text is not well-formed JSON at the token level."""

    def __init__(self, message: str, *, line: int, column: int) -> None:
        super().__init__(f"{message} at {line}:{column}")
        self.line = int(line)
        self.column = int(column)


def child_path(parent: str, key: str) -> str:
    """Return the JSONPath of the member ``key`` inside the object at ``parent``."""
    if _IDENT.match(key):
        return f"{parent}.{key}"
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'{parent}["{escaped}"]'


def _index_path(parent: str, index: int) -> str:
    return f"{parent}[{index}]"


@dataclass(frozen=True)
class KeyOccurrence:
    """One written object member.

    ``value`` is the decoded scalar for strings, numbers, ``true``/``false``/
    ``null``; for object and array values it is the raw source slice so the
    inventory never has to collapse a nested object into a dict.
    """

    path: str
    key: str
    value: Any
    value_kind: str
    ordinal: int
    line: int
    column: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "key": self.key,
            "value": self.value,
            "value_kind": self.value_kind,
            "ordinal": self.ordinal,
            "line": self.line,
            "column": self.column,
        }


@dataclass
class KeyScan:
    """Inventory of every object member written in a JSON text."""

    occurrences: list[KeyOccurrence] = field(default_factory=list)
    source_length: int = 0
    root_kind: str = ""

    def __iter__(self) -> Iterator[KeyOccurrence]:
        return iter(self.occurrences)

    def __len__(self) -> int:
        return len(self.occurrences)

    def at(self, path: str = ROOT_PATH) -> list[KeyOccurrence]:
        """Members written directly inside the object at ``path``, in order."""
        return [occ for occ in self.occurrences if occ.path == path]

    def paths(self) -> list[str]:
        """Every object path that owns at least one member, in first-seen order."""
        seen: dict[str, None] = {}
        for occ in self.occurrences:
            seen.setdefault(occ.path, None)
        return list(seen)

    def counts_at(self, path: str = ROOT_PATH) -> dict[str, int]:
        """Key -> number of times it is written inside the object at ``path``."""
        counts: dict[str, int] = {}
        for occ in self.at(path):
            counts[occ.key] = counts.get(occ.key, 0) + 1
        return counts

    def count(self, key: str, path: str | None = None) -> int:
        """Occurrences of ``key`` at ``path`` (or across the whole text)."""
        return sum(
            1
            for occ in self.occurrences
            if occ.key == key and (path is None or occ.path == path)
        )

    def values_at(self, path: str, key: str) -> list[Any]:
        """Every value written for ``key`` inside ``path``, in document order."""
        return [occ.value for occ in self.at(path) if occ.key == key]

    def duplicate_keys(self) -> list[dict[str, Any]]:
        """Keys written more than once in the same object.

        Each row carries ``path``, ``key``, ``count`` and the ordered ``values``.
        """
        rows: list[dict[str, Any]] = []
        for path in self.paths():
            for key, n in self.counts_at(path).items():
                if n > 1:
                    rows.append(
                        {
                            "path": path,
                            "key": key,
                            "count": n,
                            "values": self.values_at(path, key),
                        }
                    )
        return rows

    def has_duplicates(self) -> bool:
        return any(
            n > 1 for path in self.paths() for n in self.counts_at(path).values()
        )

    def total_members(self) -> int:
        return len(self.occurrences)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_kind": self.root_kind,
            "source_length": self.source_length,
            "total_members": self.total_members(),
            "paths": self.paths(),
            "duplicate_keys": self.duplicate_keys(),
            "occurrences": [occ.to_dict() for occ in self.occurrences],
        }


class _Scanner:
    """Recursive-descent walker over JSON source text (RFC 8259 grammar)."""

    def __init__(self, text: str, scan: KeyScan) -> None:
        self.text = text
        self.n = len(text)
        self.pos = 0
        self.scan = scan

    # -- position helpers -------------------------------------------------
    def _line_col(self, idx: int | None = None) -> tuple[int, int]:
        idx = self.pos if idx is None else idx
        line = self.text.count("\n", 0, idx) + 1
        last_nl = self.text.rfind("\n", 0, idx)
        return line, idx - last_nl

    def _error(self, message: str, idx: int | None = None) -> KeyScanError:
        line, col = self._line_col(idx)
        return KeyScanError(message, line=line, column=col)

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < self.n else ""

    def _skip_ws(self) -> None:
        while self.pos < self.n and self.text[self.pos] in _WHITESPACE:
            self.pos += 1

    def _expect(self, char: str) -> None:
        if self._peek() != char:
            got = self._peek() or "end of input"
            raise self._error(f"expected {char!r}, found {got!r}")
        self.pos += 1

    # -- grammar ------------------------------------------------------------
    def parse_document(self) -> str:
        self._skip_ws()
        if self.pos >= self.n:
            raise self._error("empty document")
        kind, _value = self.parse_value(ROOT_PATH)
        self._skip_ws()
        if self.pos != self.n:
            raise self._error("trailing characters after the root value")
        return kind

    def parse_value(self, path: str) -> tuple[str, Any]:
        """Return ``(kind, value)``; composites yield their raw source slice."""
        c = self._peek()
        if c == "{":
            start = self.pos
            self.parse_object(path)
            return "object", self.text[start : self.pos]
        if c == "[":
            start = self.pos
            self.parse_array(path)
            return "array", self.text[start : self.pos]
        if c == '"':
            return "string", self.parse_string()
        if c == "-" or c.isdigit():
            return "number", self.parse_number()
        for literal, value in (("true", True), ("false", False), ("null", None)):
            if self.text.startswith(literal, self.pos):
                self.pos += len(literal)
                return literal, value
        got = c or "end of input"
        raise self._error(f"unexpected token {got!r}")

    def parse_object(self, path: str) -> None:
        self._expect("{")
        self._skip_ws()
        if self._peek() == "}":
            self.pos += 1
            return
        ordinal = 0
        while True:
            self._skip_ws()
            if self._peek() != '"':
                got = self._peek() or "end of input"
                raise self._error(
                    f"object member must start with a string key, found {got!r}"
                )
            key_line, key_col = self._line_col()
            key = self.parse_string()
            self._skip_ws()
            self._expect(":")
            self._skip_ws()
            kind, value = self.parse_value(child_path(path, key))
            self.scan.occurrences.append(
                KeyOccurrence(
                    path=path,
                    key=key,
                    value=value,
                    value_kind=kind,
                    ordinal=ordinal,
                    line=key_line,
                    column=key_col,
                )
            )
            ordinal += 1
            self._skip_ws()
            c = self._peek()
            if c == ",":
                self.pos += 1
                self._skip_ws()
                if self._peek() == "}":
                    raise self._error("trailing comma before '}'")
                continue
            if c == "}":
                self.pos += 1
                return
            got = c or "end of input"
            raise self._error(
                f"expected ',' or '}}' after object member, found {got!r}"
            )

    def parse_array(self, path: str) -> None:
        self._expect("[")
        self._skip_ws()
        if self._peek() == "]":
            self.pos += 1
            return
        index = 0
        while True:
            self._skip_ws()
            self.parse_value(_index_path(path, index))
            index += 1
            self._skip_ws()
            c = self._peek()
            if c == ",":
                self.pos += 1
                self._skip_ws()
                if self._peek() == "]":
                    raise self._error("trailing comma before ']'")
                continue
            if c == "]":
                self.pos += 1
                return
            got = c or "end of input"
            raise self._error(f"expected ',' or ']' after array element, found {got!r}")

    def parse_string(self) -> str:
        start = self.pos
        self._expect('"')
        out: list[str] = []
        while True:
            if self.pos >= self.n:
                raise self._error("unterminated string", start)
            c = self.text[self.pos]
            if c == '"':
                self.pos += 1
                return "".join(out)
            if c == "\\":
                self.pos += 1
                if self.pos >= self.n:
                    raise self._error("unterminated escape", start)
                e = self.text[self.pos]
                if e in _ESCAPES:
                    out.append(_ESCAPES[e])
                    self.pos += 1
                    continue
                if e == "u":
                    out.append(self._parse_unicode_escape())
                    continue
                raise self._error(f"invalid escape '\\{e}'")
            if ord(c) < 0x20:
                raise self._error("control character inside string")
            out.append(c)
            self.pos += 1

    def _parse_unicode_escape(self) -> str:
        # self.pos points at the 'u'
        hex_digits = self.text[self.pos + 1 : self.pos + 5]
        if len(hex_digits) != 4 or any(
            h not in "0123456789abcdefABCDEF" for h in hex_digits
        ):
            raise self._error("invalid \\u escape")
        code = int(hex_digits, 16)
        self.pos += 5
        if 0xD800 <= code <= 0xDBFF and self.text.startswith("\\u", self.pos):
            low_digits = self.text[self.pos + 2 : self.pos + 6]
            if len(low_digits) == 4 and all(
                h in "0123456789abcdefABCDEF" for h in low_digits
            ):
                low = int(low_digits, 16)
                if 0xDC00 <= low <= 0xDFFF:
                    self.pos += 6
                    code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
        return chr(code)

    def parse_number(self) -> int | float:
        m = _NUMBER.match(self.text, self.pos)
        if not m or m.end() == self.pos:
            raise self._error("invalid number")
        raw = m.group(0)
        self.pos = m.end()
        if any(ch in raw for ch in ".eE"):
            return float(raw)
        return int(raw)


def _as_text(text: Any) -> str:
    if isinstance(text, (bytes, bytearray)):
        return bytes(text).decode("utf-8")
    return str(text)


def scan_keys(text: Any) -> KeyScan:
    """Inventory every object member written in ``text``.

    Raises :class:`KeyScanError` when the text is not well-formed JSON.
    """
    raw = _as_text(text)
    scan = KeyScan(source_length=len(raw))
    scan.root_kind = _Scanner(raw, scan).parse_document()
    return scan


def count_key_occurrences(text: Any, key: str, path: str | None = ROOT_PATH) -> int:
    """Number of times ``key`` is written inside the object at ``path``.

    ``path=None`` counts the key across every object in the document.
    """
    return scan_keys(text).count(key, path)
