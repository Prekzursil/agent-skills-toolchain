#!/usr/bin/env python3
"""Split-verdict resolution by reading both probes, never by vote.

Reviewers default to REFUTED when evidence is insufficient.
"""
from __future__ import annotations

from typing import Any


def resolve(
    independent: list[dict],
    fusion: list[dict],
    evidence: dict[str, dict],
    votes: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """`votes` is accepted and ignored. A 1-1 split is not a tie-break."""
    _ = votes  # never consulted
    ind = {row["workflow_id"]: row for row in independent}
    fus = {row["workflow_id"]: row for row in fusion}
    rows = []
    for wf, irow in ind.items():
        frow = fus.get(wf) or {}
        ev = evidence.get(wf) or {}
        sufficient = bool(ev.get("sufficient"))
        if not sufficient:
            rows.append(
                {
                    "workflow_id": wf,
                    "agreement": False,
                    "independent": irow.get("verdict"),
                    "fusion": frow.get("verdict"),
                    "chosen": "REFUTED",
                    "which_side_right": None,
                    "resolved_by": "default-REFUTED-insufficient-evidence",
                    "votes_ignored": True,
                }
            )
            continue
        iv, fv = irow.get("verdict"), frow.get("verdict")
        if iv == fv:
            rows.append(
                {
                    "workflow_id": wf,
                    "agreement": True,
                    "independent": iv,
                    "fusion": fv,
                    "chosen": iv,
                    "which_side_right": "both",
                    "resolved_by": "both-probes-agree",
                    "votes_ignored": True,
                }
            )
            continue
        independent_supported = bool(ev.get("independent_supported"))
        fusion_supported = bool(ev.get("fusion_supported"))
        if independent_supported and not fusion_supported:
            winner, chosen, side = "independent", iv, "independent"
        elif fusion_supported and not independent_supported:
            winner, chosen, side = "fusion", fv, "fusion"
        else:
            winner, chosen, side = "neither", "REFUTED", None
        rows.append(
            {
                "workflow_id": wf,
                "agreement": False,
                "independent": iv,
                "fusion": fv,
                "chosen": chosen,
                "which_side_right": side,
                "resolved_by": "read-both-probes-not-vote",
                "supporting_probe": winner,
                "votes_ignored": True,
                "evidence_notes": ev.get("notes"),
            }
        )
    return {
        "rule": (
            "a split verdict is resolved by reading both probes, never by vote "
            "or by seniority; insufficient evidence defaults to REFUTED"
        ),
        "votes_were_supplied": votes is not None,
        "rows": rows,
    }
