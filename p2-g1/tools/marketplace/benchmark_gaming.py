"""Unreproducible evidence scores zero (IMP-0097)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

try:
    from .scenario import Record
except ImportError:  # pragma: no cover
    from scenario import Record

FLAG_SELF_AUTHORED = "self-authored-case-set"


@dataclass
class Score:
    base: float
    total: float


def is_self_authored(record: Record, provenance: dict[str, Any] | None = None) -> bool:
    meta = (provenance or {}).get(record.record_id) or {}
    return bool(meta.get("self_authored") or getattr(record, "self_authored", False))


def contribution(record: Record, provenance: dict[str, Any] | None = None) -> float:
    meta = (provenance or {}).get(record.record_id) or {}
    reproduced = bool(meta.get("reproduced", record.reproduced))
    independent = bool(meta.get("independent", record.independent))
    if is_self_authored(record, provenance):
        return 0.0
    if reproduced and independent and not record.publisher_only:
        return float(record.claimed_delta)
    return 0.0


def score_with_benchmarks(
    measurements: dict[str, Any],
    records: Iterable[Record],
    provenance: dict[str, Any] | None = None,
) -> Score:
    base = float(measurements.get("base") or 0.0)
    total = base + sum(contribution(r, provenance) for r in records)
    return Score(base=base, total=total)


def score_without_record(
    measurements: dict[str, Any],
    records: Iterable[Record],
    provenance: dict[str, Any] | None,
    record_id: str,
) -> Score:
    kept = [r for r in records if r.record_id != record_id]
    return score_with_benchmarks(measurements, kept, provenance)
