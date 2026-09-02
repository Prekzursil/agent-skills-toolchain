#!/usr/bin/env python3
"""Declared compatibility-matrix rows and the CNF-0098 amendment rule.

No on-disk matrix file exists in this worktree (ARC-0095 contract and the
Phase-4 matrix artifact are absent). Rows are reconstructed from catalog
platform-adapter / clean-install units that imply a support claim, then
amended so no cell remains 'supported' without a recorded run.
"""
from __future__ import annotations

DECLARED = [
    {
        "id": "linux-any",
        "os": "linux",
        "arch": "any",
        "client": "any",
        "declared_tier": "supported",
        "declared_by": ["CNF-0097", "IMP-0015"],
    },
    {
        "id": "windows-any",
        "os": "windows",
        "arch": "any",
        "client": "any",
        "declared_tier": "supported",
        "declared_by": ["CNF-0096", "IMP-0013"],
    },
    {
        "id": "macos-any",
        "os": "macos",
        "arch": "any",
        "client": "any",
        "declared_tier": "supported",
        "declared_by": ["CNF-0098", "IMP-0014"],
    },
]

ALLOWED = frozenset({"tested-pass", "tested-fail", "untested"})


def amend(macos_reachable: bool, macos_run: dict | None) -> list[dict]:
    rows = []
    for src in DECLARED:
        row = dict(src)
        os_name = row["os"]
        if os_name == "macos":
            if macos_reachable and macos_run and macos_run.get("ran"):
                row["evidence_state"] = (
                    "tested-pass" if macos_run.get("health_ok") else "tested-fail"
                )
                row["amended_tier"] = row["evidence_state"]
                row["reason"] = macos_run.get("reason") or "install-health-ran"
            else:
                row["evidence_state"] = "untested"
                row["amended_tier"] = "untested"
                row["reason"] = (
                    "macos-runner-unreachable"
                    if not macos_reachable
                    else "reachable-but-install-health-not-run"
                )
        else:
            # Same rule: never leave an unexercised platform as supported.
            row["evidence_state"] = "untested"
            row["amended_tier"] = "untested"
            row["reason"] = "never-exercised-install-health"
        rows.append(row)
    return rows


def assert_honest(rows: list[dict]) -> None:
    if not rows:
        raise AssertionError("matrix rows empty")
    macos_rows = [r for r in rows if r.get("os") == "macos"]
    if not macos_rows:
        raise AssertionError("no macos row in matrix")
    for r in rows:
        st = r.get("evidence_state")
        if st not in ALLOWED:
            raise AssertionError(f"illegal evidence_state {st!r} on {r.get('id')}")
        if str(r.get("declared_tier") or "").lower() == "supported":
            if st not in {"tested-pass", "tested-fail"} and r.get("amended_tier") == "supported":
                raise AssertionError(f"supported without a run: {r.get('id')}")
        if st == "supported":
            raise AssertionError(f"evidence_state still 'supported' on {r.get('id')}")
    for r in macos_rows:
        if r.get("evidence_state") not in ALLOWED:
            raise AssertionError(f"macos row {r.get('id')} missing evidence_state")
