#!/usr/bin/env python3
"""Scan the assembled catalog and emit the duplicate-report body."""
from __future__ import annotations

import json
from math import comb
from pathlib import Path
from typing import Any, Mapping, Sequence

from fingerprint import (
    ALGORITHM_ID,
    JACCARD_THRESHOLD,
    collisions_among,
    fingerprint_parts,
    index_parts,
    too_coarse,
)

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
SLICE_GLOB = "command-center/catalog-slices/*.json"


HERE = Path(__file__).resolve().parent


def repo_root() -> Path:
    return HERE.parents[3]


def load_catalog(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    path = root / CATALOG_REL
    return json.loads(path.read_text(encoding="utf-8"))


def slice_files(repo: Path | None = None) -> list[str]:
    root = repo or repo_root()
    base = root / "command-center" / "catalog-slices"
    if not base.is_dir():
        return []
    return sorted(p.relative_to(root).as_posix() for p in base.glob("*.json") if p.is_file())


def adjudicate(row: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    a = by_id.get(row["unit_id_a"], {})
    b = by_id.get(row["unit_id_b"], {})
    notes = []
    for unit in (a, b):
        reason = unit.get("not_a_duplicate_because")
        if isinstance(reason, str) and reason.strip():
            notes.append(f"{unit.get('id')}: {reason.strip()}")
    if notes:
        verdict = "needs_review"
        why = "at least one unit declares not_a_duplicate_because; " + " | ".join(notes)
    elif row.get("token_sets_equal") or float(row.get("jaccard") or 0) >= 0.95:
        verdict = "genuine_duplicate"
        why = (
            "same normalized input set and target-token Jaccard "
            f"{row.get('jaccard')} (>=0.95 or token-set equal); same mechanism"
        )
    else:
        verdict = "needs_review"
        why = (
            "same input set and Jaccard "
            f"{row.get('jaccard')} in [{JACCARD_THRESHOLD}, 0.95); confirm by hand"
        )
    out = dict(row)
    out["adjudication"] = verdict
    out["adjudication_reason"] = why
    out["title_a"] = a.get("title")
    out["title_b"] = b.get("title")
    return out


def scan_units(units: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    parts = index_parts(units)
    raw = collisions_among(parts)
    by_id = {str(u.get("id")): u for u in units if isinstance(u, Mapping)}
    collisions = [adjudicate(row, by_id) for row in raw]
    coarse = too_coarse(parts, collisions)
    genuine = sum(1 for c in collisions if c["adjudication"] == "genuine_duplicate")
    false_pos = sum(1 for c in collisions if c["adjudication"] == "false_positive")
    needs = sum(1 for c in collisions if c["adjudication"] == "needs_review")
    n = len(parts)
    pairs = comb(n, 2) if n >= 2 else 0
    denom = len(collisions)
    rate_display = (
        f"{false_pos}/{denom} colliding pairs; {false_pos}/{pairs} compared pairs"
    )
    return {
        "algorithm_id": ALGORITHM_ID,
        "jaccard_threshold": JACCARD_THRESHOLD,
        "unit_count": n,
        "compared_pair_count": pairs,
        "collision_pair_count": len(collisions),
        "genuine_duplicate_count": genuine,
        "false_positive_count": false_pos,
        "needs_review_count": needs,
        "too_coarse": coarse,
        "collisions": collisions,
        "false_positive_rate": {
            "false_positives": false_pos,
            "denominator": denom,
            "denominator_meaning": "colliding pairs (flagged by the fingerprint)",
            "rate": (false_pos / denom) if denom else None,
            "rate_display": rate_display,
            "compared_pair_denominator": pairs,
            "false_positives_over_compared_pairs": f"{false_pos}/{pairs}",
        },
        "fingerprint_table_sha256": _table_digest(parts),
    }


def _table_digest(parts: Sequence[Any]) -> str:
    import hashlib

    lines = []
    for p in sorted(parts, key=lambda x: x.unit_id):
        lines.append(f"{p.unit_id}\t{p.canonical}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def scan_catalog(repo: Path | None = None) -> dict[str, Any]:
    root = repo or repo_root()
    catalog = load_catalog(root)
    units = catalog.get("work_units") or []
    meta = catalog.get("work_units_meta") or {}
    body = scan_units(units)
    slices = slice_files(root)
    declared = meta.get("target")
    counted = meta.get("work_unit_count")
    body["catalog"] = {
        "path": CATALOG_REL,
        "slice_glob": SLICE_GLOB,
        "slice_files_found": slices,
        "slice_files_declared_in_meta": list(meta.get("slice_files_merged") or []),
        "declared_program_count": declared,
        "meta_work_unit_count": counted,
        "assembled_work_unit_count": body["unit_count"],
        "shortfall": meta.get("shortfall"),
        "meta_status": meta.get("status"),
    }
    return body
