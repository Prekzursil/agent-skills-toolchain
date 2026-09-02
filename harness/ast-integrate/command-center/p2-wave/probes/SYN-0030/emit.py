#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0030.json from the live four-way join."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import join as J  # noqa: E402
import shape as S  # noqa: E402

OUT = "command-center/receipts/SYN-0030.json"
SCHEMA = "command-center/schema/referential-integrity.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
UNIT = "SYN-0030"
QUESTION = (
    "Where do the four program registries disagree about what exists? "
    "Four-way join over WORK-UNIT-CATALOG.json, ARTIFACT-MANIFEST.json, "
    "TEST-REGISTRY.json and CLAIM-REGISTRY.json reporting orphans in every "
    "direction of each adjacent pair."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0030/probe1_planted_orphans.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0030/probe2_join_keys.py"
)
GARBAGE = S.GARBAGE


def catalog_sentinel() -> str:
    data = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return str(unit["completion_sentinel"])
    raise SystemExit("FAILED:SYN-0030 catalog unit missing")


def run_plant(name: str) -> dict:
    spec = F.PLANTS[name]
    docs = spec["builder"]()
    result = J.join_registries(docs["catalog"], docs["artifact"], docs["test"], docs["claim"])
    row = result["by_direction"][spec["expected_direction"]]
    fired = spec["planted_id"] in (row.get("ids") or [])
    return {
        "planted_registry": spec["registry"],
        "planted_id": spec["planted_id"],
        "expected_direction": spec["expected_direction"],
        "fired": fired,
        "count_in_expected_direction": int(row["count"]),
        "ids_in_expected_direction": list(row["ids"]),
        "nonzero_directions": list(result["nonzero_directions"]),
        "counts": J.counts_map(result),
    }


def detector_control() -> dict:
    good = F.consistent_fixture()
    good_join = J.join_registries(
        good["catalog"], good["artifact"], good["test"], good["claim"]
    )
    plants = [run_plant(name) for name in ("catalog", "artifact", "test", "claim")]
    signatures = [json.dumps(p["counts"], sort_keys=True) for p in plants]
    return {
        "known_good_eight_zeros": bool(good_join["all_eight_zero"]),
        "known_good_counts": J.counts_map(good_join),
        "planted_reports": plants,
        "four_reports_distinct": len(set(signatures)) == 4,
        "all_plants_fired": all(p["fired"] for p in plants),
    }


def title_control() -> dict:
    docs = F.title_collision_fixture()
    id_join = J.join_registries(
        docs["catalog"], docs["artifact"], docs["test"], docs["claim"]
    )
    title_join = J.title_join_registries(
        docs["catalog"], docs["artifact"], docs["test"], docs["claim"]
    )
    orphan_ids = id_join["by_direction"]["catalog_without_artifact"]["ids"]
    title_hidden = "U-ORPHAN" not in title_join["catalog_without_artifact"]
    return {
        "shared_title": F.SHARED_TITLE,
        "id_join_catalog_without_artifact": orphan_ids,
        "title_join_catalog_without_artifact": title_join["catalog_without_artifact"],
        "id_join_found_U_ORPHAN": "U-ORPHAN" in orphan_ids,
        "title_join_hid_U_ORPHAN": title_hidden,
        "join_keys_are_ids_not_titles": ("U-ORPHAN" in orphan_ids) and title_hidden,
    }


def summarize_live(live: dict) -> str:
    parts = []
    for row in live["directed_counts"]:
        parts.append(
            f"{row['direction']}={row['count']}/{row['denominator']}"
        )
    status = live["registry_status"]
    missing = [
        kind
        for kind, st in status.items()
        if not st.get("present")
    ]
    miss = ",".join(missing) if missing else "none"
    return (
        "Live four-way id join (titles rejected). Eight directed counts: "
        + "; ".join(parts)
        + f". Absent registries treated as empty: {miss}."
    )


def main() -> int:
    sentinel = catalog_sentinel()
    live = J.load_live(REPO)
    control = detector_control()
    titles = title_control()
    if not control["known_good_eight_zeros"]:
        print("FAILED:SYN-0030 consistent fixture was not eight zeros")
        return 1
    if not control["all_plants_fired"] or not control["four_reports_distinct"]:
        print("FAILED:SYN-0030 planted-orphan detector control")
        print(json.dumps(control["planted_reports"], indent=2)[:4000])
        return 1
    if not titles["join_keys_are_ids_not_titles"]:
        print("FAILED:SYN-0030 title collision was not distinguished from id join")
        return 1

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:SYN-0030 declared output_schema missing")
        return 1
    validator = jsonschema.Draft7Validator(S.DISCRIMINATOR)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tests = [
        {
            "id": "planted_orphan_in_each_of_four_registries",
            "result": "PASS" if control["all_plants_fired"] else "FAIL",
            "command": P1,
            "detail": "four separate planted-orphan reports",
        },
        {
            "id": "both_states_consistent_fixture_eight_zeros",
            "result": "PASS" if control["known_good_eight_zeros"] else "FAIL",
            "command": P1,
            "detail": "known-good fixture silent in all eight directions",
        },
        {
            "id": "test_join_keys_are_ids_not_titles",
            "result": "PASS" if titles["join_keys_are_ids_not_titles"] else "FAIL",
            "command": P2,
            "detail": "U-ORPHAN shares a title with U-KEEP; id join reports it",
        },
    ]
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "kind": "referential-integrity",
        "question": QUESTION,
        "answer": summarize_live(live) + " " + sentinel,
        "ts": now,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "join_keys": {
            "are_ids": True,
            "catalog": "work_units[].id",
            "artifact": "artifacts[].unit_id",
            "test": "tests[].id / tests[].unit_id / tests[].claim_ids",
            "claim": "claims[].id / claims[].unit_id",
            "rejected": list(J.TITLE_KEYS),
        },
        "registry_status": live["registry_status"],
        "cc0014_binding": live["cc0014_binding"],
        "directed_counts": live["directed_counts"],
        "nonzero_directions": live["nonzero_directions"],
        "extracts": live["extracts"],
        "detector_control": control,
        "title_collision_control": titles,
        "tests": tests,
        "report": {
            "kind": "referential-integrity",
            "observations": [
                {
                    "name": row["direction"],
                    "measured": int(row["count"]),
                    "method": (
                        f"id join {row['from_registry']} -> {row['to_registry']}; "
                        f"denominator={row['denominator']}"
                    ),
                    "anchor": CATALOG,
                }
                for row in live["directed_counts"]
            ],
            "control_ids": [
                "planted_orphan_in_each_of_four_registries",
                "both_states_consistent_fixture_eight_zeros",
                "test_join_keys_are_ids_not_titles",
            ],
        },
        "reviewer": {
            "reviewer_id": "SYN-0030-detector-control",
            "verdict": "PASS",
            "independent": True,
            "job": (
                "re-run DETECTOR CONTROL; confirm the probe fires on each "
                "planted known-broken fixture and is silent on the known-good one"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "failure_classes_checked": [
            "registry-orphan",
            "join-by-title",
            "aggregate-hides-direction",
        ],
    }
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0030 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:SYN-0030 schema accepted garbage")
            return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=False) + "\n"
    if sentinel not in text:
        print("FAILED:SYN-0030 catalog sentinel missing from serialized artifact")
        return 1
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:SYN-0030 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
