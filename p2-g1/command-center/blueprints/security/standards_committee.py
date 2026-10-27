"""Standards committee: unmet least-privilege is REJECT."""
from __future__ import annotations

from typing import Any


def review(proposal: dict[str, Any]) -> dict[str, Any]:
    claims = proposal.get("claims") if isinstance(proposal.get("claims"), dict) else {}
    cited = [str(x) for x in (proposal.get("cited_standards") or [])]
    unmet = False
    if "least-privilege" in cited and claims.get("permissions_subset") is False:
        unmet = True
    verdict = "REJECT" if unmet else "ACCEPT"
    return {
        "proposal_id": proposal.get("proposal_id"),
        "verdict": verdict,
        "cited_standards": cited,
        "unmet_least_privilege": unmet,
    }
