"""Sherman-Kent band vocabulary and hedge residue for SYN-0014.

Declared five (catalog / AGENTS.md §7): almost-certain, likely,
roughly-even, unlikely, remote. Unknown hedges are residue, not mapped.
"""
from __future__ import annotations

import re

DECLARED_BANDS: tuple[str, ...] = (
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
)

BAND_RANK: dict[str, int] = {
    "remote": 0,
    "unlikely": 1,
    "roughly-even": 2,
    "likely": 3,
    "almost-certain": 4,
}

# Evidence-type ceiling: a band above the ceiling is unsupported.
EVIDENCE_CEILING: dict[str, int] = {
    "direct-measurement": 4,
    "single-inference": 3,
    "analogy": 2,
    "none": -1,
}

BAND_ALIASES: dict[str, str] = {
    "almost-certain": "almost-certain",
    "almost certain": "almost-certain",
    "almost_certain": "almost-certain",
    "almostcertain": "almost-certain",
    "likely": "likely",
    "probable": "likely",
    "roughly-even": "roughly-even",
    "roughly even": "roughly-even",
    "even chance": "roughly-even",
    "50/50": "roughly-even",
    "unlikely": "unlikely",
    "improbable": "unlikely",
    "remote": "remote",
    "remote chance": "remote",
}

# Bare hedges that must be reported, not silently assigned a band.
HEDGE_PHRASES: tuple[str, ...] = (
    "should work",
    "looks fine",
    "likely fine",
    "seems ok",
    "seems okay",
    "probably fine",
    "looks good",
    "should be fine",
    "guaranteed",
    "definitely",
)

_QUOTE_RE = re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`")
_WORD_RE = re.compile(r"[A-Za-z0-9_/-]+")


def strip_mentions(text: str) -> str:
    """Drop quoted spans so vocabulary mentions are not treated as uses."""
    return _QUOTE_RE.sub(" ", text or "")


def normalize_band(raw: object) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().lower().replace("_", "-")
    s = re.sub(r"\s+", " ", s)
    if s in BAND_ALIASES:
        return BAND_ALIASES[s]
    s_hy = s.replace(" ", "-")
    if s_hy in BAND_ALIASES:
        return BAND_ALIASES[s_hy]
    return None


def find_hedges(text: str) -> list[str]:
    body = strip_mentions(text).lower()
    found: list[str] = []
    for phrase in HEDGE_PHRASES:
        if phrase in body:
            found.append(phrase)
    return found


def find_band_in_text(text: str) -> str | None:
    """Map a used (not quoted) certainty phrase onto the declared five."""
    body = strip_mentions(text).lower()
    for phrase in HEDGE_PHRASES:
        body = body.replace(phrase, " ")
    # Longest aliases first so "almost certain" wins over nothing.
    aliases = sorted(BAND_ALIASES.keys(), key=len, reverse=True)
    for alias in aliases:
        if alias in body:
            return BAND_ALIASES[alias]
    return None


def residue_tokens(text: str) -> list[str]:
    """Tokens that look like hedges/certainty but are not declared bands."""
    body = strip_mentions(text).lower()
    for phrase in HEDGE_PHRASES:
        body = body.replace(phrase, " ")
    for alias in sorted(BAND_ALIASES.keys(), key=len, reverse=True):
        body = body.replace(alias, " ")
    extra = []
    for tok in _WORD_RE.findall(body):
        if tok in {
            "certain",
            "certainly",
            "sure",
            "confident",
            "always",
            "never",
            "undoubtedly",
            "clearly",
        }:
            extra.append(tok)
    return extra


def evidence_type_of(anchor: dict) -> str:
    raw = (
        anchor.get("evidence_type")
        or anchor.get("type")
        or anchor.get("kind")
        or ""
    )
    key = str(raw).strip().lower().replace("_", "-")
    aliases = {
        "direct-measurement": "direct-measurement",
        "direct measurement": "direct-measurement",
        "measurement": "direct-measurement",
        "single-inference": "single-inference",
        "single inference": "single-inference",
        "inference": "single-inference",
        "analogy": "analogy",
        "none": "none",
        "": "",
    }
    mapped = aliases.get(key, key)
    if mapped in EVIDENCE_CEILING:
        return mapped
    snippet = str(anchor.get("snippet") or anchor.get("quote") or "").lower()
    if any(w in snippet for w in ("unverified", "n=1", "n = 1", "maybe", "todo")):
        return "none"
    if any(w in snippet for w in ("analog", "similar to", "by analogy")):
        return "analogy"
    if any(w in snippet for w in ("measured", "sha256", "exit 0", "byte-identical")):
        return "direct-measurement"
    return "single-inference"


def ceiling_rank(evidence_type: str) -> int:
    return EVIDENCE_CEILING.get(evidence_type, -1)


FLAG_NO_ANCHOR = "band-without-any-anchor"
FLAG_UNSUPPORTED = "band-not-supported-by-its-anchor"
