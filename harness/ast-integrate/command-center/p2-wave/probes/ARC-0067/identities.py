"""Enumerated identity tokens for ARC-0067 leakage scan and redaction.

The catalog tests_required leakage scan is grep over this list: the nine
architecture names (plus A1-A9 ids) and author/vendor ids. Unit ids
ARC-0003..ARC-0065 are included as brand-identifying phrasing: each maps
onto one dossier set.
"""
from __future__ import annotations

import re
from functools import lru_cache

# Official short names from WORK-UNIT-CATALOG titles for A1-A9 DESIGN units.
ARCHITECTURES: list[dict[str, str]] = [
    {
        "id": "A1",
        "name": "config-first-minimal",
        "slug": "config-first-minimal",
        "design_unit": "ARC-0003",
    },
    {
        "id": "A2",
        "name": "generated-ssot",
        "slug": "generated-ssot",
        "design_unit": "ARC-0010",
    },
    {
        "id": "A3",
        "name": "marketplace-first",
        "slug": "marketplace-first",
        "design_unit": "ARC-0017",
    },
    {
        "id": "A4",
        "name": "gateway / lazy-activation",
        "slug": "gateway-lazy-activation",
        "design_unit": "ARC-0024",
    },
    {
        "id": "A5",
        "name": "distributed workflow-runtime",
        "slug": "distributed-workflow-runtime",
        "design_unit": "ARC-0031",
    },
    {
        "id": "A6",
        "name": "cross-vendor adapter",
        "slug": "cross-vendor-adapter",
        "design_unit": "ARC-0038",
    },
    {
        "id": "A7",
        "name": "security-first",
        "slug": "security-first",
        "design_unit": "ARC-0045",
    },
    {
        "id": "A8",
        "name": "UX / product-first",
        "slug": "ux-product-first",
        "design_unit": "ARC-0052",
    },
    {
        "id": "A9",
        "name": "maximal hybrid",
        "slug": "maximal-hybrid",
        "design_unit": "ARC-0059",
    },
]

# Phrase aliases (longest first is applied at compile time).
ARCHITECTURE_NAME_ALIASES: list[str] = [
    "generated single-source-of-truth",
    "distributed workflow-runtime",
    "gateway / lazy-activation",
    "cross-vendor adapter",
    "UX / product-first",
    "config-first-minimal",
    "generated-ssot",
    "generated SSOT",
    "marketplace-first",
    "lazy-activation",
    "lazy activation",
    "distributed-runtime",
    "cross-vendor",
    "security-first",
    "product-first",
    "ux-first",
    "maximal hybrid",
    "maximal-hybrid",
    "config-first",
    "gateway",
]

AUTHOR_IDS: list[str] = [
    r"C:\\Users\\Prekzursil",
    "C:/Users/Prekzursil",
    "Prekzursil",
    "codex-cli-default",
    "anthropic",
    "openai",
    "cursor",
    "grok-4.6",
    "claude",
    "gemini",
    "codex",
    "opus",
    "grok",
    "gpt-4",
    "xAI",
    "xai",
    "gpt",
]

REDACT = "[REDACTED]"


def architecture_ids() -> list[str]:
    return [row["id"] for row in ARCHITECTURES]


def architecture_names() -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for row in ARCHITECTURES:
        for item in (row["name"], row["slug"]):
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                names.append(item)
    for alias in ARCHITECTURE_NAME_ALIASES:
        key = alias.casefold()
        if key not in seen:
            seen.add(key)
            names.append(alias)
    return names


def dossier_unit_ids() -> list[str]:
    # A1=ARC-0003..0009, A2=0010..0016, ... A9=0059..0065
    return [f"ARC-{n:04d}" for n in range(3, 66)]


def enumerated_literals() -> list[str]:
    """The grep pattern list: names, ids, author ids, dossier unit ids."""
    items: list[str] = []
    seen: set[str] = set()
    for item in (
        architecture_names()
        + architecture_ids()
        + AUTHOR_IDS
        + dossier_unit_ids()
    ):
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


def _is_wordish(token: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", token))


@lru_cache(maxsize=1)
def compiled_patterns() -> list[re.Pattern[str]]:
    pats: list[re.Pattern[str]] = []
    for lit in sorted(enumerated_literals(), key=len, reverse=True):
        escaped = re.escape(lit)
        if _is_wordish(lit):
            pats.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
        else:
            pats.append(re.compile(escaped, re.IGNORECASE))
    return pats


def redact_text(text: str) -> str:
    out = text
    for rx in compiled_patterns():
        out = rx.sub(REDACT, out)
    return out


redact_text = redact_text


def find_hits(text: str) -> list[dict[str, str | int]]:
    hits: list[dict[str, str | int]] = []
    for rx in compiled_patterns():
        for m in rx.finditer(text):
            hits.append(
                {
                    "span": m.group(0),
                    "start": m.start(),
                    "pattern": rx.pattern,
                }
            )
    return hits


find_hits = find_hits
