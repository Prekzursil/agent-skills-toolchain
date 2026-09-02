#!/usr/bin/env python3
"""Codepoint-class scanner for TST-0246.

A naive East-Asian-Width W/F-only scan misses the Windows Terminal
regression seed U+26A0 (WARNING SIGN): on Python 3.12 / Unicode 15 it is
EAW=N and libc wcwidth=1, yet WT + emoji presentation overlap the next
cell. This scanner flags:

  * EAW Wide / Fullwidth (W, F)
  * EAW Ambiguous (A) — East-Asian-ambiguous
  * emoji-presentation (U+FE0F VS16, and default-emoji SMP / dingbat blocks)
  * the named regression seed U+26A0 even in text presentation

Combining marks (Mn/Me/Cf zero-width) are recorded but are not, by
themselves, the alignment-breaker class this unit names.
"""
from __future__ import annotations

import unicodedata
from typing import Any

REGRESSION_SEED = 0x26A0  # WARNING SIGN
VS16 = 0xFE0F
VS15 = 0xFE0E

# Default-emoji / pictograph blocks. BMP Miscellaneous Symbols includes
# U+26A0; we still special-case the seed so the hit names the regression.
EMOJI_RANGES: tuple[tuple[int, int], ...] = (
    (0x1F000, 0x1FFFF),  # SMP pictographs, emoticons, transport, extras
    (0x2600, 0x26FF),  # Miscellaneous Symbols
    (0x2700, 0x27BF),  # Dingbats
    (0x1F1E6, 0x1F1FF),  # regional indicators (also in 1F000 band)
)

ZERO_WIDTH_CATS = frozenset({"Mn", "Me", "Cf"})


def east_asian_width(ch: str) -> str:
    return unicodedata.east_asian_width(ch)


def in_emoji_range(cp: int) -> bool:
    return any(lo <= cp <= hi for lo, hi in EMOJI_RANGES)


def classify_char(ch: str, nxt: str | None = None) -> str | None:
    """Return a breaker class or None if the glyph is alignment-safe."""
    cp = ord(ch)
    cat = unicodedata.category(ch)
    if cp in (VS16, VS15):
        return "emoji-presentation-selector"
    if nxt and ord(nxt) == VS16:
        return "emoji-presentation"
    if cp == REGRESSION_SEED:
        return "regression-U+26A0"
    eaw = east_asian_width(ch)
    if eaw == "A":
        return "east-asian-ambiguous"
    if eaw == "W":
        return "wide"
    if eaw == "F":
        return "fullwidth"
    if in_emoji_range(cp) and cat not in ZERO_WIDTH_CATS:
        return "emoji-block"
    return None


def naive_wf_only(ch: str) -> str | None:
    """Known-blind scanner: only W/F. Misses U+26A0 and EAW=A."""
    eaw = east_asian_width(ch)
    if eaw == "W":
        return "wide"
    if eaw == "F":
        return "fullwidth"
    return None


def scan_line(
    line: str, *, naive: bool = False, line_no: int = 0
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for i, ch in enumerate(line):
        nxt = line[i + 1] if i + 1 < len(line) else None
        kind = naive_wf_only(ch) if naive else classify_char(ch, nxt)
        if not kind:
            continue
        cp = ord(ch)
        hits.append(
            {
                "line_no": line_no,
                "index": i,
                "char": ch,
                "codepoint": f"U+{cp:04X}",
                "east_asian_width": east_asian_width(ch),
                "category": unicodedata.category(ch),
                "name": unicodedata.name(ch, ""),
                "class": kind,
            }
        )
    return hits


def scan_text(text: str, *, naive: bool = False) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for n, line in enumerate(text.splitlines()):
        hits.extend(scan_line(line, naive=naive, line_no=n))
    return hits


def seed_properties() -> dict[str, Any]:
    ch = chr(REGRESSION_SEED)
    return {
        "codepoint": "U+26A0",
        "name": unicodedata.name(ch, ""),
        "east_asian_width": east_asian_width(ch),
        "category": unicodedata.category(ch),
        "real_class": classify_char(ch),
        "naive_class": naive_wf_only(ch),
        "note": (
            "EAW is Neutral (N) in Unicode 15 / Python 3.12, so a W/F-only "
            "or A-only scanner is blind. Windows Terminal still renders this "
            "glyph width-2 and overlapped its neighbour (catalog regression)."
        ),
    }
