#!/usr/bin/env python3
"""Probe 1: detector-control, both-states, negative control, FP rate as a number."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import checks as C  # noqa: E402
import detector as D  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0088-participant-dominance-and-airtime-concentration.md"
)


def main() -> int:
    bundle = C.both_states()
    errors = C.assert_both_states(bundle)
    fp = C.fp_bundle()
    rate = fp["rate"]
    print(f"detector_control_fired={bundle['detector_control']['fired']}")
    print(f"planted_airtime_fired={bundle['planted_airtime']['fired']}")
    print(f"planted_claims_fired={bundle['planted_claims']['fired']}")
    print(f"known_good_silent={bundle['known_good']['silent']}")
    print(f"attestation_wolf_silent={not bundle['attestation_wolf']['fired']}")
    print(f"prolific_silent={not bundle['prolific']['fired']}")
    print(
        f"false_positive_rate={rate['value']} "
        f"numerator={rate['numerator']} denominator={rate['denominator']}"
    )
    print("planted_airtime_verbatim=" + C.compact(bundle["planted_airtime"]))
    print("known_good_verbatim=" + C.compact(bundle["known_good"]))
    print("negative_control_verbatim=" + C.compact(bundle["attestation_wolf"]))
    print("detector_control_verbatim=" + C.compact(bundle["detector_control"]))
    if rate["value"] != 0.0 or rate["numerator"] != 0 or rate["denominator"] != 12:
        errors.append(
            f"FP rate expected 0/12, got {rate['numerator']}/{rate['denominator']}"
        )
    if not ART.is_file():
        errors.append("artifact missing")
    else:
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            errors.append(f"artifact self-declared {doc.get('state')}")
        if "SUCCESS:CNL-0088" not in text:
            errors.append("sentinel absent")
        bs = doc.get("both_states") or {}
        if bs.get("planted_bad", {}).get("fired") is not True:
            errors.append("artifact planted_bad.fired is not true")
        if bs.get("known_good", {}).get("fired") is not False:
            errors.append("artifact known_good.fired is not false")
        fp_doc = doc.get("false_positive_rate") or {}
        if not isinstance(fp_doc.get("value"), (int, float)):
            errors.append("artifact false_positive_rate.value is not a number")
        dc = doc.get("detector_control") or {}
        if dc.get("known_present_run_before_absence") is not True:
            errors.append("artifact detector_control missing known-present-first")
        if dc.get("known_present_fired") is not True:
            errors.append("artifact detector_control did not fire")
        blob = json.dumps(doc)
        if D.FIRE_RULE not in blob and D.FIRE_RULE not in (
            (doc.get("detector") or {}).get("mechanism") or ""
        ):
            errors.append("artifact missing fire rule")
    if errors:
        for e in errors:
            print(f"FAILED:CNL-0088-probe1 {e}")
        return 1
    print("SUCCESS:CNL-0088-probe1 both-states detector-control fp-rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
