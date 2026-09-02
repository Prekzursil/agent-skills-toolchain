#!/usr/bin/env python3
"""Probe 1: schema rejects one-signal and no-settling-experiment records."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ingest as I  # noqa: E402
from jsonschema import Draft7Validator, ValidationError

REPO = I.REPO
ART = REPO / "command-center/confirmation/CNF-0026-impossibility-records.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"


def _valid_skeleton() -> dict:
    return {
        "failure_id": "IMP-PROBE1-SKELETON",
        "title": "Skeleton used only to mutate schema-negative cases",
        "source_units": ["CNF-0016"],
        "reproduction_status": "PREREQUISITE-MISSING",
        "missing_prerequisite": "named for the negative fixture only",
        "substrates_attempted": ["linux-worktree"],
        "attempts": [
            {
                "substrate": "linux-worktree",
                "action": "schema negative fixture",
                "result": "not admitted",
            }
        ],
        "signals": [
            {
                "id": "S1",
                "channel": "path-stat",
                "method": "Path.is_file on a missing input",
                "observation": "target is_file=False",
            },
            {
                "id": "S2",
                "channel": "catalog-lookup",
                "method": "parse leftover remaining_ids",
                "observation": "CNF-0016 in leftover=True",
            },
        ],
        "settling_experiment": {
            "name": "restore-missing-input",
            "command": "test -s command-center/BASELINE-SNAPSHOT.json",
            "expected_observation": "snapshot exists and names failing steps",
            "discriminating_outcome": "file present retires the record",
        },
        "blocks_phase15_gate": False,
    }


def expect_schema_fail(record: dict, label: str) -> None:
    try:
        Draft7Validator(I.record_schema()).validate(record)
    except ValidationError:
        print(f"{label}=rejected")
        return
    print(f"FAILED:CNF-0026-probe1 {label} was accepted by schema")
    raise SystemExit(1)


def main() -> int:
    good = _valid_skeleton()
    Draft7Validator(I.record_schema()).validate(good)
    I.accept_record(good, REPO)
    print("positive_skeleton=accepted")

    one = copy.deepcopy(good)
    one["signals"] = [one["signals"][0]]
    expect_schema_fail(one, "single-signal")

    nose = copy.deepcopy(good)
    del nose["settling_experiment"]
    expect_schema_fail(nose, "no-settling-experiment")

    empty_se = copy.deepcopy(good)
    empty_se["settling_experiment"] = {
        "name": "",
        "command": "",
        "expected_observation": "too-short",
        "discriminating_outcome": "too-short",
    }
    expect_schema_fail(empty_se, "empty-settling-experiment")

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0026-probe1 live artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    I.accept_artifact(doc, REPO)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0026-probe1 self-declared", doc.get("state"))
        return 1
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u["id"] == "CNF-0026")
    text = ART.read_text(encoding="utf-8")
    if unit["completion_sentinel"] not in text:
        print("FAILED:CNF-0026-probe1 catalog sentinel absent")
        return 1
    for record in doc["records"]:
        ch = {s["channel"] for s in record["signals"]}
        if len(record["signals"]) < 2 or len(ch) < 2:
            print(
                "FAILED:CNF-0026-probe1 live record lacks two channels",
                record["failure_id"],
            )
            return 1
        if not record.get("settling_experiment", {}).get("name"):
            print("FAILED:CNF-0026-probe1 live record lacks settling experiment")
            return 1
    print(
        f"live_records={len(doc['records'])} schema_ok=True "
        f"two_channels_each=True settling_each=True"
    )
    print(
        "SUCCESS:CNF-0026-probe1 schema rejects single-signal and missing "
        "settling experiment"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
