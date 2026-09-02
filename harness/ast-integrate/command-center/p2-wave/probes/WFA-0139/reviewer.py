"""Independent reviewer: recompute joins from a second rank table, not author prose."""
from __future__ import annotations

from typing import Any

import lattice as L
import seed as S

# Second copy of the rank table. Drift against lattice.RANK is a probe failure.
RANK = {
    "PUBLIC_DOMAIN": 0,
    "OWNER_AUTHORED": 0,
    "PERMISSIVE": 1,
    "ATTRIBUTION_REQUIRED": 2,
    "WEAK_COPYLEFT": 3,
    "STRONG_COPYLEFT": 4,
    "NETWORK_COPYLEFT": 5,
    "RIDER_RESTRICTED": 6,
    "PROPRIETARY": 7,
    "UNKNOWN": 8,
}

SPDX = {
    "CC0-1.0": "PUBLIC_DOMAIN",
    "Unlicense": "PUBLIC_DOMAIN",
    "0BSD": "PUBLIC_DOMAIN",
    "MIT": "PERMISSIVE",
    "MIT-0": "PERMISSIVE",
    "Apache-2.0": "PERMISSIVE",
    "BSD-2-Clause": "PERMISSIVE",
    "BSD-3-Clause": "PERMISSIVE",
    "ISC": "PERMISSIVE",
    "CC-BY-4.0": "ATTRIBUTION_REQUIRED",
    "CC-BY-SA-4.0": "WEAK_COPYLEFT",
    "MPL-2.0": "WEAK_COPYLEFT",
    "LGPL-2.1-only": "WEAK_COPYLEFT",
    "LGPL-3.0-only": "WEAK_COPYLEFT",
    "GPL-2.0-only": "STRONG_COPYLEFT",
    "GPL-3.0-only": "STRONG_COPYLEFT",
    "AGPL-3.0-only": "NETWORK_COPYLEFT",
    "ALL-RIGHTS-RESERVED": "PROPRIETARY",
    "PROPRIETARY": "PROPRIETARY",
    "UNLICENSED": "PROPRIETARY",
    "OWNER": "OWNER_AUTHORED",
    "": "UNKNOWN",
}


def independent_spdx_class(token: str) -> str:
    return SPDX.get(str(token or "").strip(), "UNKNOWN")


def independent_copyleft(cls: str) -> bool:
    return cls in {"WEAK_COPYLEFT", "STRONG_COPYLEFT", "NETWORK_COPYLEFT"}


def independent_prohibited(a: str, b: str) -> bool:
    if a == "RIDER_RESTRICTED" or b == "RIDER_RESTRICTED":
        return True
    if independent_copyleft(a) and b == "PROPRIETARY":
        return True
    if independent_copyleft(b) and a == "PROPRIETARY":
        return True
    return False


def independent_effective(
    row: dict[str, Any],
    register: dict[str, dict[str, Any]],
    seen: frozenset[str] | None = None,
) -> str:
    rid = str(row.get("id") or "")
    walked = seen or frozenset()
    if rid and rid in walked:
        return "UNKNOWN"
    if row.get("unresolved_license") is True:
        return "UNKNOWN"
    if row.get("rider"):
        return "RIDER_RESTRICTED"
    cls = independent_spdx_class(str(row.get("spdx") or ""))
    if cls == "UNKNOWN":
        return "UNKNOWN"
    if row.get("attribution_required") and RANK[cls] < RANK["ATTRIBUTION_REQUIRED"]:
        cls = "ATTRIBUTION_REQUIRED"
    deps = [str(d) for d in (row.get("external_deps") or []) if d]
    if str(row.get("origin_class") or "") == "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY" or deps:
        nxt = walked | ({rid} if rid else frozenset())
        for dep_id in deps:
            dep = register.get(dep_id)
            if dep is None:
                return "UNKNOWN"
            child = independent_effective(dep, register, nxt)
            if child == "UNKNOWN":
                return "UNKNOWN"
            if RANK[child] > RANK[cls]:
                cls = child
    return cls


def independent_fuse(unit: dict[str, Any], register: dict[str, dict[str, Any]]) -> dict[str, Any]:
    declared = [str(x) for x in (unit.get("sources_declared") or [])]
    unresolved = [str(x) for x in (unit.get("sources_unresolved") or [])]
    missing = [sid for sid in declared if sid not in register and sid not in unresolved]
    if unresolved or missing:
        return {"status": "BLOCKED", "result_class": None, "attribution_lost": False}
    classes = []
    for sid in declared:
        classes.append(independent_effective(register[sid], register))
    if any(c == "UNKNOWN" for c in classes):
        return {"status": "BLOCKED", "result_class": None, "attribution_lost": False}
    for i, a in enumerate(classes):
        for b in classes[i + 1 :]:
            if independent_prohibited(a, b):
                return {"status": "PROHIBITED", "result_class": None, "attribution_lost": False}
    winner = max(classes, key=lambda c: RANK[c])
    required = []
    for sid in declared:
        row = register[sid]
        cls = independent_effective(row, register)
        if row.get("credits") and (
            row.get("attribution_required")
            or str(row.get("spdx") or "").startswith("CC-BY")
            or cls in {"ATTRIBUTION_REQUIRED", "WEAK_COPYLEFT"}
        ):
            required.extend(row.get("credits") or [])
    if "carried_credits" in unit:
        carried_ids = {str(c.get("id")) for c in (unit.get("carried_credits") or [])}
        lost = [c for c in required if str(c.get("id")) not in carried_ids]
    else:
        lost = []
    return {
        "status": "ALLOWED",
        "result_class": winner,
        "attribution_lost": bool(lost),
    }


def review() -> dict[str, Any]:
    register = S.register_by_id()
    mismatches = []
    for unit in S.merge_units():
        author = L.fuse_merge_unit(unit, register)
        indie = independent_fuse(unit, register)
        if author["status"] != indie["status"]:
            mismatches.append((unit["id"], "status", author["status"], indie["status"]))
        if author.get("result_class") != indie.get("result_class"):
            mismatches.append(
                (unit["id"], "class", author.get("result_class"), indie.get("result_class"))
            )
        if bool(author.get("attribution_lost")) != bool(indie.get("attribution_lost")):
            mismatches.append(
                (
                    unit["id"],
                    "credit",
                    author.get("attribution_lost"),
                    indie.get("attribution_lost"),
                )
            )
    if RANK != L.RANK:
        mismatches.append(("RANK", "table-drift", RANK, L.RANK))
    copyleft = L.fuse(
        [register["LR-01"], register["LR-16"]],
        register,
        fusion_id="review-copyleft",
    )
    unknown = L.fuse(
        [register["LR-01"], register["LR-41"]],
        register,
        fusion_id="review-unknown",
    )
    ok = (
        not mismatches
        and copyleft["status"] == "ALLOWED"
        and copyleft["result_class"] == "STRONG_COPYLEFT"
        and unknown["status"] == "BLOCKED"
        and unknown["result_class"] is None
    )
    return {
        "reviewer_id": "WFA-0139-independent-rank-recompute",
        "independent": True,
        "verdict": "PASS" if ok else "FAIL",
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:12],
        "copyleft_plus_permissive": copyleft["result_class"],
        "unknown_status": unknown["status"],
        "both_states_rerun": True,
    }
