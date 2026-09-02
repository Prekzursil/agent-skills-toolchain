#!/usr/bin/env python3
"""Named probe 2: both-states + one negative case per contract rule."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as E  # noqa: E402
import suite as S  # noqa: E402
from contract import RULE_IDS  # noqa: E402

ART = REPO / "command-center/receipts/TST-0051.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:TST-0051-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:TST-0051-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:TST-0051" not in text:
        print("FAILED:TST-0051-probe2 sentinel absent")
        return 1

    states = S.both_states()
    if not states["conforming_all_pass"]:
        print("FAILED:TST-0051-probe2 conforming fixture did not pass")
        print(json.dumps(states["conforming"], indent=2)[:2000])
        return 1
    if not states["negative_case_per_rule"]:
        print("FAILED:TST-0051-probe2 missing per-rule negative")
        print(json.dumps(states["mutants"], indent=2)[:4000])
        return 1
    if not states["both_states_holds"]:
        print("FAILED:TST-0051-probe2 both-states does not hold")
        return 1
    for rid in RULE_IDS:
        m = states["mutants"][rid]
        if not m["fired_on_mutant"]:
            print(f"FAILED:TST-0051-probe2 {rid} mutant did not fire")
            return 1
        print(f"{rid} fired_on_mutant=True negative={m['negative_case']}")

    ctrl = doc.get("both_states_control") or {}
    if ctrl.get("both_states_holds") is not True:
        print("FAILED:TST-0051-probe2 receipt both_states_holds not true")
        return 1
    if ctrl.get("negative_case_per_rule") is not True:
        print("FAILED:TST-0051-probe2 receipt negative_case_per_rule not true")
        return 1
    rec_mut = ctrl.get("mutants") or {}
    for rid in RULE_IDS:
        if not (rec_mut.get(rid) or {}).get("fired_on_mutant"):
            print(f"FAILED:TST-0051-probe2 receipt mutant {rid} not recorded")
            return 1

    conf = E.live_snapshot(HERE / "fixtures" / "conforming", include_canonical=False)
    non = E.live_snapshot(HERE / "fixtures" / "nonconforming", include_canonical=False)
    conf_d = E.set_difference(conf)
    non_d = E.set_difference(non)
    if not conf_d["sets_equal"]:
        print("FAILED:TST-0051-probe2 conforming extract not equal", conf_d)
        return 1
    if non_d["sets_equal"]:
        print("FAILED:TST-0051-probe2 nonconforming extract equal")
        return 1
    fx = ctrl.get("fixture_extract") or {}
    if fx.get("conforming_sets_equal") is not True:
        print("FAILED:TST-0051-probe2 receipt conforming extract flag")
        return 1
    if fx.get("nonconforming_sets_equal") is not False:
        print("FAILED:TST-0051-probe2 receipt nonconforming extract flag")
        return 1

    print(
        "conforming_all_pass=True negative_per_rule=True "
        f"conf_extract_equal={conf_d['sets_equal']} "
        f"non_policy_minus={non_d['policy_minus_tooling']} "
        f"non_tooling_minus={non_d['tooling_minus_policy']}"
    )
    print("SUCCESS:TST-0051-probe2 both-states per-rule negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
