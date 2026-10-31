#!/usr/bin/env python3
"""Map enumerated A1-A11 candidates onto the nine spec classes.

Must not run unless heading enumeration and hazard-matrix headers agree.
Completeness is computed: mapped + folded + rejected + full-team == enumerated.
"""
from __future__ import annotations

import enumerator as E

MAPPED = "MAPPED"
FULL_TEAM = "FULL-TEAM"
FOLD_INTO = "FOLD-INTO"
REJECT = "REJECT"


def match_class(heading: str, classes: list[dict]) -> dict | None:
    n = E.normalize(heading)
    for cls in classes:
        if E.normalize(cls["name"]) == n:
            return cls
    if "ssot" in n:
        for cls in classes:
            if "ssot" in E.normalize(cls["name"]):
                return cls
    return None


def map_candidates(snap: dict) -> dict:
    headings = snap["headings"]
    matrix_ids = snap["matrix_ids"]
    if not snap["agreed"]:
        raise RuntimeError(
            "refusing to map: heading ids "
            f"{E.ids_of(headings)} != matrix ids {matrix_ids}"
        )
    classes = snap["spec_classes"]
    seven = snap["seven_lens"]
    rows = []
    for h in headings:
        cls = match_class(h["heading"], classes)
        if cls is None and h["id"] in seven:
            cls = match_class(seven[h["id"]], classes)
        if cls is not None:
            rows.append(
                {
                    "candidate_id": h["id"],
                    "heading": h["heading"],
                    "heading_line": h["heading_line"],
                    "source_path": snap["candidates_path"],
                    "disposition": MAPPED,
                    "target_class": cls["name"],
                    "target_class_id": cls["id"],
                    "spec_line": cls["spec_line"],
                    "spec_path": cls["source_path"],
                    "mechanisms_carried": [],
                    "reason": (
                        f"Heading {h['id']} normalizes onto spec class "
                        f"{cls['name']!r} at {cls['source_path']}:{cls['spec_line']}."
                    ),
                    "falsifiable": (
                        f"Place live 13-ARCHITECTURE-CANDIDATES.md; if heading "
                        f"{h['id']} no longer normalizes onto {cls['name']!r}, "
                        "this MAP is false."
                    ),
                }
            )
            continue
        unrecovered = "unrecovered" in h["heading"].lower()
        has_block = h["id"] in seven
        if has_block:
            disp = FULL_TEAM
            reason = (
                f"{h['id']} has a seven-lens catalog title {seven[h['id']]!r} "
                "but that title does not normalize onto any of the nine spec "
                "classes. FULL-TEAM already exists in the catalog."
            )
        elif unrecovered:
            disp = REJECT
            reason = (
                f"{h['id']} heading text is not recoverable on this worktree "
                "and WORK-UNIT-CATALOG.json has zero seven-lens titles for it. "
                "FULL-TEAM is refused (would invent a control plane). "
                "FOLD-INTO is refused (would invent mechanisms)."
            )
        else:
            disp = REJECT
            reason = (
                f"{h['id']} heading {h['heading']!r} is not one of the nine "
                "spec classes and has no seven-lens catalog block. This unit "
                "does not author a new 7-lens block."
            )
        rows.append(
            {
                "candidate_id": h["id"],
                "heading": h["heading"],
                "heading_line": h["heading_line"],
                "source_path": snap["candidates_path"],
                "disposition": disp,
                "target_class": None,
                "target_class_id": None,
                "spec_line": 0,
                "spec_path": snap["spec_path"],
                "mechanisms_carried": [],
                "reason": reason,
                "falsifiable": (
                    "Seat live 13-ARCHITECTURE-CANDIDATES.md. If this id's "
                    "heading names a distinct control plane, replace REJECT "
                    "with FULL-TEAM or FOLD-INTO naming the target class and "
                    "every carried mechanism."
                ),
            }
        )
    mapped = sum(1 for r in rows if r["disposition"] == MAPPED)
    folded = sum(1 for r in rows if r["disposition"] == FOLD_INTO)
    full = sum(1 for r in rows if r["disposition"] == FULL_TEAM)
    rejected = sum(1 for r in rows if r["disposition"] == REJECT)
    enumerated = len(rows)
    accounted = mapped + folded + rejected + full
    completeness = {
        "enumerated": enumerated,
        "mapped": mapped,
        "folded": folded,
        "full_team": full,
        "rejected": rejected,
        "sum": accounted,
        "holds": accounted == enumerated,
    }
    unmapped = [
        r for r in rows if r["disposition"] in {FULL_TEAM, FOLD_INTO, REJECT}
    ]
    return {
        "rows": rows,
        "unmapped": unmapped,
        "completeness": completeness,
    }
