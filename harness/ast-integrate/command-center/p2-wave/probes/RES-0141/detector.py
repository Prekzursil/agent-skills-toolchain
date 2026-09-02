"""Lexical/structural breaking-change signals. Does not import labels.py.

Signals are evaluated on note text only (GitHub body + changelog section).
They must not read gold labels or version tuples.
"""
from __future__ import annotations

import re

SIGNAL_IDS = (
    "semver_major_bump",
    "breaking_change_footer",
    "removal_verb",
    "deprecation_then_removal",
)

# Prose claim of a major/incompatible bump — not the parsed tag.
_SEMVER_MAJOR = (
    r"(?i)\bmajor (?:version|release|update)\b",
    r"(?i)\bnot (?:backwards|backward)[- ]compatible\b",
    r"(?i)\bbackward[s-]?incompatible\b",
    r"(?i)\bincompatible (?:API|change|release)\b",
    r"(?i)\bmigration guide\b",
)

# Conventional-commit footer or changelog Breaking heading.
_BREAKING_FOOTER = (
    r"(?im)^(?:\s*)BREAKING[- ]CHANGE\s*:",
    r"(?i)\bBREAKING[- ]CHANGE\s*:",
    r"(?im)^#{1,4}\s+.*\bbreaking(?:[- ]changes?)?\b",
    r"(?im)^breaking changes?\s*$",
    r"(?im)^removed\s*$",
    r"(?im)^#{1,3}\s+removed\s*$",
)

# Removal of supported API / previously deprecated code / dropped support.
_REMOVAL = (
    r"(?i)\bremoves? previously deprecated\b",
    r"(?i)\bremove previously deprecated\b",
    r"(?i)\bdropped support for\b",
    r"(?i)\bremoved support for\b",
    r"(?i)\bdrop(?:ped)? support for\b",
    r"(?im)^[-=~\s]*removed\s*$",
    r"(?im)^#{1,4}\s+removed\b",
)

# Deprecation and removal co-occurring in the same note.
_DEPREC_REMOVAL = (
    r"(?i)\bremoves? previously deprecated\b",
    r"(?i)\bremove previously deprecated\b",
    r"(?is)\bdeprecat(?:ed|es|ion|e)\b.{0,180}\b(?:remov(?:e|es|ed|ing)|drop(?:ped|ping)? support)\b",
    r"(?is)\b(?:remov(?:e|es|ed)|drop(?:ped)? support)\b.{0,180}\bdeprecat",
)

_NEGATED_BREAKING = re.compile(
    r"(?i)(?:should not result in |(?:do(?:es)? not|does not|no|without|never)\s+)"
    r"(?:a\s+)?breaking"
)

PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "semver_major_bump": tuple(re.compile(p) for p in _SEMVER_MAJOR),
    "breaking_change_footer": tuple(re.compile(p) for p in _BREAKING_FOOTER),
    "removal_verb": tuple(re.compile(p) for p in _REMOVAL),
    "deprecation_then_removal": tuple(re.compile(p) for p in _DEPREC_REMOVAL),
}


def _unnegated_hit(pattern: re.Pattern[str], text: str, signal: str) -> bool:
    for m in pattern.finditer(text):
        if signal in {"breaking_change_footer", "semver_major_bump"}:
            lo = max(0, m.start() - 70)
            hi = min(len(text), m.end() + 40)
            if _NEGATED_BREAKING.search(text[lo:hi]):
                continue
        return True
    return False


def signals_for(text: str) -> dict[str, bool]:
    body = text or ""
    out: dict[str, bool] = {}
    for sid, pats in PATTERNS.items():
        out[sid] = any(_unnegated_hit(p, body, sid) for p in pats)
    return out


def fires(text: str, combo: tuple[str, ...]) -> bool:
    sig = signals_for(text)
    return any(sig.get(s) for s in combo)
