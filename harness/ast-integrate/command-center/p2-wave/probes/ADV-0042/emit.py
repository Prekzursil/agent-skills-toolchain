#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0042-gui-capture-surface-leakage.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"unit_id": "ADV-0042", "state": "SUCCESS"},
    {"x": "x" * 2000},
)


def write_doc(doc: dict) -> None:
    out = L.REPO / L.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if L.SENTINEL not in text:
        raise SystemExit("FAILED:ADV-0042 emit sentinel not in serialized artifact")
    out.write_text(text, encoding="utf-8")


def main() -> int:
    meas = L.live_measurement()
    if meas["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:ADV-0042 emit overall", meas["state"])
        return 1
    if not meas["controls_ok"]:
        print("FAILED:ADV-0042 emit controls not calibrated")
        print(json.dumps({
            "histogram": meas["capture"]["histogram_calibrated"],
            "retention": meas["capture"]["retention_calibrated"],
        }, indent=2, sort_keys=True))
        return 1
    raw1 = L.probe1_report(meas)
    raw2 = L.probe2_report(meas)
    doc = L.build_artifact_doc(meas, raw1, raw2)
    errs = L.validate_doc(doc)
    if errs:
        print("FAILED:ADV-0042 emit schema")
        for e in errs[:20]:
            print(" ", e)
        return 1
    import jsonschema

    validator = jsonschema.Draft7Validator(L.load_schema())
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:ADV-0042 emit schema accepted garbage", garbage)
            return 1
    write_doc(doc)
    out = L.REPO / L.OUT_REL
    print(
        f"wrote {L.OUT_REL} bytes={out.stat().st_size} sha256={L.sha256_file(out)} "
        f"state={doc['state']} overall={doc['overall_verdict']}"
    )
    print("SUCCESS:ADV-0042 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
