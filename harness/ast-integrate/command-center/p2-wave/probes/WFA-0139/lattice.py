"""Most-restrictive-wins license lattice with fail-closed unknown handling.

Rule indices are load-bearing: every fusion verdict must cite the rule it
applied. UNKNOWN never collapses to PERMISSIVE.
"""
from __future__ import annotations

from typing import Any, Iterable

# Higher rank wins a join. UNKNOWN sits at the top so it cannot be ignored,
# but combine() treats it as BLOCKED rather than as an outbound class.
RANK: dict[str, int] = {
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

COPYLEFT = frozenset({"WEAK_COPYLEFT", "STRONG_COPYLEFT", "NETWORK_COPYLEFT"})

UNKNOWN_TOKENS = frozenset(
    {"", "UNKNOWN", "NOASSERTION", "UNCLASSIFIED", "NONE", "LicenseRef-unknown"}
)
PROPRIETARY_TOKENS = frozenset(
    {
        "ALL-RIGHTS-RESERVED",
        "PROPRIETARY",
        "UNLICENSED",
        "LicenseRef-proprietary",
    }
)
OWNER_TOKENS = frozenset({"OWNER", "LicenseRef-owner"})

SPDX_CLASS: dict[str, str] = {
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
}

RULES: list[dict[str, Any]] = [
    {
        "index": 1,
        "id": "R1-SPDX-CLASS",
        "title": "Map a known SPDX token onto a lattice class",
        "fail_closed": False,
    },
    {
        "index": 2,
        "id": "R2-UNKNOWN-FAIL-CLOSED",
        "title": "Missing, UNKNOWN, or UNCLASSIFIED license never defaults to permissive",
        "fail_closed": True,
    },
    {
        "index": 3,
        "id": "R3-RIDER-RESTRICTED",
        "title": "A vendor rider or field-of-use restriction is RIDER-RESTRICTED regardless of SPDX",
        "fail_closed": True,
    },
    {
        "index": 4,
        "id": "R4-ATTRIBUTION-CREDIT",
        "title": "Attribution, NOTICE, and CC-BY credits must carry through fusion",
        "fail_closed": False,
    },
    {
        "index": 5,
        "id": "R5-OWNER-INHERITS-DEPS",
        "title": "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY inherits the most-restrictive dependency class",
        "fail_closed": False,
    },
    {
        "index": 6,
        "id": "R6-MOST-RESTRICTIVE-WINS",
        "title": "Join is max(rank); a copyleft+permissive pair yields copyleft",
        "fail_closed": False,
    },
    {
        "index": 7,
        "id": "R7-PROHIBITED-OR-UNRESOLVED",
        "title": "Copyleft+proprietary and any rider fusion are PROHIBITED; unresolved source license BLOCKS",
        "fail_closed": True,
    },
]


def _norm_spdx(token: Any) -> str:
    if token is None:
        return ""
    return str(token).strip()


def spdx_to_class(token: Any) -> str:
    spdx = _norm_spdx(token)
    if spdx in UNKNOWN_TOKENS:
        return "UNKNOWN"
    if spdx in PROPRIETARY_TOKENS:
        return "PROPRIETARY"
    if spdx in OWNER_TOKENS:
        return "OWNER_AUTHORED"
    return SPDX_CLASS.get(spdx, "UNKNOWN")


def is_copyleft(cls: str) -> bool:
    return cls in COPYLEFT


def pair_prohibited(a: str, b: str) -> bool:
    """R7: rider cannot be fused for redistribution; copyleft cannot absorb proprietary."""
    if a == "RIDER_RESTRICTED" or b == "RIDER_RESTRICTED":
        return True
    if is_copyleft(a) and b == "PROPRIETARY":
        return True
    if is_copyleft(b) and a == "PROPRIETARY":
        return True
    return False


def prohibited_class_pairs() -> list[list[str]]:
    names = [k for k in RANK if k != "UNKNOWN"]
    out: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for a in names:
        for b in names:
            if not pair_prohibited(a, b):
                continue
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            out.append([key[0], key[1]])
    return out


def _credit_key(credit: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(credit.get("id") or ""),
        str(credit.get("holder") or ""),
        str(credit.get("notice") or ""),
    )


def credits_required(row: dict[str, Any], cls: str) -> list[dict[str, Any]]:
    required = bool(row.get("attribution_required"))
    if cls in {"ATTRIBUTION_REQUIRED", "WEAK_COPYLEFT"} and row.get("credits"):
        required = True
    if str(row.get("spdx") or "").startswith("CC-BY"):
        required = True
    if not required:
        return []
    credits = row.get("credits") or []
    return [c for c in credits if isinstance(c, dict)]


def effective_class(
    row: dict[str, Any],
    register: dict[str, dict[str, Any]],
    seen: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Classify one register row. Cycle or missing dep → UNKNOWN (R2)."""
    rid = str(row.get("id") or "")
    walked = seen or frozenset()
    if rid and rid in walked:
        return {
            "id": rid,
            "class": "UNKNOWN",
            "rank": RANK["UNKNOWN"],
            "rules_applied": [2],
            "reason": "dependency-cycle",
        }
    rules: list[int] = []
    if row.get("unresolved_license") is True:
        # R2 UNKNOWN-FAIL-CLOSED: unresolved input, never permissive default.
        return {
            "id": rid,
            "class": "UNKNOWN",
            "rank": RANK["UNKNOWN"],
            "rules_applied": [2],
            "reason": "unresolved-license",
        }
    if row.get("rider"):
        rules.append(3)
        cls = "RIDER_RESTRICTED"
    else:
        cls = spdx_to_class(row.get("spdx"))
        if cls == "UNKNOWN":
            return {
                "id": rid,
                "class": "UNKNOWN",
                "rank": RANK["UNKNOWN"],
                "rules_applied": [2],
                "reason": "unknown-spdx",
            }
        rules.append(1)
        origin = str(row.get("origin_class") or "")
        if origin == "ATTRIBUTION-REQUIRED" or row.get("attribution_required"):
            if RANK[cls] < RANK["ATTRIBUTION_REQUIRED"]:
                cls = "ATTRIBUTION_REQUIRED"
            if 4 not in rules:
                rules.append(4)
        if str(row.get("spdx") or "").startswith("CC-BY"):
            if 4 not in rules:
                rules.append(4)
            if row.get("spdx") == "CC-BY-4.0" and RANK[cls] < RANK["ATTRIBUTION_REQUIRED"]:
                cls = "ATTRIBUTION_REQUIRED"
    deps = [str(d) for d in (row.get("external_deps") or []) if d]
    origin = str(row.get("origin_class") or "")
    if origin == "OWNER-AUTHORED-WITH-EXTERNAL-DEPENDENCY" or deps:
        rules.append(5)
        nxt = walked | ({rid} if rid else frozenset())
        for dep_id in deps:
            dep = register.get(dep_id)
            if dep is None:
                return {
                    "id": rid,
                    "class": "UNKNOWN",
                    "rank": RANK["UNKNOWN"],
                    "rules_applied": sorted(set(rules + [2, 5])),
                    "reason": f"missing-dep:{dep_id}",
                }
            child = effective_class(dep, register, nxt)
            if child["class"] == "UNKNOWN":
                return {
                    "id": rid,
                    "class": "UNKNOWN",
                    "rank": RANK["UNKNOWN"],
                    "rules_applied": sorted(set(rules + child["rules_applied"] + [2])),
                    "reason": f"unresolved-dep:{dep_id}",
                }
            if RANK[child["class"]] > RANK[cls]:
                cls = child["class"]
            rules.extend(child["rules_applied"])
    return {
        "id": rid,
        "class": cls,
        "rank": RANK[cls],
        "rules_applied": sorted(set(rules)),
        "reason": "classified",
    }


def fuse(
    source_rows: Iterable[dict[str, Any]],
    register: dict[str, dict[str, Any]],
    *,
    unresolved_ids: Iterable[str] | None = None,
    carried_credits: list[dict[str, Any]] | None = None,
    fusion_id: str = "",
) -> dict[str, Any]:
    """Join source licenses. Unresolved or UNKNOWN → BLOCKED, never permissive."""
    rows = list(source_rows)
    unresolved = [str(x) for x in (unresolved_ids or []) if x]
    rules: list[int] = []
    if unresolved:
        return {
            "fusion_id": fusion_id,
            "status": "BLOCKED",
            "result_class": None,
            "result_rank": None,
            "rules_applied": [7, 2],
            "reason": "unresolved-source-license",
            "unresolved_ids": unresolved,
            "source_classes": [],
            "source_class_set": [],
            "multi_class": False,
            "credits_required": [],
            "credits_carried": [],
            "credits_lost": [],
            "attribution_lost": False,
            "prohibited": False,
        }
    effectives = [effective_class(row, register) for row in rows]
    source_classes = [e["class"] for e in effectives]
    for e in effectives:
        rules.extend(e["rules_applied"])
    if any(e["class"] == "UNKNOWN" for e in effectives):
        return {
            "fusion_id": fusion_id,
            "status": "BLOCKED",
            "result_class": None,
            "result_rank": None,
            "rules_applied": sorted(set(rules + [2, 7])),
            "reason": "unknown-license-fail-closed",
            "unresolved_ids": [],
            "source_classes": source_classes,
            "source_class_set": sorted(set(source_classes)),
            "multi_class": len(set(source_classes)) > 1,
            "credits_required": [],
            "credits_carried": [],
            "credits_lost": [],
            "attribution_lost": False,
            "prohibited": False,
        }
    required: list[dict[str, Any]] = []
    seen_credits: set[tuple[str, str, str]] = set()
    for row, eff in zip(rows, effectives):
        for credit in credits_required(row, eff["class"]):
            key = _credit_key(credit)
            if key in seen_credits:
                continue
            seen_credits.add(key)
            required.append(credit)
        if credits_required(row, eff["class"]) and 4 not in rules:
            rules.append(4)
    if len(rows) >= 2:
        rules.append(6)
    classes = source_classes
    for i, a in enumerate(classes):
        for b in classes[i + 1 :]:
            if pair_prohibited(a, b):
                return {
                    "fusion_id": fusion_id,
                    "status": "PROHIBITED",
                    "result_class": None,
                    "result_rank": None,
                    "rules_applied": sorted(set(rules + [7])),
                    "reason": f"prohibited:{a}+{b}",
                    "unresolved_ids": [],
                    "source_classes": source_classes,
                    "source_class_set": sorted(set(source_classes)),
                    "multi_class": len(set(source_classes)) > 1,
                    "credits_required": required,
                    "credits_carried": [],
                    "credits_lost": required,
                    "attribution_lost": bool(required),
                    "prohibited": True,
                    "suggested_alternative": "CLEAN-ROOM-REIMPLEMENT",
                }
    winner = max(effectives, key=lambda e: e["rank"])
    carried = required if carried_credits is None else list(carried_credits)
    carried_keys = {_credit_key(c) for c in carried}
    lost = [c for c in required if _credit_key(c) not in carried_keys]
    if lost and 4 not in rules:
        rules.append(4)
    return {
        "fusion_id": fusion_id,
        "status": "ALLOWED",
        "result_class": winner["class"],
        "result_rank": winner["rank"],
        "rules_applied": sorted(set(rules)),
        "reason": "most-restrictive-wins",
        "unresolved_ids": [],
        "source_classes": source_classes,
        "source_class_set": sorted(set(source_classes)),
        "multi_class": len(set(source_classes)) > 1,
        "credits_required": required,
        "credits_carried": carried,
        "credits_lost": lost,
        "attribution_lost": bool(lost),
        "prohibited": False,
    }


def fuse_merge_unit(
    unit: dict[str, Any], register: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    declared = [str(x) for x in (unit.get("sources_declared") or [])]
    unresolved = [str(x) for x in (unit.get("sources_unresolved") or [])]
    missing = [sid for sid in declared if sid not in register and sid not in unresolved]
    unresolved_all = list(dict.fromkeys(unresolved + missing))
    rows = [register[sid] for sid in declared if sid in register]
    carried = unit.get("carried_credits")
    if "carried_credits" not in unit:
        carried = None
    verdict = fuse(
        rows,
        register,
        unresolved_ids=unresolved_all,
        carried_credits=carried,
        fusion_id=str(unit.get("id") or ""),
    )
    verdict["sources_declared"] = declared
    verdict["sources_unresolved"] = unresolved
    verdict["sources_resolved_in_registry"] = [
        sid for sid in declared if sid in register and sid not in unresolved
    ]
    return verdict
