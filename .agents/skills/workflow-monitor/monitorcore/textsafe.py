"""Pure text-safety helpers for the wfmon export renderers.

Every function here is a total, side-effect-free ``str -> str`` (or ``str -> str`` fence)
transform: no filesystem, no globals, no optional deps. They are the last mile before user
transcript content lands in a Markdown fence or an HTML node, and are applied *in the render
path* (not merely unit-tested):

    strip_ansi   -> drop terminal control sequences
    html_escape  -> neutralise the five HTML meta-characters
    safe_fence   -> pick a backtick run that can never be closed early by the content
    truncate_block / cap_artifact -> bound size with a byte-accurate, UTF-8-safe marker
    elide_base64 -> replace embedded image/blob payloads with a short byte-count marker

Byte-oriented operations slice on UTF-8 character boundaries so a truncated block is always
valid text (a multibyte code point is never cut in half).
"""

from __future__ import annotations

import re

__all__ = [
    "strip_ansi",
    "html_escape",
    "safe_fence",
    "truncate_block",
    "cap_artifact",
    "elide_base64",
    "TOOL_OUTPUT_CAP",
]

# Per-artifact UTF-8 byte cap for a single content block before ``truncate_block`` collapses
# the middle to a head + a byte-offset marker + a tail. The SINGLE source of truth for this
# cap: the Markdown/HTML renderers re-export it and the cockpit's Task/Result panes reuse it
# (was formerly duplicated ×3 as separate ``= 8000`` literals).
TOOL_OUTPUT_CAP = 8000

# ECMA-48: a CSI sequence (ESC [ params intermediates final) tried first, else a two-byte
# escape (ESC + any final byte 0x30-0x7E, e.g. ESC c reset, ESC = keypad).
_ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|[0-~])")

# Longest run of backticks -- used to size a fence that the content cannot close early.
_BACKTICK_RUN_RE = re.compile(r"`+")

# A ``data:<mime>;base64,<payload>`` URI. Group 1 is the base64 payload we elide.
_DATA_URI_RE = re.compile(r"data:[\w.+/-]*;base64,([A-Za-z0-9+/]+={0,2})")

# A long standalone base64-ish run (after data URIs are already elided). The 200-char floor
# keeps ordinary prose, hex, and short identifiers from ever matching.
_B64_RUN_RE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")


def strip_ansi(s: str) -> str:
    """Remove ANSI/VT control sequences (CSI colour, cursor, erase; single-char escapes)."""
    return _ANSI_RE.sub("", s)


def html_escape(s: str) -> str:
    """Escape ``& < > " '`` for safe embedding in HTML text or attribute context.

    ``&`` is escaped first so an already-escaped entity is never double-escaped.
    """
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def safe_fence(s: str) -> str:
    """Return a Markdown code fence delimiter guaranteed to survive ``s``.

    The delimiter is a run of backticks one longer than the longest backtick run inside
    ``s`` (minimum three), so the content can never terminate the fence prematurely.
    """
    longest = 0
    for m in _BACKTICK_RUN_RE.finditer(s):
        longest = max(longest, len(m.group()))
    return "`" * max(3, longest + 1)


def _head_boundary(raw: bytes, n: int) -> int:
    """Largest index <= ``n`` that starts a UTF-8 character (not a continuation byte)."""
    n = min(n, len(raw))
    while n > 0 and (raw[n] if n < len(raw) else 0) & 0xC0 == 0x80:
        n -= 1
    return n


def _tail_boundary(raw: bytes, start: int) -> int:
    """Smallest index >= ``start`` that starts a UTF-8 character (not a continuation byte)."""
    while start < len(raw) and raw[start] & 0xC0 == 0x80:
        start += 1
    return start


def truncate_block(s: str, cap: int, *, head: int = 2000, tail: int = 800) -> str:
    """Collapse an oversized block to ``head`` + a byte-offset marker + ``tail`` bytes.

    Sizes are measured in UTF-8 bytes. If ``s`` is at or under ``cap`` bytes it is returned
    unchanged. Head and tail cuts back off to the nearest character boundary so the result
    is always valid text. If ``head`` + ``tail`` already cover the whole block (nothing left
    to elide), ``s`` is returned unchanged.
    """
    raw = s.encode("utf-8")
    n = len(raw)
    if n <= cap:
        return s
    h = _head_boundary(raw, head)
    t_start = _tail_boundary(raw, max(h, n - tail))
    elided = n - h - (n - t_start)
    if elided <= 0:
        return s
    offset = h
    return (
        raw[:h].decode("utf-8")
        + f"\n...[{elided} bytes elided @{offset}]...\n"
        + raw[t_start:].decode("utf-8")
    )


def cap_artifact(s: str, cap: int) -> str:
    """Hard-cap ``s`` to ``cap`` UTF-8 bytes, appending a ``[N bytes elided]`` marker.

    UTF-8-safe: the cut backs off to a character boundary. Identity at or under ``cap``.
    """
    raw = s.encode("utf-8")
    n = len(raw)
    if n <= cap:
        return s
    h = _head_boundary(raw, cap)
    elided = n - h
    return raw[:h].decode("utf-8") + f"\n[{elided} bytes elided]"


def elide_base64(s: str) -> str:
    """Replace ``data:...;base64,`` URIs and long base64 runs with a byte-count marker."""

    def _data_repl(m: re.Match[str]) -> str:
        return f"<base64 image elided {len(m.group(1))} bytes>"

    def _run_repl(m: re.Match[str]) -> str:
        return f"<base64 image elided {len(m.group(0))} bytes>"

    s = _DATA_URI_RE.sub(_data_repl, s)
    return _B64_RUN_RE.sub(_run_repl, s)
