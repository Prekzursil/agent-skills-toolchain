"""Completeness join: every taxonomy code has a non-empty remediation command."""
from __future__ import annotations

from typing import Any

from .io import load_mapping, load_taxonomy, taxonomy_codes


def missing_mappings(
    taxonomy: dict[str, Any] | None = None,
    mapping: dict[str, Any] | None = None,
) -> list[str]:
    tax = taxonomy if taxonomy is not None else load_taxonomy()
    mp = mapping if mapping is not None else load_mapping()
    missing = []
    for code in taxonomy_codes(tax):
        rec = mp.get(code) or {}
        cmd = rec.get("command") if isinstance(rec, dict) else rec
        if not (isinstance(cmd, str) and cmd.strip()):
            missing.append(code)
    return missing


def validate_join() -> dict[str, Any]:
    missing = missing_mappings()
    codes = taxonomy_codes()
    return {
        "complete": not missing,
        "n": len(codes),
        "taxonomy_count": len(codes),
        "missing": missing,
        "missing_mappings": missing,
        "codes": codes,
    }
