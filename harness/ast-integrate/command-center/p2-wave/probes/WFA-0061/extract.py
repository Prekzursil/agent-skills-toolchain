"""Definition-derived mechanism extraction.

Self-description fields (mechanisms, notes, description) are mention, not
implementation. A gap produced by reading those fields is an extraction miss.
"""
from __future__ import annotations

from typing import Any


def vocab_ids(vocabulary: list[dict[str, Any]]) -> set[str]:
    return {str(v["id"]) for v in vocabulary if isinstance(v, dict) and v.get("id")}


def extract_from_definition(
    doc: dict[str, Any],
    kind_map: dict[str, str],
    vocabulary_ids: set[str],
) -> list[str]:
    """Map stages[].kind through the closed vocabulary. Ignore prose."""
    found: list[str] = []
    seen: set[str] = set()
    for stage in doc.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        kind = str(stage.get("kind") or "").strip()
        if not kind:
            continue
        mid = kind_map.get(kind)
        if not mid or mid not in vocabulary_ids or mid in seen:
            continue
        seen.add(mid)
        found.append(mid)
    return found


def extract_from_self_description(
    doc: dict[str, Any],
    vocabulary_ids: set[str],
) -> list[str]:
    """Mutant extractor: credits the mechanisms[] prose field.

    Use-versus-mention trap. Must not be used for published cells.
    """
    found: list[str] = []
    seen: set[str] = set()
    for item in doc.get("mechanisms") or []:
        mid = str(item).strip()
        if mid in vocabulary_ids and mid not in seen:
            seen.add(mid)
            found.append(mid)
    return found


def unmapped_kinds(doc: dict[str, Any], kind_map: dict[str, str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for stage in doc.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        kind = str(stage.get("kind") or "").strip()
        if not kind or kind in kind_map or kind in seen:
            continue
        seen.add(kind)
        out.append(kind)
    return out
