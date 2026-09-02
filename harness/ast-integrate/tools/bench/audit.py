"""Audit merged commits against the decision ledger."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def audit_commit_range(
    commits: Iterable[Mapping[str, Any]],
    ledger: Any,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bypass_ids: list[str] = []
    checked = 0
    for commit in commits:
        checked += 1
        if not commit.get("merged"):
            continue
        cid = str(commit.get("change_id") or "")
        sha = str(commit.get("commit_sha") or "")
        row = None
        if hasattr(ledger, "get"):
            row = ledger.get(cid) or ledger.get(sha)
        if row is None:
            bypass_ids.append(cid or sha)
            findings.append(
                {
                    "change_id": cid,
                    "commit_sha": sha,
                    "kind": "merge-without-gate-decision",
                }
            )
    return {
        "ok": not bypass_ids,
        "findings": findings,
        "bypass_ids": bypass_ids,
        "checked": checked,
    }
