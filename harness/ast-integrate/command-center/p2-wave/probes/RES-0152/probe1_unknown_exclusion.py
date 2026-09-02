#!/usr/bin/env python3
"""Probe 1: definition frozen before count; planted unknown-outcome claims excluded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    DEFINITION_PATH,
    fixture_both_states,
    load_definition,
    measure,
    planted_controls,
    sha256_file,
)

REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center"
    / "research"
    / "evidence-quality"
    / "RES-0152-confidence-band-calibration-set.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0152-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    definition = load_definition()
    live_hash = sha256_file(DEFINITION_PATH)
    if definition["_sha256"] != live_hash:
        return fail("in-memory definition hash drifted from disk")
    recorded = doc.get("definition") or {}
    if recorded.get("sha256") != live_hash:
        return fail("artifact definition.sha256 does not match DEFINITION.json")
    if recorded.get("frozen_before_count") is not True:
        return fail("definition not marked frozen_before_count")
    if recorded.get("same_rule_all_vendors") is not True:
        return fail("same_rule_all_vendors is not true")
    if doc.get("definition_locked_hash_before_enumerate") is not True:
        return fail("hash was not locked before enumeration")
    if len(planted_controls(definition)) < 5:
        return fail("definition has fewer than 5 planted unknown controls")

    live = measure()
    fx = fixture_both_states(definition)
    if not fx["good_silent"]:
        return fail("fixture good state was not silent")
    if not fx["bad_fires"]:
        return fail("fixture did not fire when unknowns were scored")
    dc = live["detector_control"]
    if not dc.get("pass"):
        return fail("live detector_control did not pass")
    if int(dc.get("unknown_n") or 0) < 5:
        return fail("fewer than 5 unknown-outcome control claims")
    if not dc.get("good_excludes_unknowns"):
        return fail("live unknown controls were scored")

    scored_ids = {
        r["id"]
        for r in live["rows"]
        if r.get("scored") is True
    }
    for uid in live.get("unknown_control_ids") or []:
        cid = f"PLANTED-UNKNOWN-{uid}"
        if cid in scored_ids:
            return fail(f"unknown control {cid} was scored")
        planted_path = None
        for item in planted_controls(definition):
            if str(item["id"]) == str(uid):
                planted_path = str(item.get("output_path") or "")
                break
        if planted_path and (REPO / planted_path).exists():
            return fail(f"planted unknown path exists on disk: {planted_path}")

    cal = doc.get("calibration") or {}
    if int(cal.get("n_unknown_excluded") or 0) < 5:
        return fail("artifact excluded fewer than 5 unknowns")
    if int(cal.get("n_scored_forward") or 0) < 60:
        return fail("artifact scored fewer than 60 known-outcome forward-looking claims")

    payload = {
        "probe": "probe1-unknown-exclusion",
        "unit_id": "RES-0152",
        "definition_sha256": live_hash,
        "frozen_before_count": True,
        "same_rule_all_vendors": True,
        "unknown_n": dc["unknown_n"],
        "unknown_ids": dc["unknown_ids"],
        "fixtures": {
            "good_silent": fx["good_silent"],
            "bad_fires": fx["bad_fires"],
        },
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:RES-0152-probe1 definition frozen before count; "
        "5 unknown-outcome claims excluded; scoring them fires"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
