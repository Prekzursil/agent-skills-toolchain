#!/usr/bin/env python3
"""Probe 1: two mechanically different extractors; disagreement is not max()."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extractors as E  # noqa: E402

ART = E.ART


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0188-probe1 {msg}")
    return 1


def main() -> int:
    live = E.live_census()
    if len(live) < 6:
        return fail(f"census rows {len(live)} want>=6")

    wu = next(r for r in live if r["id"] == "work_units")
    if wu["json_count"] != wu["md_count"]:
        return fail(
            f"work_units json {wu['json_count']} != text {wu['md_count']} "
            "(identity extractors must agree)"
        )
    if wu["json_count"] < 100:
        return fail(f"work_units {wu['json_count']} unexpectedly small")
    if wu["resolved_count"] < 2048 and wu["holds"] is True:
        return fail("work_units floor claimed HOLD without meeting 2048")
    if wu["resolved_count"] >= 2048 and wu["holds"] is not True:
        return fail("work_units count meets 2048 but holds is not True")
    rec = wu["reconciliation"]
    if rec.get("used_max_algorithm") or rec.get("method") == "max":
        return fail("work_units used max() as the resolver")

    arch = next(r for r in live if r["id"] == "architectures")
    if arch["json_count"] != arch["md_count"]:
        return fail(f"architectures json {arch['json_count']} != dirs {arch['md_count']}")
    if arch["resolved_count"] != 2:
        return fail(f"architectures resolved {arch['resolved_count']} want 2 (A1,A2)")
    if arch["holds"] is True:
        return fail("architectures floor 9 cannot hold at count 2")

    for floor_id in ("workflow_candidates", "blueprints", "council_protocols", "presets", "options"):
        row = next(r for r in live if r["id"] == floor_id)
        if row["json_count"] != 0 or row["md_count"] != 0:
            return fail(f"{floor_id} live count not 0; catalogs are absent on this tree")
        if row["reconciliation"].get("method") != "agreement":
            return fail(f"{floor_id} extractors disagreed on absence")
        if floor_id != "options" and row["holds"] is True:
            return fail(f"{floor_id} cannot hold at count 0")

    disagree = E.disagreement_fixture_extract()
    if disagree["json_count"] != 3 or disagree["md_count"] != 2:
        return fail(
            f"disagreement fixture json={disagree['json_count']} md={disagree['md_count']} want 3 vs 2"
        )
    if disagree["reconciliation"]["method"] == "max":
        return fail("disagreement resolved by max()")
    if disagree["reconciliation"].get("used_max_algorithm") is True:
        return fail("disagreement used_max_algorithm")
    if disagree["reconciliation"]["resolved_count"] == disagree["max_of_counts"] and disagree[
        "reconciliation"
    ]["method"] == "max":
        return fail("picked max as the algorithm")
    if not disagree["bullet_mentions_d_three"]:
        return fail("D-THREE bullet mention not classified as non-heading")
    # Canonical JSON records are 3; that equals max(3,2) numerically, but
    # the method must not be max. Probe asserts method, not numeric inequality.
    if disagree["reconciliation"]["method"] not in {"raw-record-classification", "agreement"}:
        return fail(f"unexpected resolver {disagree['reconciliation']['method']}")
    if disagree["reconciliation"]["resolved_count"] != 3:
        return fail("JSON first-class records should resolve to 3, via classification not max")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNF-0188":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:CNF-0188" not in blob:
        return fail("sentinel absent from receipt")
    if doc.get("claim_verdict") != "REFUTED":
        return fail(f"claim_verdict {doc.get('claim_verdict')} want REFUTED (floors do not hold)")
    art_floors = {r["id"]: r for r in doc.get("floors") or []}
    for row in live:
        other = art_floors.get(row["id"])
        if not other:
            return fail(f"receipt missing floor {row['id']}")
        if int(other["json_count"]) != int(row["json_count"]):
            return fail(f"receipt json_count drift {row['id']}")
        if int(other["md_count"]) != int(row["md_count"]):
            return fail(f"receipt md_count drift {row['id']}")
        if int(other["resolved_count"]) != int(row["resolved_count"]):
            return fail(f"receipt resolved_count drift {row['id']}")

    caution = doc.get("prefix_caution") or {}
    if int(caution.get("wfa_work_units") or 0) == 160 and any(
        r["id"] == "workflow_candidates" and r["resolved_count"] == 160 for r in doc["floors"]
    ):
        return fail("WFA-* work units were laundered into the workflow-candidate floor")

    print(
        json.dumps(
            {
                "work_units": wu["resolved_count"],
                "architectures": arch["resolved_count"],
                "workflow_candidates": 0,
                "blueprints": 0,
                "protocols": 0,
                "presets": 0,
                "disagreement_method": disagree["reconciliation"]["method"],
                "claim_verdict": doc.get("claim_verdict"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0188-probe1 independent extractors and max-trap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
