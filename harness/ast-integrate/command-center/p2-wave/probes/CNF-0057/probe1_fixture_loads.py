#!/usr/bin/env python3
"""Probe 1: every user fixture loaded; honoured-key lists recorded including unknown-key."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import reader as R  # noqa: E402

OUT = "command-center/confirmation/CNF-0057-config-key-diff.json"
SCHEMA = "command-center/schema/regression-delta.schema.json"
UNIT = "CNF-0057"


def main() -> int:
    after = R.load_schema("after")
    fixtures = R.load_fixtures()
    if len(fixtures) < 5:
        print(f"FAILED:{UNIT}-probe1 expected >=5 fixtures got {len(fixtures)}")
        return 1
    loads = R.load_all(after, fixtures, permissive=False)
    ids = [row["fixture_id"] for row in loads]
    missing = [fx["id"] for fx in fixtures if fx["id"] not in ids]
    if missing:
        print(f"FAILED:{UNIT}-probe1 fixtures not loaded: {missing}")
        return 1

    unknown = next((row for row in loads if row["control"] == "unknown-key"), None)
    if unknown is None or not unknown["unknown"]:
        print(f"FAILED:{UNIT}-probe1 unknown-key control not reported")
        return 1
    if R.UNKNOWN_CONTROL_KEY not in {u["key"] for u in unknown["unknown"]}:
        print(f"FAILED:{UNIT}-probe1 unknown control key missing from report")
        return 1
    if R.UNKNOWN_CONTROL_KEY in unknown["honoured_keys"]:
        print(f"FAILED:{UNIT}-probe1 reader is permissive; unknown key honoured")
        return 1

    artifact_path = REPO / OUT
    if not artifact_path.is_file():
        print(f"FAILED:{UNIT}-probe1 artifact absent {OUT}")
        return 1
    doc = json.loads(artifact_path.read_text(encoding="utf-8"))
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    recorded = {
        row["fixture_id"]: row.get("honoured_keys")
        for row in doc.get("fixture_loads") or []
        if isinstance(row, dict)
    }
    for row in loads:
        got = recorded.get(row["fixture_id"])
        if got != row["honoured_keys"]:
            print(
                f"FAILED:{UNIT}-probe1 honoured-key mismatch "
                f"{row['fixture_id']}: live={row['honoured_keys']} artifact={got}"
            )
            return 1
        print(
            f"fixture {row['fixture_id']} honoured={row['honoured_keys']} "
            f"unknown={[u['key'] for u in row['unknown']]} "
            f"inert={[i['key'] for i in row['inert']]} "
            f"verbatim={row['verbatim_honour']}"
        )
    print(
        f"loaded={len(loads)} unknown_control={ [u['key'] for u in unknown['unknown']] }"
    )
    print(f"SUCCESS:{UNIT}-probe1 every fixture loaded with honoured-key list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
