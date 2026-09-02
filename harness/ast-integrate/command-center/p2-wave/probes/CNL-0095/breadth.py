"""Independent breadth signal: taxonomy category coverage.

Does not call detector.detect(). Uses category labels, not Jaccard clusters.
A second round of paraphrases in already-covered categories does not raise
coverage. Complement ideas in uncovered categories do.
"""
from __future__ import annotations

from typing import Any

from transcript import first_converge_index, items_of_kind, taxonomy_of


def covered_at(events: list[dict], end_exclusive: int | None) -> set[str]:
    slice_ = events if end_exclusive is None else events[:end_exclusive]
    return {
        str(e.get("category"))
        for e in items_of_kind(slice_, "idea")
        if e.get("category")
    }


def coverage_report(run: dict[str, Any]) -> dict[str, Any]:
    events = list(run.get("events") or [])
    tax = taxonomy_of(run)
    tax_set = set(tax)
    first = first_converge_index(events)
    cov_first = covered_at(events, first) & tax_set if tax_set else set()
    last = None
    for i, ev in enumerate(events):
        if ev.get("kind") == "converge":
            last = i
    cov_last = covered_at(events, last) & tax_set if tax_set else set()
    n = len(tax) or 1
    return {
        "taxonomy": tax,
        "covered_at_first_converge": sorted(cov_first),
        "covered_at_last_converge": sorted(cov_last),
        "uncovered_at_first_converge": [c for c in tax if c not in cov_first],
        "coverage_at_first": len(cov_first) / n,
        "coverage_at_last": len(cov_last) / n,
        "coverage_delta": (len(cov_last) - len(cov_first)) / n,
        "breadth_recovered": len(cov_last) > len(cov_first),
    }
