#!/usr/bin/env python3
"""Named probe 2: known-good is silent; disabling one sub-check is detected.

NEGATIVE CONTROL: known-good yields zero findings in the same run as known-bad.
MUTATION: drop secret-gate from the composer; composition equality must fail
and the missing rule id must be exactly secret-gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.checks import RULE_IDS  # noqa: E402
from marketplace.fixtures import BAD, GOOD, SYNTHETIC_SECRET_BODY, materialize  # noqa: E402
from marketplace.package_linter import composition_sets, lint_package  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0113.json"


def main() -> int:
    materialize()
    good = lint_package(GOOD)
    bad = lint_package(BAD)
    baseline = composition_sets(BAD)
    dropped = "secret-gate"
    mutated = composition_sets(BAD, enabled=[r for r in RULE_IDS if r != dropped])
    good_blob = json.dumps(good, sort_keys=True)
    bad_blob = json.dumps(bad, sort_keys=True)
    payload = {
        "probe": "probe2-negative-mutation",
        "unit_id": "IMP-0113",
        "good_finding_count": good["finding_count"],
        "good_ok": good["ok"],
        "bad_finding_count": bad["finding_count"],
        "baseline_equal": baseline["equal"],
        "mutated_equal": mutated["equal"],
        "missing_after_mutation": mutated["union_minus_linter"],
        "secret_body_in_good": SYNTHETIC_SECRET_BODY in good_blob,
        "secret_body_in_bad": SYNTHETIC_SECRET_BODY in bad_blob,
    }
    print(json.dumps(payload, sort_keys=True))
    if good["finding_count"] != 0 or good["ok"] is not True:
        print("FAILED:IMP-0113-probe2 known-good is not silent", good)
        return 1
    if bad["finding_count"] < 1:
        print("FAILED:IMP-0113-probe2 known-bad produced no findings")
        return 1
    if not baseline["equal"]:
        print("FAILED:IMP-0113-probe2 baseline composition unequal", baseline)
        return 1
    if mutated["equal"]:
        print("FAILED:IMP-0113-probe2 mutation was silent")
        return 1
    if mutated["union_minus_linter"] != [dropped]:
        print("FAILED:IMP-0113-probe2 mutation mismatch", mutated)
        return 1
    if SYNTHETIC_SECRET_BODY in bad_blob or SYNTHETIC_SECRET_BODY in good_blob:
        print("FAILED:IMP-0113-probe2 secret body leaked")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0113-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0113-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0113" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0113-probe2 sentinel absent")
        return 1
    print("SUCCESS:IMP-0113-probe2 known-good silent and mutation detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
