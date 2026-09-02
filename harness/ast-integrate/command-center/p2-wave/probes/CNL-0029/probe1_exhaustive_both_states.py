#!/usr/bin/env python3
"""Probe 1: exhaustive matrix, both-states, negative control, ladder miss.

Re-runs the solver over every ordered pair and the planted fixtures.
Does not treat the design note's counts as the source of truth until they
match the live scan.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import ladder as L  # noqa: E402
import solver as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0029-incompatible-role-and-conflict-of-interest-checker-as-a-co.md"
)


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNL-0029-probe1 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0029-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0029" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNL-0029-probe1 sentinel absent")
        return 1

    lib = S.load_library()
    live = S.enumerate_ordered_pairs(lib)
    matrix = doc.get("matrix") or {}
    if int(matrix.get("incompatible_ordered") or -1) != live["incompatible_ordered"]:
        print("FAILED:CNL-0029-probe1 incompatible_ordered mismatch")
        return 1
    if int(matrix.get("compatible_ordered") or -1) != live["compatible_ordered"]:
        print("FAILED:CNL-0029-probe1 compatible_ordered mismatch")
        return 1
    if list(matrix.get("incompatible_unordered") or []) != live["incompatible_unordered"]:
        print("FAILED:CNL-0029-probe1 unordered mismatch")
        return 1
    cells = matrix.get("cells") or []
    if len(cells) != live["ordered_pair_count"]:
        print(f"FAILED:CNL-0029-probe1 cell count {len(cells)} != {live['ordered_pair_count']}")
        return 1
    live_map = {(r["a"], r["b"]): r for r in live["rows"]}
    for cell in cells:
        key = (cell.get("a"), cell.get("b"))
        if key not in live_map:
            print(f"FAILED:CNL-0029-probe1 extra cell {key}")
            return 1
        if bool(cell.get("incompatible")) != bool(live_map[key]["incompatible"]):
            print(f"FAILED:CNL-0029-probe1 cell {key} verdict mismatch")
            return 1
        if bool(cell.get("incompatible")) != (key in {(r["a"], r["b"]) for r in live["rows"] if r["incompatible"]}):
            print(f"FAILED:CNL-0029-probe1 cell {key} inconsistent")
            return 1

    if int((doc.get("family") or {}).get("counted_n") or -1) != live["template_count"]:
        print("FAILED:CNL-0029-probe1 family.counted_n mismatch")
        return 1
    if int((doc.get("family") or {}).get("expected_n") or -1) != live["template_count"]:
        print("FAILED:CNL-0029-probe1 family.expected_n mismatch")
        return 1
    if len(doc.get("verdicts") or []) != live["template_count"]:
        print("FAILED:CNL-0029-probe1 verdicts length mismatch")
        return 1
    for row in doc.get("verdicts") or []:
        if row.get("verdict") != "EXECUTABLE":
            print(f"FAILED:CNL-0029-probe1 template {row.get('record_id')} not EXECUTABLE")
            return 1
    misses = L.missed_by_ladder(live["incompatible_unordered"], live["names"])
    if sorted(matrix.get("ladder_misses") or []) != misses:
        print("FAILED:CNL-0029-probe1 ladder_misses mismatch")
        return 1
    if "judge+synthesiser" not in misses:
        print(f"FAILED:CNL-0029-probe1 synthesiser pair not in ladder misses: {misses}")
        return 1
    if L.ladder_incompatible("scribe", "grader"):
        print("FAILED:CNL-0029-probe1 ladder knows custom names")
        return 1

    rosters = S.load_rosters()
    bad = S.check_roster(rosters["planted_bad_self_review"], lib)
    good = S.check_roster(rosters["known_good_pcj"], lib)
    print(f"planted_bad fired={bad['fired']} silent={bad['silent']} violations={json.dumps(bad['violations'], sort_keys=True)}")
    print(f"known_good fired={good['fired']} silent={good['silent']} violations={json.dumps(good['violations'], sort_keys=True)}")
    if not bad["fired"] or bad["silent"]:
        print("FAILED:CNL-0029-probe1 planted-bad did not fire")
        return 1
    if good["fired"] or not good["silent"]:
        print("FAILED:CNL-0029-probe1 known-good was not silent")
        return 1
    if bad["violations"][0].get("constraint") != S.STRUCTURAL:
        print("FAILED:CNL-0029-probe1 planted-bad wrong constraint")
        return 1
    if bad["violations"][0].get("kind") != "proposal":
        print("FAILED:CNL-0029-probe1 planted-bad kind not proposal")
        return 1

    nc = doc.get("negative_control") or {}
    live_verbatim = json.dumps(bad, sort_keys=True)
    if nc.get("verbatim") != live_verbatim:
        print("FAILED:CNL-0029-probe1 negative_control verbatim mismatch")
        return 1
    if nc.get("fired") is not True:
        print("FAILED:CNL-0029-probe1 negative_control.fired is not True")
        return 1

    custom = S.check_roster(rosters["custom_scribe_grader"], lib)
    if not custom["fired"]:
        print("FAILED:CNL-0029-probe1 scribe+grader not rejected")
        return 1
    coi_bad = S.check_roster(rosters["planted_bad_coi"], lib)
    coi_good = S.check_roster(rosters["known_good_coi_disclosed_author"], lib)
    undecl = S.check_roster(rosters["planted_bad_undeclared_field"], lib)
    mystery = S.check_roster(rosters["custom_mystery_no_caps"], lib)
    if not coi_bad["fired"] or not coi_good["silent"]:
        print("FAILED:CNL-0029-probe1 COI both-states failed")
        return 1
    if not undecl["fired"] or undecl["violations"][0]["constraint"] != S.MISSING_INTERESTS:
        print("FAILED:CNL-0029-probe1 undeclared-field control failed")
        return 1
    if not mystery["fired"] or mystery["violations"][0]["constraint"] != S.MISSING_CAPS:
        print("FAILED:CNL-0029-probe1 mystery-role control failed")
        return 1

    print(
        f"exhaustive templates={live['template_count']} ordered={live['ordered_pair_count']} "
        f"incompatible={live['incompatible_ordered']} compatible={live['compatible_ordered']} "
        f"ladder_misses={len(misses)}"
    )
    print("SUCCESS:CNL-0029-probe1 exhaustive matrix both-states negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
