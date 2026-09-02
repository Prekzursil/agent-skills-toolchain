"""No-retirement-before-proof gate.

A removal of an old rail is allowed only when the record cites the passing
differential run id AND its sha256. Timestamps do not authorise retirement.
"""
from __future__ import annotations

from typing import Any, Mapping


def evaluate(record: Mapping[str, Any], passing: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    rail = str(record.get("rail_id") or "")
    run = passing.get(rail)
    cited_id = str(record.get("differential_run_id") or "")
    cited_sha = str(record.get("differential_sha256") or "")
    if not isinstance(run, Mapping):
        return {
            "allowed": False,
            "reason": "RETIRE-WITHOUT-PROOF",
            "detail": f"no passing differential for rail {rail!r}",
            "rail_id": rail,
        }
    if cited_id == run.get("id") and cited_sha == run.get("sha256") and cited_sha:
        return {
            "allowed": True,
            "reason": "PROOF-CITED",
            "rail_id": rail,
            "cited_run_id": cited_id,
            "cited_sha256": cited_sha,
        }
    return {
        "allowed": False,
        "reason": "RETIRE-WITHOUT-PROOF",
        "detail": (
            f"cited id={cited_id!r} sha={cited_sha!r} "
            f"want id={run.get('id')!r} sha={run.get('sha256')!r}"
        ),
        "rail_id": rail,
        "cited_run_id": cited_id,
        "cited_sha256": cited_sha,
    }


def note_text(passing: Mapping[str, Mapping[str, Any]]) -> str:
    """Commit-message-shaped citation. Probe 2 awk-reads Differential-Sha256."""
    lines = [
        "ARC-0042 no-retirement-before-proof",
        "",
        "A removal commit of an old Codex rail must cite the passing differential.",
        "",
    ]
    for rail in ("mcp-thread", "exec-fanout", "agent-mail"):
        run = passing[rail]
        lines.extend(
            [
                f"Rail: {rail}",
                f"Differential-Run: {run['id']}",
                f"Differential-Sha256: {run['sha256']}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"
