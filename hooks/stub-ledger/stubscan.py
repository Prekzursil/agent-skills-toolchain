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
import sys
from pathlib import Path

_COMMENT_TAG = re.compile(
    r"(?:#|//|/\*|<!--|;|^\s*\*)\s*(TODO|FIXME|HACK|XXX|STUB)\b(?![-\w])",
    re.IGNORECASE | re.MULTILINE,
)
_NOTIMPL = re.compile(
    r"NotImplementedError|raise\s+NotImplemented\b|\bNotImplemented\b"
)
_PHRASE = re.compile(
    r"implement(?:ed|ation)?\s+(?:this\s+|it\s+)?later"
    r"|wire\s+(?:this\s+|it\s+|them\s+)?(?:up\s+)?later"
    r"|not\s+(?:yet\s+)?implemented|coming\s+soon"
    r"|to\s+be\s+(?:implemented|done|added|written(?!\s+down)|filled\s+in)"
    r"|\bTBD\b|fill\s+(?:this\s+)?in\s+later|for\s+now,?\s+(?:just\s+)?(?:return|pass)",
    re.IGNORECASE,
)
# `#(?!\d)` so a GitHub ISSUE REFERENCE does not masquerade as a comment intro. Measured
# 2026-07-19: a markdown table row `| a native lazy-spawn flag exists | FALSE | 7 requests
# (#7336, #13805) all CLOSED NOT_PLANNED ... unimplemented ...` fired the weak-word rule FOUR
# times, because the `#` in `#7336` matched here and then "unimplemented" matched _WEAK later on
# the same line. The row is a FALSIFIED-HYPOTHESIS record about an upstream project's state -- a
# mention, not a placeholder. `# TODO` (hash + space) still matches; `#7336` no longer does.
_COMMENT_INTRO = re.compile(r"(?:#(?!\d)|//|/\*|<!--|^[ \t]*\*(?!\*))")
# Negation guard for _PHRASE. A negated completeness phrase asserts the OPPOSITE of an
# incomplete marker (an assertion that nothing remains), so it is not real pending work.
# Measured 2026-07-19: _PHRASE fired on the sentence "Fortunately x means nothing needs to be
# added" and on a doc quoting it -- the regex was negation-blind (the use-vs-mention class). When
# a negation word sits just before the phrase on the same line, the phrase is not pending work.
# (This comment deliberately avoids the bare trigger words so the scanner does not flag itself.)
_NEG = re.compile(
    r"\b(?:no|nothing|never|not|n't|zero|without|already)\b", re.IGNORECASE
)
# (?![-\w]) so a COMPOUND identifier that merely contains the word is NOT a stub:
# "stub-ledger", "stub_file", "stubscan", "placeholder_path" -> ignored; bare "stub"/"placeholder" -> flagged.
_WEAK = re.compile(r"\b(placeholder|stub|unimplemented)\b(?![-\w])", re.IGNORECASE)

# def name(...):  [-> type]:  then (optional docstring) then pass / ...
# The param span is `(?:[^)\n]|\n(?!...def|class))*` — NOT a bare `[^)]*`: a bare
# `[^)]*` matches across newlines and BACKTRACKS FORWARD to a distant `)`, so a
# COMPLETE multi-line-signature function would false-match on some LATER function's
# `pass`/`...` body (a 26k-char reach). Disallowing a newline that begins a new
# `def`/`class` keeps the param span inside THIS signature.
_PASS_BODY = re.compile(
    r"^[ \t]*(?:async[ \t]+)?def[ \t]+(\w+)[ \t]*"
    r"\((?:[^)\n]|\n(?![ \t]*(?:async[ \t]+)?(?:def|class)\b))*\)"
    r"[ \t]*(?:->[^\n:]+)?:[ \t]*(?:#[^\n]*)?\n"
    r"(?:[ \t]*(?:\"\"\"[\s\S]*?\"\"\"|'''[\s\S]*?''')[ \t]*\n)?"
    r"[ \t]*(?:pass|\.\.\.)[ \t]*(?:#[^\n]*)?(?:\n|$)",
    re.MULTILINE,
)

# An explicit `# pragma: no cover` marks a body/line as INTENTIONALLY not covered —
# a typing.Protocol/ABC interface method (`...`), a defensive `raise`, a heavy
# import seam. That is a deliberate design marker, NOT incomplete work an agent
# forgot to finish, so it must never be surfaced as an open stub.
_PRAGMA_NOCOVER = re.compile(r"#\s*pragma:\s*no\s+cover", re.IGNORECASE)


_TEST_FILE = re.compile(
    r"(?:^|[\\/])(?:test_[^\\/]+|conftest)\.py$|_test\.py$|\.test\.[jt]sx?$"
    r"|[\\/](?:tests?|__tests__|scratchpad|FAILURE-REPLAY-CORPUS|fixtures?|stub-ledger)[\\/]",
    re.IGNORECASE,
)


def is_test_file(path: str) -> bool:
    """True for test/fixture files, which legitimately CONTAIN stub/TODO markers (a
    stub-detector's own tests MUST) — callers skip them so fixtures are never flagged
    as incomplete production code."""
    return bool(path) and bool(_TEST_FILE.search(str(path).replace("\\", "/")))


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _discriminator(path: str):
    """Return a `(span_start, span_end) -> bool` real-occurrence test, or None.

    None means "no filtering" — the caller passed no path, or the shared module is unavailable.
    Fail-open by construction: a broken or missing discriminator must never silently DISARM the
    scanner, it must only ever fall back to the pre-existing regex behaviour.
    """
    if not path:
        return None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
        from use_vs_mention import Context, is_real_occurrence
    except Exception:
        return None
    ctx = Context(file_path=path, source="file")
    return lambda text, start, end: is_real_occurrence(
        text, (start, end), ctx, kind="marker"
    )


def find_stubs(text: str, path: str = "") -> list[tuple[str, int, str]]:
    """Return deduped (marker, line_no, snippet) tuples. Stdlib-only, bounded.

    `path` is OPTIONAL and backward-compatible: omitted, behaviour is exactly as before. Supplied,
    every candidate is routed through the shared use-vs-mention discriminator, which is what stops
    a design document from being scored as unfinished work. Loop 6f8a224e measured the cost of not
    doing this: 9 of 9 fires on `platform-redesign-2026-07-19` were prose ABOUT stubs, not stubs.

    Spans are absolute offsets into `text`, not line-relative — the discriminator needs to see
    fenced and inline-code regions, which a per-line offset cannot express.
    """
    if not text:
        return []
    out: list[tuple[str, int, str]] = []
    seen: set[tuple[str, str]] = set()
    is_real = _discriminator(path)

    def add(marker: str, line_no: int, snippet: str):
        snip = _norm(snippet)[:120]
        key = (marker.upper(), snip.lower())
        if key in seen or not snip:
            return
        seen.add(key)
        out.append((marker.upper(), line_no, snip))

    lines = text.splitlines()
    offset = 0  # absolute offset of the current line within `text`
    for i, line in enumerate(lines, 1):
        for m in _COMMENT_TAG.finditer(line):
            if is_real is None or is_real(text, offset + m.start(), offset + m.end()):
                add(m.group(1), i, line)
        nm = _NOTIMPL.search(line)
        if nm and (
            is_real is None or is_real(text, offset + nm.start(), offset + nm.end())
        ):
            add("NotImplemented", i, line)
        pm = _PHRASE.search(line)
        if (
            pm
            and not _NEG.search(line[max(0, pm.start() - 45) : pm.start()])
            and (
                is_real is None or is_real(text, offset + pm.start(), offset + pm.end())
            )
        ):
            add("placeholder-phrase", i, line)
        # The weak word "stub"/"placeholder" in an explicit `# pragma: no cover`
        # comment (e.g. "...  # pragma: no cover - Protocol stub") is describing a
        # deliberate interface marker, not incomplete work -> do not flag it.
        wm = _WEAK.search(line)
        if (
            _COMMENT_INTRO.search(line)
            and wm
            and not _PRAGMA_NOCOVER.search(line)
            and (
                is_real is None or is_real(text, offset + wm.start(), offset + wm.end())
            )
        ):
            add(wm.group(1), i, line)
        offset += len(line) + 1  # +1 for the newline consumed by splitlines()

    for m in _PASS_BODY.finditer(text):
        seg = text[m.start() : m.end()]
        # A pass/... body explicitly marked `# pragma: no cover` (Protocol/ABC method,
        # defensive branch) is intentional, never an unfinished stub.
        tail = seg.rstrip().splitlines()[-1] if seg.strip() else ""
        if _PRAGMA_NOCOVER.search(tail):
            continue
        line_no = text.count("\n", 0, m.start()) + 1
        header = seg.splitlines()[0]
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
