#!/usr/bin/env python3
"""Probe 1: v1→v2 mapping table, named refusal, migrated-vs-v1 decision parity."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.migrate import (  # noqa: E402
    FIELD_MAPPING,
    MIGRATION_ID,
    SHAPE_CHANGE_PROPERTY,
    SOURCE_VERSION,
    TARGET_VERSION,
    V1_PROPERTIES,
    V1_REQUIRED,
    MigrationRequired,
    canonical,
    demote_v2_to_v1,
    execute_v1,
    execute_v2,
    migrate_v1_to_v2,
    refusal_message,
    refuse_unmigrated,
)

FIX = HERE / "fixtures"
ART = REPO / "command-center" / "receipts" / "IMP-0263.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0263-probe1 {msg}")
    return 1


def main() -> int:
    v1 = json.loads((FIX / "v1_recorded.json").read_text(encoding="utf-8"))
    ballots = json.loads((FIX / "ballots.json").read_text(encoding="utf-8"))
    recorded = json.loads((FIX / "recorded_v1_decision.json").read_text(encoding="utf-8"))

    mapped_v1 = {row["v1"] for row in FIELD_MAPPING}
    if mapped_v1 != set(V1_PROPERTIES):
        return fail(f"mapping table does not cover v1 properties: {sorted(mapped_v1)} vs {list(V1_PROPERTIES)}")
    if len(V1_REQUIRED) != 12 or len(V1_PROPERTIES) != 13:
        return fail(f"v1 envelope is 13 properties / 12 required, got {len(V1_PROPERTIES)}/{len(V1_REQUIRED)}")
    shape_rows = [r for r in FIELD_MAPPING if r["v1"] == SHAPE_CHANGE_PROPERTY]
    if not shape_rows or shape_rows[0]["transform"] != "names_to_seats":
        return fail("participants is not the documented shape-change row")

    try:
        refuse_unmigrated(v1)
        return fail("un-migrated v1 was not refused")
    except MigrationRequired as exc:
        text = str(exc)
        if f"source_version={SOURCE_VERSION}" not in text:
            return fail(f"refusal missing source version: {text}")
        if f"target_version={TARGET_VERSION}" not in text:
            return fail(f"refusal missing target version: {text}")
        if MIGRATION_ID not in text:
            return fail(f"refusal missing migration id: {text}")
        print(text)

    cli = subprocess.run(
        [sys.executable, "-B", str(REPO / "tools/council/migrate.py"), "refuse", str(FIX / "v1_recorded.json")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    cli_text = (cli.stdout or "") + (cli.stderr or "")
    expected = refusal_message(SOURCE_VERSION, TARGET_VERSION, MIGRATION_ID)
    if cli.returncode == 0:
        return fail("CLI refuse exited 0 on v1 spec")
    if expected not in cli_text:
        return fail(f"CLI refuse did not print versions: {cli_text!r}")
    print(f"cli_refuse_rc={cli.returncode} printed_source_and_target=True")

    v1_decision = execute_v1(v1, ballots)
    for key in ("decision", "status", "tally", "method"):
        if v1_decision.get(key) != recorded.get(key):
            return fail(f"v1 runtime drifted from recorded fixture on {key}: {v1_decision} vs {recorded}")

    v2 = migrate_v1_to_v2(v1)
    if v2["schema_version"] != TARGET_VERSION:
        return fail("migrated spec is not v2")
    seats = v2["participants"]
    if seats != [{"id": "alice", "role": "member"}, {"id": "bob", "role": "member"}, {"id": "carol", "role": "member"}]:
        return fail(f"participants did not change shape to seats: {seats}")
    if v2["voting"] != {"method": "majority"}:
        return fail(f"voting did not wrap: {v2['voting']}")
    if v2["charter"]["id"] != v1["id"]:
        return fail("charter wrap dropped id")
    if v2["meta"]["migration_id"] != MIGRATION_ID:
        return fail("migration id not recorded on v2 meta")

    v2_decision = execute_v2(v2, ballots, version_check=True)
    if v2_decision.get("decision") != v1_decision.get("decision"):
        return fail(f"migrated v2 decision {v2_decision} != v1 {v1_decision}")
    if v2_decision.get("tally") != v1_decision.get("tally"):
        return fail("tally mismatch after migration")
    if v2_decision.get("status") != "decided" or v2_decision.get("decision") != "freeze":
        return fail(f"unexpected v2 decision {v2_decision}")

    round_trip = demote_v2_to_v1(v2)
    if canonical(round_trip) != canonical(v1):
        return fail(f"round-trip v1→v2→v1 not canonical-equal: {round_trip} vs {v1}")

    try:
        execute_v2(v1, ballots, version_check=True)
        return fail("v2 runtime executed un-migrated v1 (silent-run)")
    except MigrationRequired:
        pass

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != "IMP-0263":
            return fail("receipt unit_id")
        blob = json.dumps(doc)
        if "SUCCESS:IMP-0263" not in blob:
            return fail("receipt sentinel absent")

    print(
        json.dumps(
            {
                "mapping_rows": len(FIELD_MAPPING),
                "shape_change_property": SHAPE_CHANGE_PROPERTY,
                "refusal_names_migration": True,
                "source_version": SOURCE_VERSION,
                "target_version": TARGET_VERSION,
                "v1_decision": v1_decision["decision"],
                "v2_decision": v2_decision["decision"],
                "parity": True,
                "round_trip": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0263-probe1 mapping-table refusal parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
