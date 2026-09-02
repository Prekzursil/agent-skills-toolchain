#!/usr/bin/env python3
"""Probe 2: both-states detectors; independent table recompute; schema gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detectors as D  # noqa: E402
import measure as M  # noqa: E402

ART = REPO / "command-center/research/RES-0102.json"
SENTINEL = (
    "SUCCESS:RES-0102 in the receipt AND a per-component ablation delta table "
    "including at least one approximately-zero control"
)


def main() -> int:
    live = M.run_experiment()
    both = D.both_states(live)
    print("shipped_ids", both["shipped_ids"])
    print("rejected_silent_probe", both["rejected_silent_probe"])
    for det in both["detectors"]:
        print(
            f"{det['id']} shipped={det['shipped']} "
            f"silent_both={det['silent_in_both_states']} "
            f"good={det['known_good_fixture']['fired']} "
            f"broken={det['known_broken_fixture']['fired']}"
        )
        print(f"  good_out={det['known_good_fixture'].get('output')}")
        print(f"  broken_out={det['known_broken_fixture'].get('output')}")

    if not both["control_detector_shipped"]:
        print("FAILED:RES-0102-probe2 control detector not shipped")
        return 1
    silent_shipped = [
        d
        for d in both["detectors"]
        if d["shipped"] and d["silent_in_both_states"]
    ]
    if silent_shipped:
        print(f"FAILED:RES-0102-probe2 shipped silent-both {silent_shipped}")
        return 1
    always = next(d for d in both["detectors"] if d["id"] == "D-ALWAYS-TRUE")
    if always["shipped"] or not always["silent_in_both_states"]:
        print("FAILED:RES-0102-probe2 silent probe was not rejected")
        return 1
    if D.control_is_approx_zero(D.SYNTHETIC_BROKEN_DELTA):
        print("FAILED:RES-0102-probe2 broken fixture still looks like control")
        return 1
    if D.component_moves(0.0):
        print("FAILED:RES-0102-probe2 identity pair looks like a move")
        return 1

    if not ART.is_file():
        print("FAILED:RES-0102-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0102-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    schema = json.loads((HERE / "measurement-run.schema.json").read_text())
    jsonschema.Draft7Validator(schema).validate(doc)
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    rejected = False
    try:
        jsonschema.Draft7Validator(schema).validate(garbage)
    except jsonschema.ValidationError:
        rejected = True
    print(f"schema_rejects_garbage={rejected}")
    if not rejected:
        print("FAILED:RES-0102-probe2 schema accepts garbage")
        return 1

    art_both = doc.get("detectors") or {}
    if "D-CONTROL-ZERO" not in (art_both.get("shipped_ids") or []):
        print("FAILED:RES-0102-probe2 artifact missing shipped control detector")
        return 1
    if art_both.get("rejected_silent_probe") != "D-ALWAYS-TRUE":
        print("FAILED:RES-0102-probe2 rejected silent probe not recorded")
        return 1

    print(
        "SUCCESS:RES-0102-probe2 both-states detectors, silent probe rejected, "
        "schema discriminates garbage"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
