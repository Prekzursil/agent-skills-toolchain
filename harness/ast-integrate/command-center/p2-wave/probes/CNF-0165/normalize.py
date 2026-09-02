"""Named normalizers for CNF-0165 command-replay diffs.

Every varying region that a future diff is allowed to ignore must have a
name. An unclassified nondeterminism is a silent hole. Over-normalization
is tested by planting a real content change that must survive.
"""
from __future__ import annotations

import re
from typing import Callable

# ISO-8601 timestamps (with optional fractional seconds and Z/offset).
_ISO8601 = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
# Unix seconds in the 2016–2033 window only. Must NOT swallow 19-digit ns.
_UNIX_S = re.compile(r"\b1[6-9]\d{8}\b")
_TMP = re.compile(
    r"(?:/tmp/|/var/folders/|/var/tmp/|C:\\Users\\[^\\]+\\AppData\\Local\\Temp\\)[A-Za-z0-9._/-]+"
)
_PID = re.compile(r"\b(?:pid|PID)[=: ]+\d+\b")
_HOST = re.compile(r"\b(?:host(?:name)?|HOST)[=: ]+\S+")
_TRAIL = re.compile(r"[ \t]+$", flags=re.MULTILINE)


def eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def trailing_ws(text: str) -> str:
    body = _TRAIL.sub("", text)
    return body.strip("\n") + ("\n" if body.endswith("\n") or body else "")


def iso8601_timestamp(text: str) -> str:
    return _ISO8601.sub("<TS>", text)


def unix_seconds(text: str) -> str:
    return _UNIX_S.sub("<UNIX_S>", text)


def tmp_path(text: str) -> str:
    return _TMP.sub("<TMP>", text)


def pid(text: str) -> str:
    return _PID.sub("pid=<PID>", text)


def hostname_field(text: str) -> str:
    return _HOST.sub("host=<HOST>", text)


NORMALIZERS: list[tuple[str, Callable[[str], str]]] = [
    ("eol", eol),
    ("trailing_ws", trailing_ws),
    ("iso8601_timestamp", iso8601_timestamp),
    ("unix_seconds", unix_seconds),
    ("tmp_path", tmp_path),
    ("pid", pid),
    ("hostname_field", hostname_field),
]


def apply(text: str | None) -> tuple[str, list[str]]:
    """Return (normalized_text, names that actually changed the bytes)."""
    if text is None:
        return "", []
    cur = text
    used: list[str] = []
    for name, fn in NORMALIZERS:
        nxt = fn(cur)
        if nxt != cur:
            used.append(name)
            cur = nxt
    return cur, used


def names() -> list[str]:
    return [n for n, _ in NORMALIZERS]
