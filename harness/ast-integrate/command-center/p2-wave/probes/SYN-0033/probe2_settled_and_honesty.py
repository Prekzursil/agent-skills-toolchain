#!/usr/bin/env python3
"""Probe 2: adjudicated pairs stay SETTLED; empty zero has a denominator; schema."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import overclaim as O  # noqa: E402
from sweep import live_sweep, verdict_for  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0033.cross-phase-contradictions.json"
SCHEMA = REPO / "command-center/schema/contradiction-report.schema.json"
SENTINEL = (
    "SUCCESS:SYN-0033 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the examined-pair count "
    "is published and every open contradiction names a settling probe. Any "
    "other terminal state is FAILED:SYN-0033 <classification> with the "
    "diagnostic tail attached."
)


def main() -> int:
    settled = C.settled_not_reopened()
    scoped = C.scoped_differently_silent()
    empty = C.empty_zero_has_denominator()
    checks = [
        ("settled_not_reopened", settled.get("ok")),
        ("scoped_differently_silent", scoped.get("ok")),
        ("empty_zero_has_denominator", empty.get("ok")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:SYN-0033-probe2 {name}")
            if name == "settled_not_reopened":
                print(f"  row={settled.get('row')}")
            if name == "empty_zero_has_denominator":
                print(f"  examined={empty.get('examined')} verdict={empty.get('verdict')}")
            return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:SYN-0033-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:SYN-0033-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:SYN-0033-probe2 self-declared", doc.get("state"))
        return 1
    if not SCHEMA.is_file():
        print("FAILED:SYN-0033-probe2 schema missing")
        return 1
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0033-probe2 schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:SYN-0033-probe2 schema accepted garbage {list(garbage)[:2]}")
            return 1

    ok, why = O.check_overclaim(doc)
    print(f"artifact_overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:SYN-0033-probe2 overclaim on live artifact")
        return 1

    live = live_sweep(REPO)
    live_verdict = verdict_for(live)
    if live_verdict != doc.get("verdict"):
        print("FAILED:SYN-0033-probe2 live verdict drift", live_verdict, doc.get("verdict"))
        return 1
    if live["examined_pair_count"] != int(doc["examined_pair_count"]):
        print("FAILED:SYN-0033-probe2 live examined drift")
        return 1
    if not live["registry_present"] and doc.get("verdict") != "NOT-CHECKED":
        print("FAILED:SYN-0033-probe2 missing registry not NOT-CHECKED")
        return 1
    if int(doc["examined_pair_count"]) == 0 and doc.get("verdict") == "CONFIRMED":
        print("FAILED:SYN-0033-probe2 CONFIRMED on zero pairs")
        return 1

    print(
        "settled={0} empty_examined={1} live_verdict={2} live_examined={3}".format(
            settled["settled_ids"],
            empty["examined"],
            doc.get("verdict"),
            doc.get("examined_pair_count"),
        )
    )
    print("SUCCESS:SYN-0033-probe2 settled-not-reopened empty-denominator schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
