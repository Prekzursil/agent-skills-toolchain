#!/usr/bin/env python3
"""Probe 1: install v1 through each downgrade path with the advisory present.

Mechanically: rollback, pinned range, exact pin, missing floor, first-listed
index order. Control: a fresh index selects v2; a v1-only index selects v1
(the client is consulting the index). A hardcoded-v2 mutant is exposed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    ADVISORY,
    fresh_index,
    materialize,
    v1_first_index,
    v1_only_index,
)
from resolver import (  # noqa: E402
    V1,
    V2,
    AdvisoryBlocked,
    first_listed,
    resolve,
)

UNIT = "ADV-0066"
ART = REPO / "command-center/adversarial/ADV-0066-version-downgrade-attack.json"
SCHEMA = REPO / "command-center/schema/supply-chain-attestation.schema.json"
GARBAGE = (
    {},
    {"unit_id": UNIT, "passing_tests": 999999},
    {"state": "SUCCESS", "report_kind": "not-attestation"},
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def measure() -> dict:
    materialize()
    fresh = fresh_index()
    v1only = v1_only_index()
    v1first = v1_first_index()
    latest = resolve(fresh, "latest", advisory=ADVISORY, apply_floor=False)
    v1_only_latest = resolve(v1only, "latest", advisory=ADVISORY, apply_floor=False)
    mutant = resolve(v1only, "latest", advisory=ADVISORY, mutant="always-v2")
    rollback = resolve(fresh, V1, advisory=ADVISORY, apply_floor=False)
    pin_range = resolve(
        fresh, ">=1.0.0,<2.0.0", advisory=ADVISORY, apply_floor=False
    )
    pin_exact = resolve(fresh, f"=={V1}", advisory=ADVISORY, apply_floor=False)
    first = first_listed(v1first)
    floor_blocked = False
    try:
        resolve(fresh, V1, advisory=ADVISORY, apply_floor=True)
    except AdvisoryBlocked:
        floor_blocked = True
    consults = latest["version"] == V2 and v1_only_latest["version"] == V1
    mutant_exposed = mutant["version"] == V2 and mutant["consulted_index"] is False
    return {
        "probe": "probe1-downgrade-paths",
        "unit_id": UNIT,
        "pass": bool(
            consults
            and mutant_exposed
            and rollback["version"] == V1
            and pin_range["version"] == V1
            and pin_exact["version"] == V1
            and first["version"] == V1
            and floor_blocked
            and latest["consulted_index"]
            and ADVISORY["revoked"] is False
        ),
        "advisory_id": ADVISORY["id"],
        "advisory_present": True,
        "advisory_revoked": ADVISORY["revoked"],
        "advisory_vulnerable_versions": list(ADVISORY["vulnerable_versions"]),
        "fresh_latest": latest["version"],
        "fresh_consulted_index": latest["consulted_index"],
        "fresh_index_versions": latest["index_versions"],
        "v1_only_latest": v1_only_latest["version"],
        "control_consults_index": consults,
        "hardcoded_v2_mutant_version": mutant["version"],
        "hardcoded_v2_mutant_consulted_index": mutant["consulted_index"],
        "hardcoded_v2_mutant_exposed": mutant_exposed,
        "rollback_installed": rollback["version"],
        "rollback_succeeded": rollback["version"] == V1,
        "pin_range_installed": pin_range["version"],
        "pin_range_succeeded": pin_range["version"] == V1,
        "pin_exact_installed": pin_exact["version"],
        "pin_exact_succeeded": pin_exact["version"] == V1,
        "first_listed_installed": first["version"],
        "first_listed_succeeded": first["version"] == V1,
        "floor_applied_on_attack_paths": False,
        "floor_would_block_v1": floor_blocked,
        "method": "index-consulting-resolver-with-advisory-present-no-floor",
    }


def main() -> int:
    live = measure()
    if not live["pass"]:
        return fail("controls or path matrix failed", live)
    if not live["control_consults_index"]:
        return fail("client is not consulting the index", live)
    if not live["hardcoded_v2_mutant_exposed"]:
        return fail("always-v2 mutant was not distinguishable", live)
    if live["fresh_latest"] != V2:
        return fail("fresh index did not select v2", live)

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:ADV-0066" not in blob:
        return fail("sentinel absent")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)
    errors = list(validator.iter_errors(doc))
    if errors:
        return fail("artifact fails schema", errors[0].message)

    recorded = doc.get("probe1") or {}
    for key in (
        "fresh_latest",
        "v1_only_latest",
        "rollback_installed",
        "pin_range_installed",
        "pin_exact_installed",
        "first_listed_installed",
        "control_consults_index",
        "floor_would_block_v1",
        "hardcoded_v2_mutant_exposed",
        "advisory_id",
    ):
        if recorded.get(key) != live.get(key):
            return fail(
                f"artifact probe1 {key} mismatch",
                {"live": live.get(key), "art": recorded.get(key)},
            )

    cmds = [
        p.get("command")
        for p in (doc.get("named_probes") or [])
        if isinstance(p, dict)
    ]
    if not any("probe1_downgrade_paths.py" in str(c) for c in cmds):
        return fail("named probe1 command absent", cmds)

    (HERE / "probe1-downgrade-paths.raw.json").write_text(
        json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(live, sort_keys=True))
    print("SUCCESS:ADV-0066-probe1 downgrade paths with advisory present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
