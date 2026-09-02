#!/usr/bin/env python3
"""Signal 2: mechanical id census (set intersection), not tense/prose.

Bare option/mechanism tokens are M-<digits>. Mechanism cards after the
2026-08-07 re-prefix are MECH-<digits>. A token 'M-NN' with literal N
letters is a metavariable and is not an id.
"""
from __future__ import annotations

import re
from typing import Iterable

# Negative lookbehind keeps MECH-12 from counting as bare M-12.
BARE_M_RE = re.compile(r"(?<![A-Z])M-(\d+)\b")
MECH_RE = re.compile(r"\bMECH-(\d+)\b")


def bare_m_ids(text: str) -> set[int]:
    return {int(m.group(1)) for m in BARE_M_RE.finditer(text or "")}


def mech_ids(text: str) -> set[int]:
    return {int(m.group(1)) for m in MECH_RE.finditer(text or "")}


def collision_ids(option_text: str, architecture_text: str) -> set[int]:
    """Literal shared bare M-N tokens across option-universe and architecture."""
    return bare_m_ids(option_text) & bare_m_ids(architecture_text)


def census(option_text: str, architecture_text: str) -> dict:
    opt = bare_m_ids(option_text)
    arch_bare = bare_m_ids(architecture_text)
    arch_mech = mech_ids(architecture_text)
    shared = opt & arch_bare
    return {
        "option_bare_m_count": len(opt),
        "architecture_bare_m_count": len(arch_bare),
        "architecture_mech_count": len(arch_mech),
        "literal_collision_count": len(shared),
        "literal_collision_ids": sorted(shared),
        "reprefix_applied": len(arch_mech) > 0 and len(arch_bare) == 0,
        "instrument": "python-re-set-intersection-bare-M-vs-MECH",
    }


def json_id_present(raw: str, unit_id: str) -> bool:
    """Second, non-JSON-walk signal: quoted id token in raw bytes."""
    if not unit_id or '"' in unit_id:
        return False
    return bool(re.search(rf'"id"\s*:\s*"{re.escape(unit_id)}"', raw))


def walk_json_ids(obj, found: set[str] | None = None) -> set[str]:
    found = found if found is not None else set()
    if isinstance(obj, dict):
        ident = obj.get("id")
        if isinstance(ident, str):
            found.add(ident)
        for v in obj.values():
            walk_json_ids(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk_json_ids(v, found)
    return found


def join_texts(parts: Iterable[str]) -> str:
    return "\n".join(parts)
