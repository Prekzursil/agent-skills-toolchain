#!/usr/bin/env python3
"""Leak detector for blind confirmation briefs (CNF-0005).

A conclusion fragment is a distinctive token or window that appears in the
denied receipt fields and does NOT appear in the allow-list fields. The
detector flags a brief when any such fragment, or any denied JSON key,
is present in the confirmer input.
"""
from __future__ import annotations

import json
import re
from typing import Any

from builder import (
    ALLOWED_FIELDS,
    DENIED_FIELDS,
    allowed_view,
    denied_view,
    serialize_brief,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{7,}")
_WINDOW = 20
_STEP = 10
_MIN_ALNUM = 12


def flatten_text(obj: Any) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, dict):
        return "\n".join(flatten_text(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return "\n".join(flatten_text(v) for v in obj)
    return str(obj)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def distinctive_fragments(forbidden: str, allowed: str) -> list[str]:
    """Fragments unique to denied text. Empty list means the detector is vacuous."""
    forb = _norm(forbidden)
    allw_l = _norm(allowed).lower()
    out: list[str] = []
    seen: set[str] = set()

    def add(frag: str) -> None:
        if not frag or frag in seen:
            return
        if frag.lower() in allw_l:
            return
        seen.add(frag)
        out.append(frag)

    for tok in _TOKEN_RE.findall(forb):
        add(tok)
    for i in range(0, max(0, len(forb) - _WINDOW + 1), _STEP):
        window = forb[i : i + _WINDOW]
        if sum(ch.isalnum() for ch in window) >= _MIN_ALNUM:
            add(window)
    return out


def extra_keys(brief: dict[str, Any]) -> list[str]:
    return sorted(k for k in brief.keys() if k not in ALLOWED_FIELDS)


def denied_keys_present(brief: dict[str, Any]) -> list[str]:
    keys = set(brief.keys())
    named = keys.intersection(DENIED_FIELDS)
    extra = keys.difference(ALLOWED_FIELDS)
    return sorted(named.union(extra))


def scan_brief(brief: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Return leak findings for one (brief, source-receipt) pair.

    This function is the cited detector source for CNF-0005 evidence.
    """
    allowed_text = flatten_text(allowed_view(receipt))
    denied_text = flatten_text(denied_view(receipt))
    needles = distinctive_fragments(denied_text, allowed_text)
    blob = serialize_brief(brief)
    hits = [n for n in needles if n in blob]
    keys = denied_keys_present(brief)
    return {
        "claim_id": receipt.get("claim_id"),
        "leak": bool(hits) or bool(keys),
        "fragments": hits[:24],
        "denied_keys_present": keys,
        "needle_count": len(needles),
        "vacuous": len(needles) == 0,
    }


def inject_conclusion(brief: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    """Plant the implementer conclusion into the claim statement (builder-bug shape)."""
    leaked = json.loads(json.dumps(brief))
    conclusion = receipt.get("implementer_conclusion")
    if conclusion is None:
        raise KeyError("receipt has no implementer_conclusion to inject")
    stmt = leaked.get("claim_statement") or ""
    leaked["claim_statement"] = stmt + "\n" + flatten_text(conclusion)
    return leaked
