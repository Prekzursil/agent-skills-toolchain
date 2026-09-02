#!/usr/bin/env python3
"""Named probe 2: both-states control plus one negative per contract rule.

Different field from probe 1: detector vacuity (conforming pass / naive fail),
not the user-owned inventory set-difference.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import RULE_IDS  # noqa: E402
from suite import run_both_states, run_negatives  # noqa: E402

ART = REPO / "command-center/receipts/TST-0048.json"
RAW = HERE / "probe2-both-states.raw.json"
SENTINEL = "SUCCESS:TST-0048"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:TST-0048-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:TST-0048-probe2 sentinel absent")
        return 1
    if doc.get("unit_id") != "TST-0048":
        print("FAILED:TST-0048-probe2 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="tst0048-p2-") as tmp:
        root = Path(tmp)
        both = run_both_states(root / "both")
        negatives = run_negatives(root / "neg")

    if both["vacuous_suite"]:
        print("FAILED:TST-0048-probe2 suite is vacuous (naive also passed)")
        return 1
    if not both["detector_ok"]:
        print(
            "FAILED:TST-0048-probe2 detector_ok false "
            f"conforming={both['conforming_pass']} naive_fail={both['nonconforming_fails']}"
        )
        return 1
    if not both["naive_deleted_user_owned"]:
        print("FAILED:TST-0048-probe2 naive mutant did not delete user-owned paths")
        return 1
    silent = [n["rule"] for n in negatives if not n["fired_on_bad_state"]]
    if silent:
        print("FAILED:TST-0048-probe2 negatives did not fire", silent)
        return 1
    if [n["rule"] for n in negatives] != list(RULE_IDS):
        print("FAILED:TST-0048-probe2 negative rule id drift")
        return 1

    rec_both = doc.get("both_states") or {}
    if rec_both.get("detector_ok") is not True or rec_both.get("vacuous_suite") is not False:
        print("FAILED:TST-0048-probe2 receipt both_states does not match live detector")
        return 1
    control = doc.get("both_states_control") or {}
    if control.get("fired_on_bad") is not True or control.get("silent_on_good") is not True:
        print("FAILED:TST-0048-probe2 both_states_control missing or false", control)
        return 1
    if doc.get("kind") != "conformance-report":
        print("FAILED:TST-0048-probe2 kind", doc.get("kind"))
        return 1
    schemas = doc.get("schemas_under_test") or []
    if len(schemas) < 6:
        print("FAILED:TST-0048-probe2 schemas_under_test count", len(schemas))
        return 1
    rules = doc.get("contract_rules") or []
    if any(r.get("result") != "PASS" for r in rules) or len(rules) != len(RULE_IDS):
        print("FAILED:TST-0048-probe2 contract_rules not all PASS")
        return 1
    if doc.get("all_negatives_fired") is not True:
        print("FAILED:TST-0048-probe2 receipt all_negatives_fired is not true")
        return 1
    rec_negs = doc.get("negatives") or []
    if len(rec_negs) != len(RULE_IDS):
        print("FAILED:TST-0048-probe2 receipt negative count", len(rec_negs))
        return 1
    exercises = doc.get("real_artifact_exercises") or []
    if not exercises:
        print("FAILED:TST-0048-probe2 real_artifact_exercises empty")
        return 1
    for e in exercises:
        note = e.get("note")
        nerr = int(e.get("error_count") or 0)
        if note == "want-reject" and nerr < 1:
            print("FAILED:TST-0048-probe2 want-reject was accepted", e)
            return 1
        if note == "want-accept" and nerr != 0:
            print("FAILED:TST-0048-probe2 want-accept had errors", e)
            return 1

    payload = {
        "probe": "probe2-both-states",
        "unit_id": "TST-0048",
        "pass": True,
        "conforming_pass": both["conforming_pass"],
        "nonconforming_fails": both["nonconforming_fails"],
        "vacuous_suite": both["vacuous_suite"],
        "detector_ok": both["detector_ok"],
        "negatives_fired": len(negatives),
        "naive_deleted_user_owned": both["naive_deleted_user_owned"],
        "nonconforming_failed_rules": both["nonconforming"]["failed"],
    }
    RAW.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "detector_ok=True vacuous=False negatives_fired="
        + str(len(negatives))
        + " naive_deleted="
        + str(len(both["naive_deleted_user_owned"]))
    )
    print("SUCCESS:TST-0048-probe2 both-states and per-rule negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
