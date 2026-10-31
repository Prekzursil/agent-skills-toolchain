"""Overclaim gate for ARC-0054 architecture-review claims."""
from __future__ import annotations

from typing import Any

LOCUS = frozenset({"DESIGN", "SENTENCE"})
VERDICTS = frozenset({"REFUTED", "CONFIRMED", "PARTIAL", "NOT-CHECKED"})
AUTHOR_IDS = {
    "FM-ERROR-NO-NEXT",
    "FM-STOP-UNDOCUMENTED",
    "FM-CATALOG-UNBROWSEABLE",
    "FM-DRYRUN-UNDERSTATES",
    "FM-REPAIR-SILENT",
}
UX_REQUIRED = (
    "error_fail_rejected",
    "error_pass_accepted",
    "stopping_live_undocumented",
    "catalog_live_unbrowseable",
    "dryrun_honest_matches_apply",
    "dryrun_lie_detected",
    "repair_healthy_noop",
    "repair_broken_repaired",
)


def check_overclaim(doc: dict[str, Any]) -> tuple[bool, str]:
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims-missing-or-short"
    refuted = 0
    confirmed = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            return False, f"claims[{i}]-not-object"
        verdict = str(row.get("verdict") or "")
        if verdict not in VERDICTS:
            return False, f"claims[{i}]-bad-verdict:{verdict}"
        if verdict == "REFUTED":
            refuted += 1
            if str(row.get("defect_locus") or "") not in LOCUS:
                return False, f"claims[{i}]-REFUTED-missing-defect_locus"
            if not str(row.get("claim") or "").strip():
                return False, f"claims[{i}]-empty-claim"
        elif verdict == "CONFIRMED":
            confirmed += 1
    if refuted < 1:
        return False, "no-REFUTED-claim"
    if confirmed < 1:
        return False, "no-CONFIRMED-claim"

    modes = doc.get("author_failure_modes") or []
    ids = [m.get("id") for m in modes if isinstance(m, dict)]
    if set(ids) != AUTHOR_IDS:
        return False, f"author-modes-mismatch:{ids}"
    for m in modes:
        if m.get("executable") is not True:
            return False, f"{m.get('id')}-not-executable"
        if m.get("advisory") is True:
            return False, f"{m.get('id')}-advisory-not-allowed"

    added = (doc.get("reviewer") or {}).get("added_failure_mode") or {}
    if added.get("id") != "FM-NEXT-ACTION-UNREACHABLE":
        return False, "reviewer-mode-missing"
    if added.get("id") in AUTHOR_IDS:
        return False, "reviewer-mode-was-author"
    if (doc.get("reviewer") or {}).get("enumeration_certified_against_47") is True:
        return False, "cannot-certify-47-source-absent"

    ux = doc.get("ux_criteria") or {}
    for key in UX_REQUIRED:
        if ux.get(key) is not True:
            return False, f"ux-criterion-unproven:{key}"
    return True, f"refuted={refuted} confirmed={confirmed}"
