#!/usr/bin/env python3
"""Probe 2: disjointness, sum check, known-present, known-absent, regex silence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import extractors as E  # noqa: E402

ART = E.ART


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0188-probe2 {msg}")
    return 1


def main() -> int:
    council = E.council_fixture_extract()
    disagree = E.disagreement_fixture_extract()
    tests = {t["id"]: t for t in E.detector_tests(council, disagree)}
    required = [
        "disjointness",
        "sum-check",
        "known-present",
        "known-absent",
        "regex-silence",
        "max-trap",
        "disagreement-not-max",
    ]
    for tid in required:
        t = tests.get(tid)
        if t is None:
            return fail(f"missing test {tid}")
        if not t["pass"]:
            return fail(f"{tid} failed detail={t.get('detail')}")

    if council["intersection"] or council["md_intersection"]:
        return fail("protocol/preset id intersection not empty")
    if council["json_sum"] != council["h4_count"] or council["md_sum"] != council["h4_count"]:
        return fail("category counts do not equal heading total")
    if KNOWN := E.KNOWN_PROTOCOL:
        if KNOWN not in council["json_protocols"] or KNOWN not in council["md_protocols"]:
            return fail(f"known protocol {KNOWN} missing")
    if E.KNOWN_PRESET not in council["json_presets"] or E.KNOWN_PRESET not in council["md_presets"]:
        return fail("known preset missing")
    if E.ABSENT in council["json_protocols"] or E.ABSENT in council["md_presets"]:
        return fail("absent sentinel found by extractor")
    if council["protocol_re_on_preset_section"] or council["preset_re_on_protocol_section"]:
        return fail("regex silence broken")
    if council["wrong_max_json"] == council["json_sum"]:
        return fail("max trap collapsed to the sum; fixture is not discriminating")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:CNF-0188" not in json.dumps(doc):
        return fail("sentinel absent")
    art_tests = {t["id"]: t for t in doc.get("tests") or []}
    for tid in required:
        if not art_tests.get(tid, {}).get("pass"):
            return fail(f"receipt test {tid} not pass")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        return fail(f"reviewer verdict {reviewer.get('verdict')}")
    if not reviewer.get("independent"):
        return fail("reviewer not independent")
    if int(reviewer.get("work_units_third_extractor_disagreement") or 0) <= 0:
        return fail("third extractor did not disagree with identity count on sentinels")
    if reviewer.get("resolved_work_units") != next(
        r["resolved_count"] for r in doc["floors"] if r["id"] == "work_units"
    ):
        return fail("reviewer resolved work_units by a different number than identity")
    if reviewer.get("did_not_pick_max") is not True:
        return fail("reviewer did not record refusing max()")

    print(
        json.dumps(
            {
                "disjoint": True,
                "h4": council["h4_count"],
                "sum": council["json_sum"],
                "wrong_max": council["wrong_max_json"],
                "known_protocol": E.KNOWN_PROTOCOL,
                "absent": E.ABSENT,
                "reviewer_sentinel_gap": reviewer.get("work_units_third_extractor_disagreement"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:CNF-0188-probe2 detector controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
