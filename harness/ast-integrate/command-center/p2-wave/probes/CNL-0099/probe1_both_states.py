#!/usr/bin/env python3
"""Probe 1: detector-control, both-states, naive-vs-full negative control.

Re-runs the executable detector on fixtures. Does not trust the artifact's
adjectives: it re-evaluates and then checks the artifact recorded the same
booleans and verbatim dumps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import schema_check as SC  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0099-hallucinated-expertise-and-hidden-conflicts-of-interest.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0099-probe1 {msg}")
    return 1


def main() -> int:
    index = D.load_index()
    control_fix = D.load_fixture(index["detector_control"])
    planted = D.load_fixture(index["planted_bad_primary"])
    good = D.load_fixture(index["known_good_primary"])
    planted_coi = D.load_fixture(index["planted_coi"])
    good_coi = D.load_fixture(index["known_good_coi"])

    gated = D.scan_with_control(good, control_fix)
    print(f"detector_control_ok={gated['ok']}")
    print(f"detector_control_found_known_present={gated['control']['fired']}")
    if not gated["ok"] or not gated["control"]["fired"]:
        return fail("detector-control missed known-present")
    if gated["result"]["fired"]:
        return fail("known-good fired after passing detector-control")

    planted_r = D.evaluate(planted)
    good_r = D.evaluate(good)
    planted_coi_r = D.evaluate(planted_coi)
    good_coi_r = D.evaluate(good_coi)
    naive_exp = D.naive_expertise_tag_match(planted)
    naive_coi = D.naive_coi_declaration_only(planted_coi)
    fp = D.fixture_false_positive_rate()

    checks = [
        ("expertise_fires_on_planted", planted_r["fired"] is True),
        ("expertise_silent_on_good", good_r["fired"] is False),
        ("coi_fires_on_planted", planted_coi_r["fired"] is True),
        ("coi_silent_on_good", good_coi_r["fired"] is False),
        ("naive_tag_silent_on_planted_expertise", naive_exp["fired"] is False),
        ("naive_declaration_silent_on_planted_coi", naive_coi["fired"] is False),
        ("fp_numerator_zero", fp["false_positive_numerator"] == 0),
        ("fp_denominator_positive", fp["false_positive_denominator"] >= 1),
        ("fp_rate_is_float", isinstance(fp["false_positive_rate"], float)),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            return fail(name)

    for name in index["fire"]:
        r = D.evaluate(D.load_fixture(name))
        print(f"fire_fixture {name} fired={r['fired']}")
        if not r["fired"]:
            return fail(f"expected-fire-silent:{name}")
    for name in index["silent"]:
        r = D.evaluate(D.load_fixture(name))
        print(f"silent_fixture {name} fired={r['fired']}")
        if r["fired"]:
            return fail(f"expected-silent-fired:{name}")

    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0099" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")

    spec = SC.payload(doc)
    bs = spec.get("both_states") or {}
    if bs.get("planted_bad", {}).get("fired") is not True:
        return fail("artifact-planted-bad-not-fired")
    if bs.get("known_good", {}).get("fired") is not False:
        return fail("artifact-known-good-not-silent")
    if bs.get("planted_bad", {}).get("verbatim") != D.dump_result(planted_r):
        return fail("artifact-planted-verbatim-drift")
    if bs.get("known_good", {}).get("verbatim") != D.dump_result(good_r):
        return fail("artifact-good-verbatim-drift")
    if spec.get("detector_control", {}).get("found_known_present") is not True:
        return fail("artifact-detector-control-false")
    if not isinstance(spec.get("false_positive_rate"), (int, float)):
        return fail("artifact-fp-not-number")
    if float(spec["false_positive_rate"]) != float(fp["false_positive_rate"]):
        return fail("artifact-fp-drift")

    print(
        f"fp_rate={fp['false_positive_rate']} "
        f"{fp['false_positive_numerator']}/{fp['false_positive_denominator']}"
    )
    print("SUCCESS:CNL-0099-probe1 both-states detector-control naive-negative")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
