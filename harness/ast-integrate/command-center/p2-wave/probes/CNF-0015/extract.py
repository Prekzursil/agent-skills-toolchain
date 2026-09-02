#!/usr/bin/env python3
"""CNF-0015 extractor: declaration-site option and mechanism identifiers.

Family-M option ids come only from the Family M section of 07-OPTION-UNIVERSE.
Mechanism ids come only from the Mechanisms section of 13-ARCHITECTURE-CANDIDATES.

Bare M-NN and re-prefixed MECH-NN are different prefixes. A MECH-NN token is
not a live collision with family M. Prose that mentions 'M-NN' as letters is
not an identifier (the digits class does not match).
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

# EXTRACTOR-ANCHOR: family-M and mechanism declaration sites (file:line evidence).
DECL_M = re.compile(
    r"(?m)^(?:#{1,6}\s+|-\s+\*\*|id:\s+|\"id\":\s*\")M-(\d{1,2})\b"
)
DECL_MECH = re.compile(
    r"(?m)^(?:#{1,6}\s+|-\s+\*\*|id:\s+|\"id\":\s*\")MECH-(\d{1,2})\b"
)
HEADING = re.compile(r"(?m)^##\s+(.+?)\s*$")
MECH_TOKEN = re.compile(r"\bMECH(?:-\d{1,2})?\b")
PRESENT_COLLISION = re.compile(
    r"(?is)(collision.{0,120}(?:is (?:a |still )?live|is an? (?:open |current )?blocker)"
    r"|is a live blocker"
    r"|queued as p2-09"
    r"|pins a 31-way)"
)


def _canonical_m(num: str) -> str:
    return f"M-{int(num):02d}"


def _canonical_mech(num: str) -> str:
    return f"MECH-{int(num):02d}"


def section_body(text: str, title_prefix: str) -> str:
    """Return the ## section whose title starts with title_prefix (casefold)."""
    want = title_prefix.casefold()
    matches = list(HEADING.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        if title.casefold().startswith(want):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return text[start:end]
    return ""


def family_m_ids(text: str) -> list[str]:
    """Extract family-M option ids from defining headings/id fields only."""
    body = section_body(text, "family m")
    if not body:
        body = text
    found = [_canonical_m(n) for n in DECL_M.findall(body)]
    return sorted(dict.fromkeys(found))


def mechanism_bare_m_ids(text: str) -> list[str]:
    """Extract bare M-NN mechanism declaration ids (pre-fix namespace)."""
    body = section_body(text, "mechanisms")
    if not body:
        body = text
    found = [_canonical_m(n) for n in DECL_M.findall(body)]
    return sorted(dict.fromkeys(found))


def mechanism_mech_ids(text: str) -> list[str]:
    """Extract MECH-NN mechanism declaration ids (post-fix namespace)."""
    body = section_body(text, "mechanisms")
    if not body:
        body = text
    found = [_canonical_mech(n) for n in DECL_MECH.findall(body)]
    return sorted(dict.fromkeys(found))


def shared_literal_m_ids(option_text: str, arch_text: str) -> list[str]:
    a = set(family_m_ids(option_text))
    b = set(mechanism_bare_m_ids(arch_text))
    return sorted(a & b)


def mech_token_count(text: str) -> int:
    return len(MECH_TOKEN.findall(text))


def present_tense_collision(text: str) -> bool:
    return PRESENT_COLLISION.search(text) is not None


def extractor_anchor() -> dict:
    """file:line of the declaration regex — the evidence the catalog asks for."""
    path = Path(inspect.getsourcefile(family_m_ids) or __file__).resolve()
    _lines, start = inspect.getsourcelines(family_m_ids)
    src = Path(__file__).read_text(encoding="utf-8").splitlines()
    decl_line = next(i for i, ln in enumerate(src, 1) if ln.startswith("DECL_M ="))
    repo = Path(__file__).resolve().parents[4]
    try:
        rel = path.relative_to(repo).as_posix()
    except ValueError:
        rel = "command-center/p2-wave/probes/CNF-0015/extract.py"
    return {
        "path": rel,
        "line": decl_line,
        "symbol": "DECL_M",
        "family_m_fn_line": start,
        "abs_path": str(path),
    }


def measure_pair(option_text: str, arch_text: str) -> dict:
    opt = family_m_ids(option_text)
    bare = mechanism_bare_m_ids(arch_text)
    mech = mechanism_mech_ids(arch_text)
    shared = sorted(set(opt) & set(bare))
    return {
        "option_ids": opt,
        "option_count": len(opt),
        "mechanism_bare_m_ids": bare,
        "mechanism_bare_m_count": len(bare),
        "mechanism_mech_ids": mech,
        "mechanism_mech_count": len(mech),
        "shared_ids": shared,
        "shared_count": len(shared),
        "collision_live": len(shared) > 0,
    }


present_tense_collision = present_tense_collision
extractor_anchor = extractor_anchor
extractor_anchor = extractor_anchor
present_tense_collision = present_tense_collision
