"""Per-test-id outcome sets and the symmetric difference aggregate counts cannot see.

A pass/fail total that is unchanged can hide one new pass cancelling one new
failure. Collection errors are a separate bucket: a suite that cannot collect
is not a suite that passed.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

FLIP_TO_FAIL_ID = "test_outcomes.py::OutcomeSet::test_beta_was_pass"
FLIP_TO_PASS_ID = "test_outcomes.py::OutcomeSet::test_gamma_was_fail"

OUTCOMES = (
    "passed",
    "failed",
    "skipped",
    "xfailed",
    "xpassed",
    "error",
    "collection_error",
)
PASS_LIKE = frozenset({"passed", "xpassed"})
FAIL_LIKE = frozenset({"failed", "error"})
# Human-facing aggregates that a cancelling pair is constructed to leave unchanged.
VISIBLE_COUNT_KEYS = ("passed", "failed", "skipped")


def counts_of(members: Iterable[dict[str, Any]]) -> dict[str, int]:
    rows = list(members)
    raw = Counter(str(m.get("outcome") or "") for m in rows)
    return {
        "passed": int(raw["passed"] + raw["xpassed"]),
        "failed": int(raw["failed"]),
        "skipped": int(raw["skipped"] + raw["xfailed"]),
        "error": int(raw["error"]),
        "collection_error": int(raw["collection_error"]),
        "total_ids": len(rows),
    }


def _index(members: Iterable[dict[str, Any]]) -> dict[str, str]:
    idx: dict[str, str] = {}
    for row in members:
        tid = str(row.get("id") or "").strip()
        if not tid:
            continue
        idx[tid] = str(row.get("outcome") or "")
    return idx


def visible_counts(members: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Pass/fail/skip totals. Collection errors are excluded by construction."""
    c = counts_of(members)
    return {k: c[k] for k in VISIBLE_COUNT_KEYS}


def aggregate_counts_unchanged(before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]) -> bool:
    return visible_counts(before) == visible_counts(after)


def symmetric_difference(
    before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    b = _index(before)
    a = _index(after)
    only_before = sorted(set(b) - set(a))
    only_after = sorted(set(a) - set(b))
    flipped: list[dict[str, str]] = []
    for tid in sorted(set(b) & set(a)):
        if b[tid] == a[tid]:
            continue
        flipped.append({"id": tid, "from": b[tid], "to": a[tid]})
    to_pass = sum(1 for f in flipped if f["from"] in FAIL_LIKE and f["to"] in PASS_LIKE)
    to_fail = sum(1 for f in flipped if f["from"] in PASS_LIKE and f["to"] in FAIL_LIKE)
    return {
        "only_in_before": only_before,
        "only_in_after": only_after,
        "flipped": flipped,
        "counts": {
            "before_only": len(only_before),
            "after_only": len(only_after),
            "flipped": len(flipped),
            "flipped_to_pass": to_pass,
            "flipped_to_fail": to_fail,
        },
    }


def difference_nonempty(diff: dict[str, Any]) -> bool:
    c = diff.get("counts") or {}
    return int(c.get("before_only") or 0) + int(c.get("after_only") or 0) + int(c.get("flipped") or 0) > 0


def cancelling_pair_holds(
    before: Iterable[dict[str, Any]], after: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """One flip each way, aggregate counts unchanged, set difference nonempty."""
    before_l = list(before)
    after_l = list(after)
    diff = symmetric_difference(before_l, after_l)
    c = diff["counts"]
    unchanged = aggregate_counts_unchanged(before_l, after_l)
    each_way = int(c["flipped_to_pass"]) >= 1 and int(c["flipped_to_fail"]) >= 1
    return {
        "constructed": True,
        "aggregate_count_unchanged": unchanged,
        "set_difference_nonempty": difference_nonempty(diff),
        "flipped_each_way": each_way,
        "symmetric_difference": diff,
        "visible_counts_before": visible_counts(before_l),
        "visible_counts_after": visible_counts(after_l),
        "holds": unchanged and difference_nonempty(diff) and each_way,
    }


def collection_errors_are_separate(members: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(members)
    c = counts_of(rows)
    err_ids = [m["id"] for m in rows if m.get("outcome") == "collection_error"]
    fail_ids = [m["id"] for m in rows if m.get("outcome") == "failed"]
    overlap = sorted(set(err_ids) & set(fail_ids))
    suite_passed = c["failed"] == 0 and c["error"] == 0 and c["collection_error"] == 0
    return {
        "collection_error_count": c["collection_error"],
        "failed_count": c["failed"],
        "counted_separately_from_failures": c["collection_error"] > 0 and not overlap,
        "overlap_ids": overlap,
        "suite_classified_passed": suite_passed,
        "suite_not_classified_passed": (not suite_passed) and c["collection_error"] > 0,
        "holds": c["collection_error"] > 0 and not overlap and not suite_passed,
    }


def outcome_set(label: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(members, key=lambda m: str(m.get("id") or ""))
    return {"label": label, "members": ordered, "counts": counts_of(ordered)}
