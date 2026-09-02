"""Resolve extracted claims against the results ledger.

Resolution is attempted before any unbacked verdict. A cited run that
actually failed is contradicted — the most severe class, listed first.
"""
from __future__ import annotations

from typing import Any

from ledger import commits_match, run_passed

CONTRADICTED = "contradicted"
UNRESOLVED = "unresolved"
RESOLVED = "resolved"
CLASS_ORDER = (CONTRADICTED, UNRESOLVED, RESOLVED)


def _lookup(ledger: dict[str, Any], run_id: str) -> dict[str, Any] | None:
    if not run_id:
        return None
    return (ledger.get("by_run_id") or {}).get(run_id)


def _unit_runs(ledger: dict[str, Any], unit_id: str) -> list[dict[str, Any]]:
    if not unit_id:
        return []
    return list((ledger.get("by_unit_id") or {}).get(unit_id) or [])


def resolve_claim(
    claim: dict[str, Any],
    ledger: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Always consults the ledger before returning unresolved."""
    lookups: list[str] = []
    # lookups.append records every ledger consult so unbacked never precedes a read
    run_id = str(claim.get("run_id") or "")
    commit = str(claim.get("commit") or "").lower()
    unit_id = str(claim.get("authoring_unit") or "")
    row = None
    source = ""

    lookups.append("by_run_id")
    if run_id:
        row = _lookup(ledger, run_id)
        if row:
            source = "cited-run-id"

    if row is None:
        lookups.append("registry")
        reg = registry or {}
        mapped = (reg.get("by_unit_id") or {}).get(unit_id) or ""
        if mapped:
            lookups.append("by_run_id")
            row = _lookup(ledger, mapped)
            if row:
                run_id = mapped
                source = "test-registry-unit"

    if row is None:
        lookups.append("by_unit_id")
        candidates = _unit_runs(ledger, unit_id)
        if commit:
            for cand in candidates:
                if commits_match(commit, cand.get("commit") or ""):
                    row = cand
                    run_id = cand["run_id"]
                    source = "unit-id-commit"
                    break
        elif len(candidates) == 1:
            row = candidates[0]
            run_id = row["run_id"]
            source = "unit-id-unique"

    out = {
        **claim,
        "resolution_attempted": True,
        "ledger_present": bool(ledger.get("present")),
        "ledger_lookups": lookups,
        "resolved_run_id": run_id or None,
        "resolved_commit": (row or {}).get("commit") or None,
        "resolution_source": source or None,
        "ledger_row_status": (row or {}).get("status") if row else None,
    }

    if row is None:
        out["class"] = UNRESOLVED
        out["reason"] = (
            "ledger-row-absent" if ledger.get("present") else "ledger-absent-after-lookup"
        )
        return out

    passed = run_passed(row)
    row_ok = passed is True
    row_fail = passed is False
    row_commit = str(row.get("commit") or "")

    # if row_ok is False: cited run failed — contradicted, listed first
    if row_fail:
        out["class"] = CONTRADICTED
        out["reason"] = "cited-run-failed"
        return out

    if not row_ok:
        out["class"] = UNRESOLVED
        out["reason"] = "ledger-status-unknown"
        return out

    if not row_commit:
        out["class"] = UNRESOLVED
        out["reason"] = "ledger-row-missing-commit"
        return out

    if commit and not commits_match(commit, row_commit):
        out["class"] = UNRESOLVED
        out["reason"] = "commit-mismatch"
        return out

    out["class"] = RESOLVED
    out["reason"] = "run-pass-commit-pinned"
    out["resolved_commit"] = row_commit
    return out


def classify_claims(
    claims: list[dict[str, Any]],
    ledger: dict[str, Any],
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classified = [resolve_claim(c, ledger, registry) for c in claims]
    buckets = {name: [] for name in CLASS_ORDER}
    for row in classified:
        buckets[row["class"]].append(row)

    defects = []
    for cls in (CONTRADICTED, UNRESOLVED):
        for row in buckets[cls]:
            defects.append(
                {
                    "authoring_unit": row.get("authoring_unit") or "UNKNOWN",
                    "class": cls,
                    "form": row.get("form"),
                    "path": row.get("path"),
                    "line": row.get("line"),
                    "text": row.get("text"),
                    "reason": row.get("reason"),
                    "run_id": row.get("resolved_run_id") or row.get("run_id"),
                }
            )

    counts = {name: len(buckets[name]) for name in CLASS_ORDER}
    counts["found"] = len(classified)
    return {
        "classes_in_severity_order": list(CLASS_ORDER),
        "counts": counts,
        "contradicted": buckets[CONTRADICTED],
        "unresolved": buckets[UNRESOLVED],
        "resolved": buckets[RESOLVED],
        "defects": defects,
        "all": classified,
        "every_unbacked_attempted_resolution": all(
            r.get("resolution_attempted") is True for r in classified
        )
        if classified
        else True,
    }
