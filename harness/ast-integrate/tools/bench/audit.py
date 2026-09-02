"""Audit merged commits against the decision ledger (TST-0311).

Every merged change must have a gate decision on the ledger, and that
decision must be KEEP. Finding kinds:

* ``BYPASS`` - merged with no gate decision recorded for the change or sha.
* ``UNAUTHORIZED-RETENTION`` - merged although the gate said REVERT.
* ``MERGED-WITHOUT-EVIDENCE`` - merged although the gate said
  INSUFFICIENT-EVIDENCE (no KEEP was ever earned).

An unmerged change is checked but never a finding.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

KIND_BYPASS = "BYPASS"
KIND_RETENTION = "UNAUTHORIZED-RETENTION"
KIND_NO_EVIDENCE = "MERGED-WITHOUT-EVIDENCE"
# Kept for callers that grep the older descriptive label.
LEGACY_BYPASS_LABEL = "merge-without-gate-decision"


def _lookup(ledger: Any, cid: str, sha: str) -> dict[str, Any] | None:
    if ledger is None:
        return None
    row = None
    if hasattr(ledger, "get"):
        if cid:
            row = ledger.get(cid)
        if row is None and sha:
            row = ledger.get(sha)
    if row is None and hasattr(ledger, "rows"):
        for cand in ledger.rows() or []:
            if (cid and cand.get("change_id") == cid) or (sha and cand.get("commit_sha") == sha):
                row = cand
                break
    if row is not None and sha and row.get("commit_sha") and str(row.get("commit_sha")) != sha:
        # A decision for the change id that was made on a different commit
        # does not authorise this merge.
        return None
    return dict(row) if row is not None else None


def _ledger_size(ledger: Any) -> int | None:
    for attr in ("rows", "all", "records"):
        fn = getattr(ledger, attr, None)
        if callable(fn):
            try:
                return len(fn())
            except Exception:  # pragma: no cover - defensive
                continue
    try:
        return len(ledger)
    except Exception:
        return None


def audit_commit_range(
    commits: Iterable[Mapping[str, Any]],
    ledger: Any,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    bypass_ids: list[str] = []
    retained_ids: list[str] = []
    checked = 0
    for commit in commits:
        checked += 1
        if not commit.get("merged"):
            continue
        cid = str(commit.get("change_id") or "")
        sha = str(commit.get("commit_sha") or "")
        row = _lookup(ledger, cid, sha)
        ident = cid or sha
        if row is None:
            bypass_ids.append(ident)
            findings.append(
                {
                    "kind": KIND_BYPASS,
                    "label": LEGACY_BYPASS_LABEL,
                    "change_id": cid,
                    "commit_sha": sha,
                    "detail": "merged with no gate decision on the ledger",
                }
            )
            continue
        outcome = str(row.get("outcome") or "").upper()
        if outcome == "KEEP":
            continue
        kind = KIND_RETENTION if outcome == "REVERT" else KIND_NO_EVIDENCE
        retained_ids.append(ident)
        findings.append(
            {
                "kind": kind,
                "change_id": cid,
                "commit_sha": sha,
                "gate_outcome": outcome or "UNKNOWN",
                "reason_id": row.get("reason_id"),
                "detail": f"merged although the gate decided {outcome or 'nothing'}",
            }
        )
    return {
        "ok": not findings,
        "findings": findings,
        "bypass_ids": bypass_ids,
        "retained_ids": retained_ids,
        "checked": checked,
        "ledger_size": _ledger_size(ledger),
    }
