"""Signal A: histogram from candidates[].classification, never from counts."""
from __future__ import annotations

from collections import Counter
from typing import Any


def _label(rec: dict[str, Any]) -> str:
    raw = rec.get("classification")
    if raw is None or raw == "":
        return "<MISSING>"
    return str(raw)


def recompute_from_candidates(candidates: list[dict[str, Any]]) -> dict[str, int]:
    """Authoritative recount. Independent of any sibling counts block."""
    c = Counter(_label(r) for r in candidates if isinstance(r, dict))
    return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))


def tally_loop(candidates: list[dict[str, Any]]) -> dict[str, int]:
    """Mechanically different accumulator (no Counter) for both-states."""
    out: dict[str, int] = {}
    for rec in candidates:
        if not isinstance(rec, dict):
            continue
        key = _label(rec)
        out[key] = out.get(key, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def counts_block_of(doc: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(doc, dict):
        return {}
    raw = doc.get("counts")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for k, v in raw.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out[str(k)] = v
        elif isinstance(v, float) and v.is_integer():
            out[str(k)] = int(v)
    return out


def disagreement(
    recomputed: dict[str, int], block: dict[str, int]
) -> list[dict[str, Any]]:
    keys = sorted(set(recomputed) | set(block))
    diffs = []
    for k in keys:
        a = int(recomputed.get(k) or 0)
        b = int(block.get(k) or 0)
        if a != b:
            diffs.append({"value": k, "from_candidates": a, "from_counts_block": b})
    return diffs


def unused_counts(recomputed: dict[str, int], unused: tuple[str, ...]) -> dict[str, int]:
    return {v: int(recomputed.get(v) or 0) for v in unused}
