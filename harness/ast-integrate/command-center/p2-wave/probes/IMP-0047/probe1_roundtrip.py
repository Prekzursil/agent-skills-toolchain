#!/usr/bin/env python3
"""Named probe 1: apply-then-inverse hash census + wrong-inverse negative control.

Signal 1 is the per-file sha256 map. Signal 2 is a blake2b tree digest over
path+size+bytes. Both must restore after a declared inverse. A step with a
deliberately wrong inverse must fail the round-trip (both-states).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from plugin.migration import (  # noqa: E402
    MigrationEngine,
    Step,
    blake2_tree_digest,
    build_demo_tree,
    censuses,
    censuses_equal,
    demo_engine,
    demo_step_specs,
    sha256_file_census,
    validate_step_spec,
    wrong_inverse_spec,
)

ART = REPO / "command-center/receipts/IMP-0047.json"
UNIT = "IMP-0047"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    for spec in demo_step_specs():
        validate_step_spec(spec)

    before_files: dict = {}
    before_blake = ""
    after_blake = ""

    with tempfile.TemporaryDirectory(prefix="imp0047-p1-") as tmp:
        root = build_demo_tree(Path(tmp) / "good")
        journal = Path(tmp) / "good.json"
        before_files = sha256_file_census(root)
        before_blake = blake2_tree_digest(root)
        engine = demo_engine()
        engine.migrate(root, "3", journal=journal)
        mid = censuses(root)
        if mid["file_census"] == before_files:
            return fail("apply did not change the tree (vacuous round-trip)")
        engine.invert(root, "0", journal=journal)
        after_files = sha256_file_census(root)
        after_blake = blake2_tree_digest(root)
        if after_files != before_files:
            return fail("file-sha256 census mismatch after inverse")
        if after_blake != before_blake:
            return fail("blake2 census mismatch after inverse")

        bad_root = build_demo_tree(Path(tmp) / "bad")
        bad_journal = Path(tmp) / "bad.json"
        bad_before = censuses(bad_root)
        bad_engine = MigrationEngine([Step(wrong_inverse_spec())])
        bad_engine.migrate(bad_root, "1", journal=bad_journal)
        bad_engine.invert(bad_root, "0", journal=bad_journal)
        bad_after = censuses(bad_root)
        if censuses_equal(bad_before, bad_after):
            return fail("wrong inverse was silent (negative control did not fire)")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("unit_id") != UNIT:
            return fail(f"artifact unit_id={doc.get('unit_id')}")
        blob = json.dumps(doc)
        if "SUCCESS:IMP-0047" not in blob:
            return fail("sentinel absent")
        rec = doc.get("round_trip") or {}
        if rec.get("file_census_restored") is not True:
            return fail("artifact round_trip.file_census_restored is not true")
        if rec.get("blake2_restored") is not True:
            return fail("artifact round_trip.blake2_restored is not true")
        if rec.get("before_blake2") != before_blake:
            return fail("artifact before_blake2 drifted from live")
        neg = doc.get("negative_control_wrong_inverse") or {}
        if neg.get("round_trip_equal") is not False:
            return fail("artifact does not record wrong-inverse failure")

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": UNIT,
        "file_count": len(before_files),
        "before_blake2": before_blake,
        "after_blake2": after_blake,
        "file_census_restored": True,
        "blake2_restored": True,
        "wrong_inverse_detected": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UNIT}-probe1 apply-inverse round-trip and wrong-inverse negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
