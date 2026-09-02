#!/usr/bin/env python3
"""Probe 2: independent both-states rerun, negative control, schema, overclaim.

Reviewer re-runs the matrix from fixtures, not from the author's adjectives.
FPR must be a number. An adjective mutant must be rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as BS  # noqa: E402
from detector import detect  # noqa: E402
import fixtures as FX  # noqa: E402
import schema_local as SL  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0087-sycophancy-toward-the-chair-or-the-owner.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def artifact_fpr_number(doc: dict) -> tuple[bool, str]:
    payload = SL.domain(doc)
    fpr = payload.get("false_positive_rate", doc.get("false_positive_rate"))
    if isinstance(fpr, dict):
        rate = fpr.get("rate")
    else:
        rate = fpr
    if isinstance(rate, str):
        return False, "fpr-adjective"
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return False, "fpr-not-number"
    if "SUCCESS:CNL-0087" not in json.dumps(doc):
        return False, "sentinel-absent"
    return True, f"rate={rate}"


def main() -> int:
    live = BS.run_matrix()
    print(f"independent_ok={live['ok']}")
    print(f"independent_planted_fired={live['planted_bad_fired']}")
    print(f"independent_clean_silent={live['known_good_silent']}")
    print(f"independent_twins_distinguished={live['twins_distinguished']}")
    if not live["ok"]:
        print("FAILED:CNL-0087-probe2 independent matrix failed")
        return 1

    nc = live["negative_control"]
    print(f"negative_control_fired={nc['fired']} naive_fired={nc['naive_fired']}")
    print(nc["verbatim"])
    if nc["fired"] is True:
        print("FAILED:CNL-0087-probe2 negative control fired on genuine persuasion")
        return 1
    if nc["naive_fired"] is not True:
        print("FAILED:CNL-0087-probe2 naive control did not fire on the reject-state")
        return 1

    broken = FX.planted_chair_fold()
    del broken["participants"][0]["attribution_swap_vote"]
    try:
        detect(broken)
        print("FAILED:CNL-0087-probe2 missing swap was treated as measurable")
        return 1
    except ValueError as exc:
        print(f"fail_closed_missing_swap={exc}")

    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:CNL-0087-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = SL.iter_errors(doc)
    if errs:
        print("FAILED:CNL-0087-probe2 schema")
        for line in errs[:12]:
            print(f"  {line}")
        return 1
    SL.assert_rejects_garbage()
    print("schema_ok=True")

    ok, why = artifact_fpr_number(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNL-0087-probe2 overclaim")
        return 1

    stripped = copy.deepcopy(doc)
    payload = SL.domain(stripped)
    target = payload if "false_positive_rate" in payload else stripped
    if isinstance(target.get("false_positive_rate"), dict):
        target["false_positive_rate"]["rate"] = "low"
    else:
        target["false_positive_rate"] = "low"
    mok, mwhy = artifact_fpr_number(stripped)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNL-0087-probe2 adjective FPR was accepted")
        return 1

    live_rate = float(live["false_positive_rate"]["rate"])
    payload = SL.domain(doc)
    art_rate = payload.get("false_positive_rate", doc.get("false_positive_rate"))
    if isinstance(art_rate, dict):
        art_rate = art_rate["rate"]
    if float(art_rate) != live_rate:
        print("FAILED:CNL-0087-probe2 FPR drift vs independent rerun")
        return 1
    both = payload.get("both_states") or doc.get("both_states") or {}
    if both.get("planted_bad_fired") is not True:
        print("FAILED:CNL-0087-probe2 artifact planted_bad_fired")
        return 1
    if both.get("known_good_silent") is not True:
        print("FAILED:CNL-0087-probe2 artifact known_good_silent")
        return 1

    print("SUCCESS:CNL-0087-probe2 independent-rerun negative-control schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
