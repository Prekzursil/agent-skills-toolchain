#!/usr/bin/env python3
"""Probe 1: frozen definition hashed before count; same rule; both-states fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import DEFINITION_PATH, fixture_both_states, load_definition, sha256_file  # noqa: E402

REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0035.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0035-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    definition = load_definition()
    live = sha256_file(DEFINITION_PATH)
    if definition["_sha256"] != live:
        return fail("in-memory definition hash drifted from disk")
    recorded = doc.get("definition") or {}
    if recorded.get("sha256") != live:
        return fail("artifact definition.sha256 does not match DEFINITION.json")
    if recorded.get("frozen_before_count") is not True:
        return fail("definition not marked frozen_before_count")
    if recorded.get("same_rule_all_vendors") is not True:
        return fail("same_rule_all_vendors is not true")
    if doc.get("definition_locked_hash_before_enumerate") is not True:
        return fail("hash was not locked before enumeration")

    fx = fixture_both_states(definition)
    if not fx["planted_break_counted"]:
        return fail("planted config-surface break was not counted")
    if not fx["noise_excluded"]:
        return fail("UI 'breaking' noise was counted")
    if not fx["optional_add_excluded"]:
        return fail("optional additive settings.json key was counted")

    rows = doc.get("per_vendor_counts") or []
    if len(rows) < 5:
        return fail("fewer than 5 vendors measured")
    vendors = [r.get("vendor_id") for r in rows]
    if len(set(vendors)) != len(vendors):
        return fail("duplicate vendor rows")
    for row in rows:
        for item in row.get("items") or []:
            if not item.get("published_at") or not item.get("version"):
                return fail(f"counted item missing version/date: {item}")

    payload = {
        "probe": "probe1-definition-before-count",
        "unit_id": "RES-0035",
        "definition_sha256": live,
        "frozen_before_count": True,
        "same_rule_all_vendors": True,
        "fixtures": {
            "planted_break_counted": fx["planted_break_counted"],
            "noise_excluded": fx["noise_excluded"],
            "optional_add_excluded": fx["optional_add_excluded"],
        },
        "vendors": len(rows),
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print("SUCCESS:RES-0035-probe1 definition frozen before count; both-states fixtures fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
