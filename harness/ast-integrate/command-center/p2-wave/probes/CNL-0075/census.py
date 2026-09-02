#!/usr/bin/env python3
"""Measure which lineage hop is missing on THIS worktree.

Signal 1 (catalog): first forward hop with no authoring unit other than CNL-0075.
Signal 2 (disk): implementation modules + parent-field grep, excluding this
probe dir, the unit artifact, and the catalog (the catalog names the chain).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

COUNCIL_UID = re.compile(r"^(CNL|IMP)-\d+$")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lineage as L  # noqa: E402

CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
SELF_UNIT = "CNL-0075"
EXCLUDE_PREFIXES = (
    "command-center/p2-wave/probes/CNL-0075/",
    "command-center/design/council/CNL-0075-",
    "command-center/WORK-UNIT-CATALOG.json",
)
SEARCH_GLOBS = (
    "**/*.py",
    "**/*.json",
    "**/*.md",
    "**/*.schema.json",
)
MODULE_BY_KIND = {
    "idea": "tools/council/protocol/brainstorm.py",
    "option_card": "tools/council/artifacts/option_cards.py",
    "claim": "tools/council/artifacts/claims.py",
    "argument": "tools/council/artifacts/argument_graph.py",
    "vote": "tools/council/protocol/vote.py",
    "decision": "tools/council/outcomes/lineage_export.py",
    "action_plan": "tools/council/outcomes/action_plan.py",
}
SCHEMA_PATHS = (
    "command-center/schema/councilspec.v2.schema.json",
    "command-center/schema/council-design-note.schema.json",
    "platform/schema/councilspec.schema.json",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/design/council/CNL-0056-idea-ledger-schema-and-per-participant-provenance.md",
    "tools/council/artifacts/option_cards.py",
    "tools/council/artifacts/argument_graph.py",
    "tools/council/outcomes/action_plan.py",
)


def _rel(path: Path) -> str:
    return path.as_posix() if path.is_absolute() else path.as_posix()


def catalog_authors(needles: tuple[str, ...]) -> list[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    hits = []
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if uid == SELF_UNIT or not COUNCIL_UID.match(uid):
            continue
        blob = " ".join(
            [
                str(unit.get("title") or ""),
                str(unit.get("question_or_target") or ""),
            ]
        ).lower()
        if all(n.lower() in blob for n in needles):
            hits.append(uid)
    return hits


def field_hits(field: str) -> list[str]:
    pat = re.compile(re.escape(field))
    found: list[str] = []
    for glob in SEARCH_GLOBS:
        for path in REPO.glob(glob):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(REPO).as_posix()
            except ValueError:
                continue
            if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
                continue
            if "node_modules" in rel.split("/") or rel.startswith("."):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if pat.search(text):
                found.append(rel)
    return sorted(set(found))


def measure() -> dict[str, Any]:
    hops = []
    first_unauthored = None
    first_unbuilt = None
    for hop in L.iter_hops():
        authors = catalog_authors(tuple(hop["catalog_needles"]))
        field = hop["parent_field"]
        disk = field_hits(field)
        child_mod = MODULE_BY_KIND.get(hop["to_kind"])
        parent_mod = MODULE_BY_KIND.get(hop["from_kind"])
        child_exists = bool(child_mod) and (REPO / child_mod).is_file()
        parent_exists = bool(parent_mod) and (REPO / parent_mod).is_file()
        row = {
            "from_kind": hop["from_kind"],
            "to_kind": hop["to_kind"],
            "parent_field": field,
            "catalog_authors_excluding_self": authors,
            "catalog_authored": bool(authors),
            "parent_field_hits_outside_self": disk,
            "parent_field_present_on_disk": bool(disk),
            "child_module": child_mod,
            "child_module_exists": child_exists,
            "parent_module": parent_mod,
            "parent_module_exists": parent_exists,
        }
        hops.append(row)
        if first_unauthored is None and not authors:
            first_unauthored = f"{hop['from_kind']}->{hop['to_kind']}"
        if first_unbuilt is None and not child_exists:
            first_unbuilt = f"{hop['from_kind']}->{hop['to_kind']}"

    schemas = {p: (REPO / p).is_file() for p in SCHEMA_PATHS}
    missing_link = first_unauthored or first_unbuilt or "NONE"
    return {
        "missing_link": missing_link,
        "missing_link_rule": (
            "First forward hop with zero CNL-* or IMP-* catalog authors other "
            "than CNL-0075 (needles = both hop names in title or question). "
            "Loose scans that include CC/AUD/ARC coincidences (e.g. CC-0019 "
            "option-cards-plus-claims normalization) are discarded. Disk "
            "modules and parent-field greps are the second signal, not the "
            "ranking key."
        ),
        "hops": hops,
        "on_disk": schemas,
        "cnl_0056_artifact": schemas[
            "command-center/design/council/CNL-0056-idea-ledger-schema-and-per-participant-provenance.md"
        ],
        "councilspec_v2_schema": schemas[
            "command-center/schema/councilspec.v2.schema.json"
        ],
    }


def main() -> int:
    doc = measure()
    print(json.dumps(doc, indent=2, sort_keys=True))
    print(f"missing_link={doc['missing_link']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
