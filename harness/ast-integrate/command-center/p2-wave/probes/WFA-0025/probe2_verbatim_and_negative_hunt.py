#!/usr/bin/env python3
"""Probe 2: verbatim effect sizes and negative-result hunt.

Independent of probe 1's estate walk. Re-runs substring checks against the
frozen quotes and requires negative phrasing in hunt queries. Both-states:
a rounded/paraphrased number, or a dropped hunt, must fail.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import classify as C  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0025-sweep-academic-protocols.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0025-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if doc.get("unit_id") != "WFA-0025":
        return fail(f"unit_id {doc.get('unit_id')}")
    if "SUCCESS:WFA-0025" not in text:
        return fail("sentinel-absent")

    live = C.build_classified(REPO)
    if not live["all_pass"]:
        return fail("live classification did not pass")

    for row in doc.get("protocols") or []:
        primary = row.get("primary") or {}
        ok, why = C.verbatim_ok(primary)
        if not ok:
            return fail(f"{row.get('protocol_id')} verbatim {why}")
        ok, why = C.negative_hunt_ok(row.get("negative_hunt") or {})
        if not ok:
            return fail(f"{row.get('protocol_id')} negative-hunt {why}")
        live_row = next(
            r for r in live["protocols"] if r["protocol_id"] == row["protocol_id"]
        )
        if primary.get("reported_value") != live_row["primary"].get("reported_value"):
            return fail(f"{row['protocol_id']} reported_value drift")
        if primary.get("quote") != live_row["primary"].get("quote"):
            return fail(f"{row['protocol_id']} quote drift")

    controls = C.detector_controls(live)
    if not controls["mutant_round_number_fires"]:
        return fail("rounded-number mutant silent")
    if not controls["mutant_drop_negative_hunt_fires"]:
        return fail("negative-hunt mutant silent")
    if not controls["good_state_silent"]:
        return fail("good state not silent")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    if reviewer.get("verdict") != "PASS":
        return fail("reviewer verdict")

    payload = {
        "probe": "probe2-verbatim-and-negative-hunt",
        "unit_id": "WFA-0025",
        "pass": True,
        "verbatim_rows": len(doc.get("protocols") or []),
        "mutant_round_number_fires": True,
        "mutant_drop_negative_hunt_fires": True,
        "reviewer": "WFA-0025-probe2-verbatim-negative-hunt",
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:WFA-0025-probe2 verbatim effect sizes and negative-result hunt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
