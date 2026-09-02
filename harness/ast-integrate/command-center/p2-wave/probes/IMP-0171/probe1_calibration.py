#!/usr/bin/env python3
"""Named probe 1: planted mutant classes land in reported numeric bands.

Calibration, not adjectives. Re-runs the instrument against the planted
corpus and checks every class's live min/max against the receipt bands.
A mutant of the receipt that replaces numbers with 'high'/'low' is rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import calibrate as cal  # noqa: E402
import corpus as C  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0171.json"
ADJECTIVES = {
    "high",
    "low",
    "medium",
    "strong",
    "weak",
    "similar",
    "close",
    "near",
    "far",
    "duplicate",
    "distinct",
}


def _is_number(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _bands_are_numeric(bands: dict) -> tuple[bool, str]:
    for cls, band in bands.items():
        if not isinstance(band, dict):
            return False, f"{cls} band is {type(band).__name__}, not an object"
        for key in ("min", "max", "mean"):
            val = band.get(key)
            if isinstance(val, str) and val.strip().lower() in ADJECTIVES:
                return False, f"{cls}.{key} is adjective {val!r}"
            if not _is_number(val):
                return False, f"{cls}.{key} is {val!r} (not a number)"
        if float(band["min"]) > float(band["max"]):
            return False, f"{cls} min > max"
    return True, "ok"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0171-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0171-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0171-probe1 receipt not an object")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0171-probe1 self-declared {st}")
        return 1
    if "SUCCESS:IMP-0171" not in text:
        print("FAILED:IMP-0171-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "IMP-0171":
        print(f"FAILED:IMP-0171-probe1 unit_id {doc.get('unit_id')}")
        return 1

    cal_doc = doc.get("calibration")
    if not isinstance(cal_doc, dict):
        print("FAILED:IMP-0171-probe1 calibration object absent")
        return 1
    bands = cal_doc.get("bands")
    if not isinstance(bands, dict) or not bands:
        print("FAILED:IMP-0171-probe1 bands absent")
        return 1
    ok, why = _bands_are_numeric(bands)
    if not ok:
        print(f"FAILED:IMP-0171-probe1 {why}")
        return 1

    live = cal.calibrate()
    live_bands = live["bands"]
    for cls in list(C.HIGH_BAND_CLASSES) + list(C.LOW_BAND_CLASSES):
        if cls not in bands:
            print(f"FAILED:IMP-0171-probe1 missing reported band {cls}")
            return 1
        reported = bands[cls]
        got = live_bands[cls]
        for key in ("min", "max"):
            if abs(float(reported[key]) - float(got[key])) > 1e-9:
                print(
                    f"FAILED:IMP-0171-probe1 {cls}.{key} reported="
                    f"{reported[key]} live={got[key]}"
                )
                return 1
        for score in got["scores"]:
            if score < float(reported["min"]) - 1e-9 or score > float(
                reported["max"]
            ) + 1e-9:
                print(
                    f"FAILED:IMP-0171-probe1 {cls} score {score} outside "
                    f"[{reported['min']}, {reported['max']}]"
                )
                return 1

    if not live["separated"] or not cal_doc.get("separated"):
        print("FAILED:IMP-0171-probe1 bands are not separated")
        return 1
    if float(cal_doc["high_band_min"]) <= float(cal_doc["low_band_max"]):
        print("FAILED:IMP-0171-probe1 high_band_min not above low_band_max")
        return 1

    scope = str(doc.get("scope") or cal_doc.get("scope") or "")
    if "LEXICAL" not in scope.upper() or "NOT detectable" not in scope:
        print("FAILED:IMP-0171-probe1 scope does not state lexical limit")
        return 1

    mutant = copy.deepcopy(doc)
    mutant["calibration"]["bands"]["exact_rename"]["min"] = "high"
    mutant["calibration"]["bands"]["known_distinct"]["max"] = "low"
    mut_ok, mut_why = _bands_are_numeric(mutant["calibration"]["bands"])
    if mut_ok:
        print("FAILED:IMP-0171-probe1 adjective mutant was accepted")
        return 1

    payload = {
        "adjective_mutant_rejected": True,
        "adjective_mutant_reason": mut_why,
        "bands_numeric": True,
        "classes_checked": sorted(live_bands),
        "high_band_min": live["high_band_min"],
        "low_band_max": live["low_band_max"],
        "pass": True,
        "probe": "probe1-calibration-bands",
        "separated": True,
        "unit_id": "IMP-0171",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "bands_numeric=True adjective_mutant_rejected=True "
        f"high_min={live['high_band_min']} low_max={live['low_band_max']}"
    )
    print("SUCCESS:IMP-0171-probe1 planted classes land in numeric bands")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
