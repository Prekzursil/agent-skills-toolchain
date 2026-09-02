#!/usr/bin/env python3
"""Probe 1: format check + default/impact check.

Catalog tests:
  * exactly one foundation-level question per packet entry (compound fails)
  * every entry has a non-empty default and an impact statement
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from packet import (  # noqa: E402
    ESTATE_PACKET_REL,
    UNIT_PACKET_REL,
    build_packet,
    estate_packet_intact,
    is_compound_question,
    load_unresolved,
    parse_packet,
    validate_entry,
)

ART = REPO / "command-center/receipts/CNF-0161.json"
ESTATE_PACKET = REPO / ESTATE_PACKET_REL
UNIT_PACKET = REPO / UNIT_PACKET_REL
FIXTURE = HERE / "fixtures" / "unresolved.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0161-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = ART.read_text(encoding="utf-8")
    if doc.get("unit_id") != "CNF-0161":
        return fail(f"unit_id={doc.get('unit_id')}")
    if "SUCCESS:CNF-0161" not in text:
        return fail("sentinel-absent")

    loaded = load_unresolved(FIXTURE)
    if loaded["status"] != "PRESENT" or len(loaded["claims"]) != 2:
        return fail(f"fixture load {loaded}")
    entries, skipped = build_packet(loaded["claims"], decisions=[])
    if skipped:
        return fail(f"fixture skipped unexpectedly {skipped}")
    if len(entries) != 2:
        return fail(f"open_entries={len(entries)} want=2")
    for entry in entries:
        errors = validate_entry(entry)
        if errors:
            return fail(f"valid fixture entry rejected {entry['claim_id']} {errors}")
        if is_compound_question(entry["question"]):
            return fail(f"fixture question marked compound {entry['claim_id']}")

    compound = deepcopy(entries[0])
    compound["question"] = (
        "Should the Anthropic verdict be treated as authoritative, and should "
        "the Codex verdict be discarded?"
    )
    compound_errors = validate_entry(compound)
    if "compound-question" not in compound_errors:
        return fail(f"compound question accepted {compound_errors}")

    two_marks = deepcopy(entries[0])
    two_marks["question"] = "Should we close the claim? Should we also re-run vendors?"
    if "compound-question" not in validate_entry(two_marks):
        return fail("two-question string accepted")

    missing_default = deepcopy(entries[0])
    missing_default["default_if_unanswered"] = "   "
    default_errors = validate_entry(missing_default)
    if "default_if_unanswered-empty" not in default_errors:
        return fail(f"empty default accepted {default_errors}")

    missing_impact = deepcopy(entries[0])
    missing_impact["impact"] = ""
    impact_errors = validate_entry(missing_impact)
    if "impact-empty" not in impact_errors:
        return fail(f"empty impact accepted {impact_errors}")

    estate_text = ESTATE_PACKET.read_text(encoding="utf-8") if ESTATE_PACKET.is_file() else ""
    if not estate_packet_intact(estate_text):
        return fail("estate OWNER-QUESTION-PACKET.md missing or overwritten")

    if not UNIT_PACKET.is_file():
        return fail("unit-scoped packet missing")
    live_entries = parse_packet(UNIT_PACKET.read_text(encoding="utf-8"))
    for entry in live_entries:
        errors = validate_entry(entry)
        if errors:
            return fail(f"unit packet entry {entry.get('claim_id')} {errors}")

    print(
        json.dumps(
            {
                "probe": "probe1-format-default",
                "unit_id": "CNF-0161",
                "fixture_entries": len(entries),
                "compound_rejected": True,
                "two_question_rejected": True,
                "empty_default_rejected": True,
                "empty_impact_rejected": True,
                "live_open_entries": len(live_entries),
                "pass": True,
            }
        )
    )
    print("SUCCESS:CNF-0161-probe1 format and default checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
