#!/usr/bin/env python3
"""Probe 1: every CAUSE maps to RIVAL or SINGLE-HYPOTHESIS; schema; planted miss fires."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate  # noqa: E402
import generate as G  # noqa: E402

ART = G.REPO / "command-center/synthesis/SYN-0003.rival-explanations.json"
SCHEMA = G.REPO / "command-center/schema/rival-hypothesis.schema.json"
SENTINEL_PREFIX = "SUCCESS:SYN-0003"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0003-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    if not SCHEMA.is_file() or SCHEMA.stat().st_size <= 0:
        return fail("declared schema missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    G.validate_doc(doc)

    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}]
    rejected = 0
    validator = jsonschema.Draft7Validator(G.DISCRIMINATOR)
    for g in garbage:
        try:
            validator.validate(g)
        except jsonschema.ValidationError:
            rejected += 1
    print(f"schema_garbage_rejected={rejected}/3")
    if rejected != 3:
        return fail("schema accepts garbage")

    text = ART.read_text(encoding="utf-8")
    unit = G.catalog_unit("SYN-0003")
    sentinel = str(unit.get("completion_sentinel") or "")
    if sentinel not in text or not str(doc.get("sentinel") or "").startswith(SENTINEL_PREFIX):
        return fail("catalog sentinel absent from artifact")
    if doc.get("unit_id") != "SYN-0003":
        return fail("unit_id")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    hier = G.load_hierarchy()
    cause_ids = [c["id"] for c in hier["causes"]]
    records = doc.get("records") or []
    if set(cause_ids) != set(doc.get("hierarchy_source", {}).get("cause_ids") or []):
        return fail("artifact cause_ids != loaded hierarchy")

    # Detector-control first: planted missing CAUSE must FIRE.
    planted_ids = cause_ids + ["CAUSE-PLANTED-ORPHAN"]
    planted = gate.coverage(planted_ids, records)
    print("detector_control_first=True")
    print(f"planted_missing_ok={planted['ok']} missing={planted['missing_cause_ids']}")
    if planted["ok"] or "CAUSE-PLANTED-ORPHAN" not in planted["missing_cause_ids"]:
        return fail("planted missing cause did not FIRE")
    print("detector_control_found_known_present=True")

    planted_drop = gate.coverage(cause_ids, records[:-1] if records else [])
    if planted_drop["ok"]:
        return fail("truncated records did not FIRE")

    planted_nd = copy.deepcopy(records)
    if planted_nd:
        planted_nd[0]["label"] = "NON-DISCRIMINATING"
        nd_cov = gate.coverage(cause_ids, planted_nd)
        if nd_cov["ok"]:
            return fail("NON-DISCRIMINATING counted as completing")
        print("non_discriminating_does_not_complete=True")

    live = gate.coverage(cause_ids, records)
    print(
        f"live_coverage_ok={live['ok']} causes={live['cause_count']} "
        f"rivals={live['rival_count']} single={live['single_hypothesis_count']}"
    )
    if not live["ok"]:
        return fail(f"live coverage gaps {live}")
    if live["cause_count"] < 1:
        return fail("no cause nodes")

    print("SUCCESS:SYN-0003-probe1 coverage schema planted-orphan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
