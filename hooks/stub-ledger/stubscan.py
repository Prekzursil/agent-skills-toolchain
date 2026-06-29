#!/usr/bin/env python3
"""stub-ledger/stubscan.py — shared placeholder/stub scanner (stdlib-only).

find_stubs(text) -> list[(marker, line_no, snippet)] for the high-signal placeholder
shapes an agent leaves behind: comment tags (TODO/FIXME/HACK/XXX/STUB), NotImplemented,
"implement later" / "not implemented" / "coming soon" / "TBD" phrases, pass-only / ...-only
function bodies, and the weak words placeholder/stub/unimplemented in a comment.

Used by BOTH record.py (scan written content) and report.py (re-scan current files to
confirm a recorded stub is STILL open). Kept tight to avoid flagging prose that merely
mentions the word "stub".
"""
from __future__ import annotations

import re

_COMMENT_TAG = re.compile(r"(?:#|//|/\*|<!--|;|^\s*\*)\s*(TODO|FIXME|HACK|XXX|STUB)\b(?![-\w])", re.IGNORECASE | re.MULTILINE)
_NOTIMPL = re.compile(r"NotImplementedError|raise\s+NotImplemented\b|\bNotImplemented\b")
_PHRASE = re.compile(
    r"implement(?:ed|ation)?\s+(?:this\s+|it\s+)?later"
    r"|wire\s+(?:this\s+|it\s+|them\s+)?(?:up\s+)?later"
    r"|not\s+(?:yet\s+)?implemented|coming\s+soon"
    r"|to\s+be\s+(?:implemented|done|added|written|filled\s+in)"
    r"|\bTBD\b|fill\s+(?:this\s+)?in\s+later|for\s+now,?\s+(?:just\s+)?(?:return|pass)",
    re.IGNORECASE,
)
_COMMENT_INTRO = re.compile(r"(?:#|//|/\*|<!--|^\s*\*)")
# (?![-\w]) so a COMPOUND identifier that merely contains the word is NOT a stub:
# "stub-ledger", "stub_file", "stubscan", "placeholder_path" -> ignored; bare "stub"/"placeholder" -> flagged.
_WEAK = re.compile(r"\b(placeholder|stub|unimplemented)\b(?![-\w])", re.IGNORECASE)

# def name(...):  [-> type]:  then (optional docstring) then pass / ...  (single-line signature)
_PASS_BODY = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+(\w+)[ \t]*\([^)]*\)[ \t]*(?:->[^\n:]+)?:[ \t]*(?:#[^\n]*)?\n"
    r"(?:[ \t]*(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?''')[ \t]*\n)?"
    r"[ \t]*(?:pass|\.\.\.)[ \t]*(?:#[^\n]*)?(?:\n|$)",
    re.MULTILINE,
)


_TEST_FILE = re.compile(
    r"(?:^|[\\/])(?:test_[^\\/]+|conftest)\.py$|_test\.py$|\.test\.[jt]sx?$"
    r"|[\\/](?:tests?|__tests__|scratchpad)[\\/]",
    re.IGNORECASE,
)


def is_test_file(path: str) -> bool:
    """True for test/fixture files, which legitimately CONTAIN stub/TODO markers (a
    stub-detector's own tests MUST) — callers skip them so fixtures are never flagged
    as incomplete production code."""
    return bool(path) and bool(_TEST_FILE.search(str(path).replace("\\", "/")))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_stubs(text: str) -> list[tuple[str, int, str]]:
    """Return deduped (marker, line_no, snippet) tuples. Stdlib-only, bounded."""
    if not text:
        return []
    out: list[tuple[str, int, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(marker: str, line_no: int, snippet: str):
        snip = _norm(snippet)[:120]
        key = (marker.upper(), snip.lower())
        if key in seen or not snip:
            return
        seen.add(key)
        out.append((marker.upper(), line_no, snip))

    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        for m in _COMMENT_TAG.finditer(line):
            add(m.group(1), i, line)
        if _NOTIMPL.search(line):
            add("NotImplemented", i, line)
        if _PHRASE.search(line):
            add("placeholder-phrase", i, line)
        if _COMMENT_INTRO.search(line) and _WEAK.search(line):
            add(_WEAK.search(line).group(1), i, line)

    for m in _PASS_BODY.finditer(text):
        line_no = text.count("\n", 0, m.start()) + 1
        header = text[m.start():m.end()].splitlines()[0]
        add("pass-only-body", line_no, header)

    out.sort(key=lambda t: t[1])
    return out[:50]


if __name__ == "__main__":  # tiny self-check
    sample = (
        "def foo(x):\n    pass\n\n"
        "# TODO: handle the edge case\n"
        "def bar():\n    raise NotImplementedError('later')\n"
        "value = 1  # placeholder until wired\n"
        "const x = 2; // coming soon\n"
    )
    for mk, ln, sn in find_stubs(sample):
        print(f"{ln}: [{mk}] {sn}")
