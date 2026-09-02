#!/usr/bin/env python3
"""Named probe 1: resolved-view dump for three units + live 0/103 census.

Recomputes the dump from tools/command-center/catalog.py against the live
defaults block. Compares it to command-center/receipts/IMP-0436.json so a
stale or hand-typed dump cannot pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import catalog as cat  # noqa: E402
from scenario import DISTINCT, THREE, live_override_census, three_cases  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0436.json"
SENTINEL = "SENTINEL:IMP-0436:CATALOG-OVERRIDES-ENFORCED"
NINE = cat.OVERRIDEABLE_FIELDS


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0436-probe1 {msg}")
    return 1


def _by_field(view: dict) -> dict:
    return {row["field"]: row for row in view["fields"]}


def main() -> int:
    catalog = cat.load()
    defaults = cat.catalog_defaults(catalog)
    if defaults is None:
        return fail("live defaults block missing")

    census = live_override_census(catalog)
    if census["items"] != 103:
        return fail(f"items={census['items']} want=103")
    if census["items_overriding_any_of_nine"] != 0:
        return fail(f"overrides={census['overriding_ids']}")
    if census["defaults_block_problems"]:
        return fail(f"defaults_block_problems={census['defaults_block_problems']}")

    views = three_cases(catalog)
    cases = [v["case"] for v in views]
    if cases != ["all-defaults", "override-three", "override-nine"]:
        return fail(f"cases={cases}")

    all_def, three, nine = views
    if all_def["override_count"] != 0 or all_def["default_count"] != 9:
        return fail(f"all-defaults counts {all_def['override_count']}/{all_def['default_count']}")
    if three["override_count"] != 3 or three["default_count"] != 6:
        return fail(f"override-three counts {three['override_count']}/{three['default_count']}")
    if nine["override_count"] != 9 or nine["default_count"] != 0:
        return fail(f"override-nine counts {nine['override_count']}/{nine['default_count']}")
    if any(v["unset_count"] != 0 for v in views):
        return fail("unexpected unset")

    all_map = _by_field(all_def)
    for field in NINE:
        row = all_map[field]
        if row["provenance"] != cat.PROVENANCE_DEFAULT:
            return fail(f"all-defaults {field} provenance={row['provenance']}")
        if row["value"] != defaults[field]:
            return fail(f"all-defaults {field} value mismatch")

    three_map = _by_field(three)
    for field in NINE:
        row = three_map[field]
        if field in THREE:
            if row["provenance"] != cat.PROVENANCE_OVERRIDE:
                return fail(f"override-three {field} not override")
            if row["value"] != DISTINCT[field]:
                return fail(f"override-three {field} value mismatch")
        else:
            if row["provenance"] != cat.PROVENANCE_DEFAULT:
                return fail(f"override-three {field} not default")
            if row["value"] != defaults[field]:
                return fail(f"override-three {field} leaked override")

    nine_map = _by_field(nine)
    for field in NINE:
        row = nine_map[field]
        if row["provenance"] != cat.PROVENANCE_OVERRIDE:
            return fail(f"override-nine {field} provenance={row['provenance']}")
        if row["value"] != DISTINCT[field]:
            return fail(f"override-nine {field} value mismatch")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("enforced_by") != cat.OVERRIDE_SEMANTICS["enforced_by"]:
        return fail("enforced_by mismatch")
    if list(doc.get("overridable_fields") or []) != list(NINE):
        return fail("overridable_fields mismatch")
    stored = doc.get("resolved_views") or []
    if len(stored) != 3:
        return fail(f"stored views={len(stored)}")
    for live_view, stored_view in zip(views, stored):
        if stored_view.get("case") != live_view["case"]:
            return fail(f"stored case {stored_view.get('case')}")
        if stored_view.get("fields") != live_view["fields"]:
            return fail(f"stored dump drifted for {live_view['case']}")
        if stored_view.get("override_count") != live_view["override_count"]:
            return fail(f"stored override_count drifted for {live_view['case']}")

    live_cat = doc.get("live_catalog") or {}
    if live_cat.get("items") != 103:
        return fail("receipt live_catalog.items")
    if live_cat.get("items_overriding_any_of_nine") != 0:
        return fail("receipt live_catalog overrides")

    print(
        json.dumps(
            {
                "all_defaults_id": all_def["id"],
                "override_three_id": three["id"],
                "override_nine_id": nine["id"],
                "counts": [
                    {
                        "case": v["case"],
                        "override": v["override_count"],
                        "default": v["default_count"],
                    }
                    for v in views
                ],
                "live_items": census["items"],
                "live_overrides": census["items_overriding_any_of_nine"],
                "enforced_by": cat.OVERRIDE_SEMANTICS["enforced_by"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0436-probe1 three-unit dump live-0/103")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
