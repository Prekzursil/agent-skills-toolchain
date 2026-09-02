#!/usr/bin/env python3
"""Named probe 2: flooding control and :11330 known-miss (independent of probe 1).

Does not call scenario.evaluate(). Re-derives:
  1. Concatenating every catalogue description yields measured tokens > budget
     and offer-recall 1.0 on the gold set (both axes live).
  2. The :11330 installed skill is in the suite: flood offers it, budgeted
     trigger-table does not.
  3. Uninstalling that skill removes it from the flood offer set (installed,
     not a ghost label).
  4. Starve injects the empty payload (cost 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from router import (  # noqa: E402
    FALLBACK_ID,
    TOKEN_BUDGET,
    count_tokens,
    inject,
    payload_for,
)

OUT = HERE / "probe2-flood.raw.json"
ART = REPO / "command-center/receipts/TST-0318.json"
MISS_CASE = "case.fc11330-installed-skill"
MISS_SKILL = "skill.deploy-parity-live-tree"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0318-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:TST-0318" not in json.dumps(doc):
        return fail("sentinel absent")

    repertoire = json.loads((HERE / "repertoire.json").read_text(encoding="utf-8"))
    labelled = json.loads((HERE / "labelled_set.json").read_text(encoding="utf-8"))
    caps = list(repertoire["capabilities"])
    cases = list(labelled["cases"])

    miss_case = next(c for c in cases if c["id"] == MISS_CASE)
    if str(miss_case["expected"]) != MISS_SKILL:
        return fail("known-miss gold is not the installed skill")
    if not any(c["id"] == MISS_SKILL for c in caps):
        return fail("known-miss skill not installed in repertoire")

    joined = payload_for(caps)
    measured = count_tokens(joined)
    estimate = sum(int(c.get("token_cost") or 0) for c in caps)
    if measured <= TOKEN_BUDGET:
        return fail(f"flood payload {measured} did not exceed budget {TOKEN_BUDGET}")
    if measured == estimate:
        return fail("measured cost collapsed onto decoy token_cost sum")

    flood_hits = []
    for case in cases:
        pred = inject(str(case["prompt"]), caps, policy="flood")
        if pred["injected_token_cost"] != measured:
            return fail("flood cost was not the concatenated catalogue payload")
        if str(case["expected"]) not in pred["offered_ids"]:
            return fail(f"flood missed gold {case['id']}")
        if pred["budget_ok"]:
            return fail("flood claimed budget_ok")
        flood_hits.append(case["id"])

    starve = inject(cases[0]["prompt"], caps, policy="starve")
    if starve["payload"] != "" or starve["injected_token_cost"] != 0:
        return fail("starve is not the empty payload")
    if starve["offered_ids"]:
        return fail("starve offered capabilities")

    budgeted_miss = inject(str(miss_case["prompt"]), caps, policy="budgeted")
    flood_miss = inject(str(miss_case["prompt"]), caps, policy="flood")
    if MISS_SKILL in budgeted_miss["offered_ids"]:
        return fail("budgeted unexpectedly offered the :11330 skill")
    if MISS_SKILL not in flood_miss["offered_ids"]:
        return fail("flood did not offer the installed :11330 skill")
    if budgeted_miss["injected_token_cost"] > TOKEN_BUDGET:
        return fail("budgeted miss-path exceeded budget")

    # Direct re-measure of a no-match prompt (fallback, not a confident wrong pick).
    weather = next(c for c in cases if c["id"] == "case.weather-none")
    live = inject(weather["prompt"], caps, policy="budgeted")
    if live["top1_id"] != FALLBACK_ID or live["confident"]:
        return fail(f"live weather route {live}")
    if FALLBACK_ID not in live["offered_ids"]:
        return fail("negative did not offer fallback")

    mutant_caps = [c for c in caps if c["id"] != MISS_SKILL]
    mutant = inject(str(miss_case["prompt"]), mutant_caps, policy="flood")
    if MISS_SKILL in mutant["offered_ids"]:
        return fail("uninstall mutation still offered the skill")
    if count_tokens(payload_for(mutant_caps)) >= measured:
        return fail("uninstall did not shrink the flood payload")

    claimed = (doc.get("known_miss") or {})
    if claimed.get("capability_id") != MISS_SKILL:
        return fail("receipt known_miss capability mismatch")
    if claimed.get("budgeted_offered") is not False or claimed.get("flood_offered") is not True:
        return fail("receipt known_miss flags mismatch live")

    flood_ctrl = doc.get("flooding_control") or {}
    if flood_ctrl.get("perfect_recall") is not True:
        return fail("receipt flooding_control.perfect_recall missing")
    if int(flood_ctrl.get("injected_token_cost") or 0) != measured:
        return fail("receipt flooding cost mismatch live concatenation")

    payload = {
        "probe": "probe2-flood-and-known-miss",
        "unit_id": "TST-0318",
        "flood_measured": measured,
        "flood_estimate": estimate,
        "flood_hits": flood_hits,
        "budgeted_miss_offered": False,
        "flood_miss_offered": True,
        "uninstall_dropped": True,
        "computed_not_asserted": True,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "flood_tokens": measured,
                "budget": TOKEN_BUDGET,
                "flood_perfect_recall": True,
                "known_miss_budgeted_offered": False,
                "known_miss_flood_offered": True,
                "uninstall_dropped": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0318-probe2 flooding control and known-miss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
