#!/usr/bin/env python3
"""Probe 2: negative control, numeric false-positive rate, schema, three-ack floor.

Independent of probe 1's narrative: re-runs the battery, requires the catalog
artifact, and records what the check does on the state it is meant to reject
(firing on a clean nothing-to-add / engaged council).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import local_schema as S  # noqa: E402

OUT = HERE / "probe2-negative-fp.raw.json"
ART = REPO / "command-center/design/council/CNL-0089-silence-and-the-minimum-engagement-floor.md"
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"
FILLER = "planted-filler-consent.json"
NEG = "clean-all-engaged.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNL-0089-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print("FAILED:CNL-0089-probe2 artifact not JSON", exc)
        return 1
    if "SUCCESS:CNL-0089" not in text:
        print("FAILED:CNL-0089-probe2 sentinel absent")
        return 1
    if doc.get("unit_id") != "CNL-0089":
        print("FAILED:CNL-0089-probe2 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNL-0089-probe2 self-declared", doc.get("state"))
        return 1

    if not SCHEMA.is_file():
        print("FAILED:CNL-0089-probe2 schema file missing")
        return 1
    empty_errs = S.errors_of({})
    if not empty_errs:
        print("FAILED:CNL-0089-probe2 schema accepted empty object")
        return 1
    garbage_errs = S.errors_of({"totally": "unrelated", "passing_tests": 999999})
    if not garbage_errs:
        print("FAILED:CNL-0089-probe2 schema accepted garbage")
        return 1
    errs = S.errors_of(doc)
    if errs:
        print("FAILED:CNL-0089-probe2 schema")
        for e in errs[:12]:
            print(" ", e)
        return 1

    payload = S.domain(doc)
    if payload.get("kind") != "council-detector-spec":
        print("FAILED:CNL-0089-probe2 report.kind", payload.get("kind"))
        return 1
    rate = payload.get("false_positive_rate")
    if not isinstance(rate, (int, float)) or isinstance(rate, bool):
        print("FAILED:CNL-0089-probe2 false_positive_rate is not a number")
        return 1

    batt = D.battery()
    if not batt["planted_all_fired"]:
        print("FAILED:CNL-0089-probe2 planted fixture did not fire")
        return 1
    if not batt["clean_all_silent"]:
        print("FAILED:CNL-0089-probe2 clean fixture fired (false positive)")
        return 1
    live_rate = batt["false_positive_rate"]
    if live_rate != 0.0:
        print("FAILED:CNL-0089-probe2 live fp rate", live_rate)
        return 1
    if float(rate) != float(live_rate):
        print("FAILED:CNL-0089-probe2 artifact fp rate mismatch", rate, live_rate)
        return 1

    filler = D.scan_file(FILLER)
    if not filler["fired"] or "filler-masquerade" not in filler["seats"]["D"]["reasons"]:
        print("FAILED:CNL-0089-probe2 three empty acks satisfied the floor")
        return 1

    neg = D.scan_file(NEG)
    neg_verbatim = json.dumps(
        {
            "fixture_id": neg["fixture_id"],
            "fired": neg["fired"],
            "silent": neg["silent"],
            "fired_seats": neg["fired_seats"],
        },
        sort_keys=True,
    )
    print("NEGATIVE-CONTROL state the check is meant to reject (firing on engaged)")
    print(neg_verbatim)
    if not neg["silent"]:
        print("FAILED:CNL-0089-probe2 negative control fired")
        return 1

    control = payload.get("detector_control") or {}
    if not control.get("known_present_run_first"):
        print("FAILED:CNL-0089-probe2 detector-control flag missing")
        return 1

    raw = {
        "false_positive_rate": live_rate,
        "false_positive_count": batt["false_positive_count"],
        "clean_count": batt["clean_count"],
        "three_empty_acks_fail_floor": True,
        "negative_control_silent": True,
        "negative_control_verbatim": neg_verbatim,
        "schema_ok": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"false_positive_rate={live_rate} "
        f"three_empty_acks_fail_floor=True "
        f"negative_control_silent=True"
    )
    print("SUCCESS:CNL-0089-probe2 negative control and numeric false-positive rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
