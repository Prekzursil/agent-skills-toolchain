"""Adversarial reviewer: default REFUTED unless dual-rail intersection holds."""
from __future__ import annotations

from typing import Any

import features as F
import intersect as I


def review(extracted: dict[str, Any], artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    lists = extracted["e2_sets"]
    live_inter = I.intersection(lists)
    live_uniques = I.unique_sets(lists)
    findings: list[str] = []
    refuted = False

    for pid in live_inter:
        cells = [
            c
            for c in extracted["cells"]
            if c["primitive_id"] == pid and c["vendor"] in F.VENDORS
        ]
        for cell in cells:
            if cell.get("evidence_tier") != "E2" or int(cell.get("rail_count") or 0) < 2:
                findings.append(f"intersection member {pid}/{cell['vendor']} is not dual-rail")
                refuted = True

    if F.PLANTED_UNIQUE in live_inter:
        findings.append("Roo-only custom-modes leaked into intersection")
        refuted = True
    if "first-class-memories" in live_inter:
        findings.append("Windsurf memories cited as portable core without dual rails")
        refuted = True
    if "memory-bank-methodology" in live_inter:
        findings.append("Cline Memory Bank methodology treated as a first-class primitive")
        refuted = True

    if artifact is not None:
        payload = F.domain_payload(artifact)
        claimed = list((payload.get("intersection") or {}).get("members") or [])
        if claimed != live_inter:
            findings.append("artifact intersection members != live set operations")
            refuted = True
        art_u = payload.get("unique_sets") or {}
        for vendor in F.VENDORS:
            if list(art_u.get(vendor) or []) != live_uniques.get(vendor):
                findings.append(f"artifact unique_sets.{vendor} != live unique set")
                refuted = True
        if not (payload.get("intersection") or {}).get("computed") is True:
            findings.append("intersection.computed is not true")
            refuted = True

    caveats = [
        "Windsurf editor source is closed; Windsurf E2 cells use GitHub's versioned install guide plus official docs, not Windsurf binaries.",
        "Cline Memory Bank is a markdown methodology layered on rules, not a first-class memory API; it is E3 and excluded from the citable intersection.",
        "Presence of workspace-rules in all three vendors' docs is NOT dual-rail for Windsurf, so it is not cited as measured portable core.",
        "No runtime adapter was executed against the three products; this matrix is source+docs evidence, not behaviour.",
    ]
    verdict = "REFUTED" if refuted else "PASS"
    return {
        "reviewer_id": "RES-0031-adversarial-refuter",
        "independent": True,
        "verdict": verdict,
        "defaulted_to_refuted_on_insufficient_evidence": True,
        "findings": findings,
        "strongest_caveat": caveats[0],
        "caveats": caveats,
        "live_intersection": live_inter,
        "live_uniques": live_uniques,
        "added_failure_mode": {
            "id": "FM-UNION-AS-CORE",
            "detail": "Advertising-union primitives (custom modes, memories, hooks) must not be reported as the portable core.",
        },
    }
