#!/usr/bin/env python3
"""Both-directions least-privilege reconciliation.

Direction A: declared grant minus observed use -> UNEXERCISED
  (never OVER-GRANT; absence in the window is not proof the grant is unnecessary).
Direction B: observed use minus declared grant -> UNDER-DECLARATION
  (includes DENY records: the attempt is observed use).

A single compliance percentage is not a verdict and is not emitted.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from enforcement import Permission, Record, matches

MIN_EXECUTIONS = 12
OVERGRANT_FORBIDDEN_LABEL = "OVER-GRANT"


def observed_keys(records: Iterable[Record]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for rec in records:
        out[rec.capability_id].add(rec.permission)
    return dict(out)


def parse_key(key: str) -> Permission:
    cls, name = key.split(":", 1)
    return Permission(cls, name, "grant")


def grant_covers(declared: list[Permission], observed_key: str) -> bool:
    requested = parse_key(observed_key)
    return any(p.effect == "grant" and matches(p, requested) for p in declared)


def observed_covers_grant(seen: set[str], grant: Permission) -> bool:
    return any(matches(grant, parse_key(key)) for key in seen)


def grant_rows(declared: list[Permission]) -> list[Permission]:
    return [p for p in declared if p.effect == "grant"]


def label_declared_not_observed(sample_adequate: bool) -> str:
    """Production classifier. Mutants that return OVER-GRANT are wrong."""
    if not sample_adequate:
        return "NOT-CHECKED"
    return "UNEXERCISED"


def label_observed_not_declared(sample_adequate: bool) -> str:
    if not sample_adequate:
        return "NOT-CHECKED"
    return "UNDER-DECLARATION"


def adequacy(sample_size: int) -> str:
    if sample_size <= 0:
        return "NO-RECORDS"
    if sample_size < MIN_EXECUTIONS:
        return "INADEQUATE"
    return "ADEQUATE"


def reconcile(
    capabilities: dict[str, list[Permission]],
    records: list[Record],
    window_id: str,
) -> dict:
    sample_size = len(records)
    adeq = adequacy(sample_size)
    adequate = adeq == "ADEQUATE"
    obs = observed_keys(records)
    dir_a: list[dict] = []
    dir_b: list[dict] = []
    matched: list[dict] = []
    for cap_id, declared in sorted(capabilities.items()):
        grants = grant_rows(declared)
        seen = obs.get(cap_id, set())
        for grant in sorted(grants, key=lambda p: p.key()):
            row = {
                "capability_id": cap_id,
                "permission": grant.key(),
                "window_id": window_id,
            }
            if observed_covers_grant(seen, grant):
                row["label"] = (
                    "EXERCISED-AND-DECLARED" if adequate else "NOT-CHECKED"
                )
                matched.append(row)
            else:
                row["label"] = label_declared_not_observed(adequate)
                dir_a.append(row)
        for perm in sorted(seen):
            if grant_covers(declared, perm):
                continue
            dir_b.append(
                {
                    "capability_id": cap_id,
                    "permission": perm,
                    "label": label_observed_not_declared(adequate),
                    "window_id": window_id,
                }
            )
    if any(row["label"] == OVERGRANT_FORBIDDEN_LABEL for row in dir_a):
        raise AssertionError("UNEXERCISED must not be reported as OVER-GRANT")
    return {
        "window_id": window_id,
        "sample_size": sample_size,
        "min_executions": MIN_EXECUTIONS,
        "adequacy": adeq,
        "sample_adequate": adequate,
        "declared_not_observed": dir_a,
        "observed_not_declared": dir_b,
        "exercised_and_declared": matched,
        "deny_count": sum(1 for r in records if r.decision == "DENY"),
        "allow_count": sum(1 for r in records if r.decision == "ALLOW"),
        "enforcement_points": sorted({r.enforcement_point for r in records}),
        "verdict_shape": "two-directions",
    }


def mutant_unexercised_as_overgrant(sample_adequate: bool) -> str:
    """Known-wrong classifier used as a negative control."""
    if not sample_adequate:
        return "NOT-CHECKED"
    return OVERGRANT_FORBIDDEN_LABEL
