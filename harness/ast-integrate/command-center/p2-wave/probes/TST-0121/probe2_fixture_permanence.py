#!/usr/bin/env python3
"""Probe 2: every discovered disagreement is a permanent fixture.

Independent of emit_receipt: re-run the recorded-seed campaign, re-parse
each on-disk fixture, and require a fixture file per finding. A synthetic
unsaved finding must be reported missing (negative control). Same seed
must reproduce the identical id set.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import (  # noqa: E402
    DEFAULT_COUNT,
    DEFAULT_SEED,
    finding_id,
    load_fixture,
    load_index,
    missing_fixtures,
    run_campaign,
)
from parsers import classify, is_disagreement  # noqa: E402

ART = Path(__file__).resolve().parents[4] / "command-center" / "receipts" / "TST-0121.json"


def main() -> int:
    first = run_campaign(DEFAULT_SEED, DEFAULT_COUNT)
    second = run_campaign(DEFAULT_SEED, DEFAULT_COUNT)
    if first["finding_ids"] != second["finding_ids"]:
        print("FAILED:TST-0121-probe2 same seed produced different finding ids")
        print(first["finding_ids"])
        print(second["finding_ids"])
        return 1
    if first["finding_count"] < 2:
        print(f"FAILED:TST-0121-probe2 expected >=2 findings got {first['finding_count']}")
        return 1
    if first["planted_found_count"] < 2:
        print(
            "FAILED:TST-0121-probe2 planted divergences missing from campaign "
            f"{first['planted_ids']}"
        )
        return 1

    missing = missing_fixtures(first["findings"], HERE)
    if missing:
        print(f"FAILED:TST-0121-probe2 campaign findings without fixtures {missing}")
        return 1

    index = load_index(HERE)
    if set(index.get("finding_ids") or []) != set(first["finding_ids"]):
        print("FAILED:TST-0121-probe2 INDEX finding_ids != live campaign")
        print({"index": index.get("finding_ids"), "live": first["finding_ids"]})
        return 1
    if int(index.get("seed")) != DEFAULT_SEED:
        print(f"FAILED:TST-0121-probe2 INDEX seed {index.get('seed')} != {DEFAULT_SEED}")
        return 1

    dest = HERE / "fixtures" / "disagreements"
    files = sorted(dest.glob("D-*.json"))
    if not files:
        print("FAILED:TST-0121-probe2 no fixture files on disk")
        return 1
    unique_ids = set(first["finding_ids"])
    if len(unique_ids) != first["finding_count"]:
        print("FAILED:TST-0121-probe2 finding_ids contain duplicates")
        return 1
    if len(files) != first["finding_count"]:
        print(
            f"FAILED:TST-0121-probe2 fixture files {len(files)} != "
            f"findings {first['finding_count']}"
        )
        return 1

    for path in files:
        doc = load_fixture(path)
        live = classify(doc["input"])
        if not is_disagreement(live):
            print(f"FAILED:TST-0121-probe2 fixture is not a live disagreement {path.name}")
            return 1
        if live["kind"] != doc.get("kind"):
            print(f"FAILED:TST-0121-probe2 kind drift {path.name} {live['kind']} {doc.get('kind')}")
            return 1
        if live["strict"] != doc.get("strict"):
            print(f"FAILED:TST-0121-probe2 strict interpretation drift {path.name}")
            return 1
        if live["lenient"] != doc.get("lenient"):
            print(f"FAILED:TST-0121-probe2 lenient interpretation drift {path.name}")
            return 1
        expected_id = finding_id(live["kind"], doc["input"])
        if expected_id != doc.get("id") or expected_id != path.stem:
            print(f"FAILED:TST-0121-probe2 id mismatch {path.name} {expected_id}")
            return 1
        side = doc.get("interpretations_side_by_side") or {}
        if side.get("strict") != doc.get("strict") or side.get("lenient") != doc.get("lenient"):
            print(f"FAILED:TST-0121-probe2 side-by-side missing {path.name}")
            return 1

    unsaved = {
        "id": finding_id("accept-reject", "{ // unsaved\n}"),
        "kind": "accept-reject",
        "input": "{ // unsaved\n}",
    }
    gap = missing_fixtures([unsaved], HERE)
    if unsaved["id"] not in gap:
        print("FAILED:TST-0121-probe2 unsaved finding was not reported missing")
        return 1

    if ART.is_file():
        receipt = json.loads(ART.read_text(encoding="utf-8"))
        rec_ids = [r["id"] for r in receipt.get("findings") or []]
        if set(rec_ids) != set(first["finding_ids"]):
            print("FAILED:TST-0121-probe2 receipt findings != live campaign")
            return 1
        if "SUCCESS:TST-0121" not in json.dumps(receipt):
            print("FAILED:TST-0121-probe2 receipt sentinel absent")
            return 1

    print(
        json.dumps(
            {
                "seed": first["seed"],
                "findings": first["finding_count"],
                "fixtures": len(files),
                "reproduction_ids_equal": True,
                "unsaved_detected": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0121-probe2 every disagreement is a fixture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
