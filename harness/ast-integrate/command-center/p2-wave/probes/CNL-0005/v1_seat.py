"""Locate v1 $defs.seat and compare it to the nine CNL-0005 dials.

The catalog cites a Windows harness-restore path that is not on this Linux
worktree. This module records the search, and separately measures the live
on-disk analog at command-center/schema/council-preset.schema.json
delta.roles (id, vote_weight, seated, ...).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DECLARED_V1 = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "11-COUNCIL-SPECIFICATION.schema.json"
)
NINE = (
    "model",
    "vendor",
    "expertise",
    "role",
    "authority",
    "vote_weight",
    "tools",
    "effort",
    "context",
)
PRESET = "command-center/schema/council-preset.schema.json"

SEARCH_REL = (
    "11-COUNCIL-SPECIFICATION.schema.json",
    "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
    "command-center/schema/11-COUNCIL-SPECIFICATION.schema.json",
    "platform/schema/councilspec.schema.json",
    "platform/schema/councilspec.schema.json",
    "harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
)


def candidate_paths() -> list[Path]:
    out = [Path(DECLARED_V1)]
    for rel in SEARCH_REL:
        out.append(REPO / rel)
    return out


def _properties_of_seat(schema: dict[str, Any]) -> dict[str, Any] | None:
    defs = schema.get("$defs") or schema.get("definitions") or {}
    if not isinstance(defs, dict):
        return None
    seat = defs.get("seat")
    if not isinstance(seat, dict):
        return None
    props = seat.get("properties")
    return props if isinstance(props, dict) else {}


def load_v1_seat() -> dict[str, Any]:
    searched: list[dict[str, Any]] = []
    for path in candidate_paths():
        exists = path.is_file()
        searched.append({"path": str(path).replace("\\", "/"), "exists": exists})
        if not exists:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            searched[-1]["error"] = type(exc).__name__
            continue
        props = _properties_of_seat(doc)
        if props is None:
            searched[-1]["error"] = "no-$defs.seat"
            continue
        return {
            "present": True,
            "path": str(path).replace("\\", "/"),
            "property_names": sorted(props),
            "properties": {
                k: {"type": v.get("type")} if isinstance(v, dict) else {}
                for k, v in props.items()
            },
            "searched": searched,
            "declared_path": DECLARED_V1,
        }
    return {
        "present": False,
        "path": None,
        "property_names": [],
        "properties": {},
        "searched": searched,
        "declared_path": DECLARED_V1,
        "note": (
            "Catalog evidence_requirement cites $defs.seat in the Windows "
            "harness-restore tree. That file is absent on this Linux worktree "
            "(searched declared path plus repo-relative successors). Field-by-"
            "field citation of $defs.seat is therefore NOT-MEASURABLE here. "
            "The nine dials are taken from this unit's question_or_target. "
            "The live on-disk analog is council-preset.schema.json $defs.role "
            "(id, count, votes, obligation) — a role slot, not a participant descriptor."
        ),
    }


def _anchor(lines: list[str], name: str) -> str:
    needle = f'"{name}"'
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{PRESET}:{i}"
    return PRESET


def preset_role_fields() -> dict[str, Any]:
    """Measure the live seat-like object on this tree: $defs.role.

    Sibling units rewrite council-preset.schema.json. This walker reads
    $defs.role.properties if present rather than a frozen JSON pointer.
    """
    path = REPO / PRESET
    if not path.is_file():
        return {
            "path": PRESET,
            "present": False,
            "property_names": [],
            "required": [],
            "anchors": {},
            "def_name": None,
        }
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    lines = text.splitlines()
    defs = doc.get("$defs") or doc.get("definitions") or {}
    role = defs.get("role") if isinstance(defs, dict) else None
    if not isinstance(role, dict):
        return {
            "path": PRESET,
            "present": False,
            "property_names": [],
            "required": [],
            "anchors": {},
            "def_name": None,
            "note": "council-preset.schema.json has no $defs.role on this tree",
        }
    role_props = role.get("properties") or {}
    return {
        "path": PRESET,
        "present": True,
        "def_name": "$defs.role",
        "property_names": sorted(role_props),
        "required": list(role.get("required") or []),
        "anchors": {name: _anchor(lines, name) for name in role_props},
    }


def field_by_field() -> dict[str, Any]:
    v1 = load_v1_seat()
    preset = preset_role_fields()
    v1_names = set(v1["property_names"])
    preset_names = set(preset["property_names"])
    rows = []
    for dial in NINE:
        in_v1 = dial in v1_names if v1["present"] else None
        in_preset = dial in preset_names
        rows.append(
            {
                "dial": dial,
                "v1_$defs.seat": (
                    "PRESENT"
                    if in_v1
                    else ("ABSENT" if v1["present"] else "NOT-MEASURABLE-FILE-ABSENT")
                ),
                "on_disk_preset_roles": in_preset,
                "preset_anchor": preset["anchors"].get(dial) if in_preset else None,
            }
        )
    carried = [r["dial"] for r in rows if r["on_disk_preset_roles"]]
    lacking = [r["dial"] for r in rows if not r["on_disk_preset_roles"]]
    extra_preset = sorted(preset_names - set(NINE))
    return {
        "v1": v1,
        "preset_roles": preset,
        "rows": rows,
        "nine_dials": list(NINE),
        "carried_on_disk_preset_roles": carried,
        "lacking_on_disk_preset_roles": lacking,
        "preset_fields_not_in_nine": extra_preset,
    }
