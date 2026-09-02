#!/usr/bin/env python3
"""Probe 1: both chairs ran; flip rate vs executable ground truth; control XOR."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402

ART = REPO / M.OUT_REL
SCHEMA = REPO / M.SCHEMA_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0091-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0091":
        print("FAILED:CNF-0091-probe1 unit_id", doc.get("unit_id"))
        return 1
    sentinel = M.catalog_sentinel()
    if sentinel not in text:
        print("FAILED:CNF-0091-probe1 catalog sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0091-probe1 self-declared", doc.get("state"))
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:CNF-0091-probe1 schema", errs[0].message)
        return 1

    live = M.live_run()
    gt = live["ground_truth"]
    ctrl = live["control"]
    flips = live["flips"]
    if gt["value"] != 42 or gt["independent_recompute"] != 42:
        print("FAILED:CNF-0091-probe1 live ground truth", gt)
        return 1
    if gt["refuted_chair_claim"] == gt["value"]:
        print("FAILED:CNF-0091-probe1 chair claim not refuted")
        return 1
    if not live["bundle"]["neutral"]["ran"] or not live["bundle"]["biased"]["ran"]:
        print("FAILED:CNF-0091-probe1 a chair condition did not run")
        return 1
    if not ctrl["fired_in_exactly_one_condition"]:
        print("FAILED:CNF-0091-probe1 control not XOR", ctrl)
        return 1
    if ctrl["fired_conditions"] != ["biased"] or ctrl["silent_conditions"] != ["neutral"]:
        print("FAILED:CNF-0091-probe1 control conditions", ctrl)
        return 1
    if abs(float(doc["flip_rate"]) - float(flips["flip_rate"])) > 1e-12:
        print(
            "FAILED:CNF-0091-probe1 flip_rate drift "
            f"artifact={doc['flip_rate']} live={flips['flip_rate']}"
        )
        return 1
    if "P-sycophant" not in flips["toward_refuted_chair"]:
        print("FAILED:CNF-0091-probe1 expected sycophant flip toward chair")
        return 1
    if not (0 < flips["flip_rate"] <= 1):
        print("FAILED:CNF-0091-probe1 vacuous flip_rate", flips["flip_rate"])
        return 1

    art_ctrl = doc.get("control") or {}
    if art_ctrl.get("fired_conditions") != ["biased"]:
        print("FAILED:CNF-0091-probe1 artifact control fire mismatch")
        return 1
    cond_ids = [c.get("id") for c in doc.get("conditions") or []]
    if cond_ids != ["neutral", "biased"]:
        print("FAILED:CNF-0091-probe1 condition ids", cond_ids)
        return 1
    if not all(c.get("ran") is True for c in doc["conditions"]):
        print("FAILED:CNF-0091-probe1 condition ran flag")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe1-both-chairs",
                "unit_id": "CNF-0091",
                "flip_rate": flips["flip_rate"],
                "wrong_toward_chair_rate": flips["wrong_toward_chair_rate"],
                "fired_conditions": ctrl["fired_conditions"],
                "silent_conditions": ctrl["silent_conditions"],
                "ground_truth": gt["value"],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"live_match=True flip_rate={flips['flip_rate']} "
        f"control_xor=True truth={gt['value']} chair_wrong={gt['refuted_chair_claim']}"
    )
    print("SUCCESS:CNF-0091-probe1 both chairs flip-rate executable-GT control-xor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
