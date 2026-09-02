#!/usr/bin/env python3
"""Probe 2: control — at least one class where reimplementation is the only route.

Catalog tests_required[1]. Trademarked-method handling must be stated.
Mutants: clear only-route flags, or drop trademark handling, must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from schema_check import check_document  # noqa: E402

ART = REPO / "command-center/research/RES-0122.json"
SENTINEL = (
    "SUCCESS:RES-0122 in the receipt AND a per-class obligation table "
    "with clause citations and the trademarked-method handling stated"
)


def control_ok(doc: dict) -> tuple[bool, str]:
    errors = check_document(doc)
    if errors:
        return False, "schema:" + errors[0]
    table = doc.get("obligation_table") or []
    flagged = [
        r.get("class_id")
        for r in table
        if isinstance(r, dict) and r.get("reimplementation_is_only_permitted_route") is True
    ]
    control = doc.get("control") or {}
    listed = list(control.get("classes_where_reimplementation_is_only_permitted_route") or [])
    if not flagged:
        return False, "no class flagged only-permitted-route"
    if set(flagged) != set(listed):
        return False, f"table {flagged} != control {listed}"
    if "CC-BY-ND" not in flagged:
        return False, "CC-BY-ND not flagged"
    if "trademarked-method" not in flagged:
        return False, "trademarked-method not flagged"
    forbid_ideas = [
        r.get("class_id")
        for r in table
        if isinstance(r, dict) and r.get("forbids_reimplementation_of_unprotected_ideas") is True
    ]
    if forbid_ideas:
        return False, f"overclaim: classes forbid idea-reimplementation {forbid_ideas}"
    if list(control.get("classes_that_forbid_reimplementation_of_unprotected_ideas") or []) != []:
        return False, "control forbid list not empty"
    tm = doc.get("trademarked_method_handling") or {}
    if tm.get("stated") is not True:
        return False, "trademarked handling not stated"
    if tm.get("do_not_name_the_feature") is not True:
        return False, "do_not_name_the_feature missing"
    if tm.get("implement_the_generic_mechanism") is not True:
        return False, "implement_the_generic_mechanism missing"
    rule = str(tm.get("rule") or "").lower()
    if "generic mechanism" not in rule or "not name" not in rule.replace("don't", "do not"):
        if "do not name" not in rule and "not name the feature" not in rule:
            return False, "trademark rule text missing handling"
    return True, f"only_route={flagged}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0122-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0122-probe2 sentinel absent")
        return 1
    doc = json.loads(text)
    ok, why = control_ok(doc)
    print(f"control_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0122-probe2", why)
        return 1

    mutant = copy.deepcopy(doc)
    for row in mutant["obligation_table"]:
        row["reimplementation_is_only_permitted_route"] = False
    mutant["control"]["classes_where_reimplementation_is_only_permitted_route"] = []
    mok, mwhy = control_ok(mutant)
    print(f"mutant_clear_flags_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0122-probe2 empty only-route was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    mutant2["trademarked_method_handling"] = {"stated": False}
    m2ok, m2why = control_ok(mutant2)
    print(f"mutant_drop_trademark_ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:RES-0122-probe2 missing trademark handling was accepted")
        return 1

    print("SUCCESS:RES-0122-probe2 reimplementation-only control trademark handling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
