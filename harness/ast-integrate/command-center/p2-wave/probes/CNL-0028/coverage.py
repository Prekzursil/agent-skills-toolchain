"""Mechanical role-coverage of the 58 catalog-cited protocol records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROTOCOLS = HERE / "protocols.json"
TEMPLATES = HERE / "templates.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def covering_names(tmpl: dict[str, Any]) -> set[str]:
    names = set(tmpl["templates"])
    names.update(tmpl.get("aliases") or {})
    names.update(tmpl.get("explicit_gaps") or [])
    return names


def named_roles(census: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for rec in census["protocols"]:
        out.update(rec["roles"])
    return out


def coverage_report(
    census: dict[str, Any] | None = None,
    tmpl: dict[str, Any] | None = None,
) -> dict[str, Any]:
    census = census if census is not None else load_json(PROTOCOLS)
    tmpl = tmpl if tmpl is not None else load_json(TEMPLATES)
    records = list(census["protocols"])
    ids = [r["id"] for r in records]
    roles = named_roles(census)
    covering = covering_names(tmpl)
    unmapped = sorted(roles - covering)
    unused = sorted(set(tmpl["templates"]) - roles)
    family_counts: dict[str, int] = {}
    for rec in records:
        family_counts[rec["family"]] = family_counts.get(rec["family"], 0) + 1
    ablation: dict[str, list[str]] = {}
    for drop in tmpl["templates"]:
        reduced = set(tmpl["templates"]) - {drop}
        reduced.update(tmpl.get("aliases") or {})
        reduced.update(tmpl.get("explicit_gaps") or [])
        ablation[drop] = sorted(roles - reduced)
    return {
        "protocol_n": len(records),
        "unique_ids": len(set(ids)),
        "duplicate_ids": sorted({i for i in ids if ids.count(i) > 1}),
        "named_role_n": len(roles),
        "named_roles": sorted(roles),
        "template_n": len(tmpl["templates"]),
        "template_ids": sorted(tmpl["templates"]),
        "explicit_gaps": list(tmpl.get("explicit_gaps") or []),
        "unmapped": unmapped,
        "unused_templates": unused,
        "family_counts": family_counts,
        "ablation_unmapped": ablation,
        "minimum_holds": all(ablation[t] for t in tmpl["templates"]),
        "covered": unmapped == [],
        "library_on_tree": bool(census.get("library_file_on_this_tree")),
    }


def mutant_unmapped_role(census: dict[str, Any]) -> dict[str, Any]:
    import copy

    planted = copy.deepcopy(census)
    planted["protocols"][0]["roles"] = list(planted["protocols"][0]["roles"]) + ["wizard"]
    return planted
