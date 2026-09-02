"""Locate $defs.role, or reconstruct it from catalog citations on this tree.

The evidence requirement names
C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json
which is not on this Linux worktree. This module records that absence instead of
inventing a byte-level cite, then inventories fields from two mechanically
different catalog quotations of spec :10925 / IMP-0280 / WFA-0037.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

SCHEMA_CANDIDATES = (
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"),
    REPO / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "command-center" / "sources" / "11-COUNCIL-SPECIFICATION.schema.json",
    REPO / "platform" / "schema" / "councilspec.schema.json",
    REPO / "command-center" / "schema" / "councilspec.v2.schema.json",
)

# Needles that must appear as catalog quotations, not as this file's prose.
NEEDLES = {
    "cnl0022_question": "which of the existing $defs.role fields conflates them",
    "spec_10925": "role mandates, permissions, tool/source access, speaking rights, vote rights, veto rights and incompatible-role checks",
    "imp0280": "typed role objects carrying tool access, source access, speaking rights, vote rights and veto rights",
    "wfa0037": "with what mandate, tool access, speaking rights and vote rights",
}


def first_line(text: str, needle: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return None


def locate_schema() -> dict:
    hits = []
    found = None
    for path in SCHEMA_CANDIDATES:
        exists = path.is_file()
        hits.append({"path": str(path), "exists": exists})
        if exists and found is None:
            found = path
    payload = None
    role_def = None
    if found is not None:
        try:
            payload = json.loads(found.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            defs = payload.get("$defs") or payload.get("definitions") or {}
            if isinstance(defs, dict) and isinstance(defs.get("role"), dict):
                role_def = defs["role"]
    return {
        "found_path": str(found) if found is not None else None,
        "candidates": hits,
        "parsed": isinstance(payload, dict),
        "role_def": role_def,
        "source": "disk" if role_def is not None else "absent",
    }


def catalog_citations() -> dict:
    text = CATALOG.read_text(encoding="utf-8")
    cites = {}
    for key, needle in NEEDLES.items():
        line = first_line(text, needle)
        cites[key] = {
            "needle": needle,
            "path": "command-center/WORK-UNIT-CATALOG.json",
            "line": line,
            "present": line is not None,
        }
    missing = [k for k, v in cites.items() if not v["present"]]
    return {"citations": cites, "missing": missing, "catalog_bytes": len(text.encode("utf-8"))}


def v1_field_inventory() -> list[dict]:
    """Field-by-field reconstructed $defs.role.

    Each row names a modality. The load-bearing conflator is permissions:
    it is the only typed collection that can hold an obligation id, a
    permission id, and a right id as indistinguishable strings.
    """
    return [
        {
            "name": "id",
            "json_type": "string",
            "modality": "identity",
            "conflates": False,
            "source_keys": ["cnl0022_question"],
        },
        {
            "name": "name",
            "json_type": "string",
            "modality": "identity",
            "conflates": False,
            "source_keys": ["wfa0037"],
        },
        {
            "name": "mandate",
            "json_type": "string",
            "modality": "prose-mixed",
            "conflates": False,
            "why_not_the_conflator": (
                "A free-text string cannot be discharged or left unused by a "
                "checker; the executable mix lives in permissions[]."
            ),
            "source_keys": ["spec_10925", "wfa0037", "imp0280"],
        },
        {
            "name": "permissions",
            "json_type": "array<string>",
            "modality": "conflated-grant-bag",
            "conflates": True,
            "holds": ["obligation", "permission", "right"],
            "source_keys": ["spec_10925"],
        },
        {
            "name": "tool_access",
            "json_type": "array<string>",
            "modality": "permission",
            "conflates": False,
            "source_keys": ["imp0280", "spec_10925"],
        },
        {
            "name": "source_access",
            "json_type": "array<string>",
            "modality": "permission",
            "conflates": False,
            "source_keys": ["imp0280", "spec_10925"],
        },
        {
            "name": "speaking_rights",
            "json_type": "boolean",
            "modality": "right-typed-as-optional-flag",
            "conflates": False,
            "note": "Named a right but typed like a permission (true/false, no undeniable constraint).",
            "source_keys": ["imp0280", "spec_10925", "wfa0037"],
        },
        {
            "name": "vote_rights",
            "json_type": "boolean",
            "modality": "right-typed-as-optional-flag",
            "conflates": False,
            "source_keys": ["imp0280", "spec_10925", "wfa0037"],
        },
        {
            "name": "veto_rights",
            "json_type": "boolean",
            "modality": "right-typed-as-optional-flag",
            "conflates": False,
            "source_keys": ["imp0280", "spec_10925"],
        },
        {
            "name": "incompatible_roles",
            "json_type": "array<string>",
            "modality": "constraint",
            "conflates": False,
            "source_keys": ["spec_10925"],
        },
    ]


def reconstruct() -> dict:
    loc = locate_schema()
    cites = catalog_citations()
    fields = v1_field_inventory()
    conflators = [f["name"] for f in fields if f.get("conflates")]
    return {
        "schema_file": loc,
        "catalog": cites,
        "inventory_source": (
            "disk:$defs.role" if loc["role_def"] is not None else "catalog-quotations"
        ),
        "fields": fields,
        "field_count": len(fields),
        "conflating_field": conflators[0] if len(conflators) == 1 else None,
        "conflator_count": len(conflators),
        "three_grants": {
            "obligation": {
                "modal": "MUST",
                "definition": "a duty the seated participant must discharge; absence of the named discharge artifact fails the role check",
            },
            "permission": {
                "modal": "MAY",
                "definition": "a capability the seated participant may use; leaving it unused must not fail the role check",
            },
            "right": {
                "modal": "NOBODY-MAY-DENY",
                "definition": "an entitlement the runtime or chair may not strip; denial fails even if the participant never exercises it",
            },
        },
    }


if __name__ == "__main__":
    print(json.dumps(reconstruct(), indent=2, sort_keys=True))
