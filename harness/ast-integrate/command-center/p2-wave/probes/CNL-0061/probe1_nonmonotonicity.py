#!/usr/bin/env python3
"""Probe 1: worked non-monotonicity fixture + majority negative control.

Signal 1 is the author IRV-COUNCIL-v1 round table on NM-7x3 (raising C on one
ballot flips C -> B). Signal 2 is the 3-candidate raise-to-first census at
n=7 (a count, not a citation). Majority-7 must stay silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import irv_author as A  # noqa: E402
import pathology as P  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0061-ranked-choice-tabulation-and-its-known-pathologies.md"
)
OUT = HERE / "probe1-nonmonotonicity.raw.json"
CENSUS_N7_EXPECTED = 6


def main() -> int:
    F.write_fixture_files()
    nm0 = F.load_named("nm-7x3-original")
    nm1 = F.load_named("nm-7x3-raised")
    maj0 = F.load_named("majority-7-original")
    maj1 = F.load_named("majority-7-raised")
    nm4_0 = F.load_named("nm-7x4-original")
    nm4_1 = F.load_named("nm-7x4-raised")
    wt = F.load_named("weighted-double-c")

    nm = P.nonmonotonicity_check(
        A.tabulate,
        nm0["options"],
        F.as_ballots(nm0),
        F.as_ballots(nm1),
        nm0["raised_candidate"],
    )
    silent = P.nonmonotonicity_check(
        A.tabulate,
        maj0["options"],
        F.as_ballots(maj0),
        F.as_ballots(maj1),
        maj0["raised_candidate"],
    )
    nm4 = P.nonmonotonicity_check(
        A.tabulate,
        nm4_0["options"],
        F.as_ballots(nm4_0),
        F.as_ballots(nm4_1),
        nm4_0["raised_candidate"],
    )
    census_n7 = P.census_three_cand_raise_to_first(A.tabulate, 7)
    orig = A.tabulate(nm0["options"], F.as_ballots(nm0))
    w_eq = A.tabulate(wt["options"], F.as_ballots(wt))

    r0 = orig["rounds"][0]
    negative_verbatim = json.dumps(
        {
            "fixture": "majority-7",
            "fired": silent["fired"],
            "silent": silent["silent"],
            "before_winner": silent["before_winner"],
            "after_winner": silent["after_winner"],
            "raised_candidate": silent["raised_candidate"],
        },
        sort_keys=True,
    )

    ok = (
        nm["fired"]
        and nm["before_winner"] == "C"
        and nm["after_winner"] == "B"
        and silent["silent"]
        and silent["before_winner"] == "A"
        and silent["after_winner"] == "A"
        and nm4["fired"]
        and nm4["before_winner"] == "D"
        and nm4["after_winner"] == "B"
        and census_n7 == CENSUS_N7_EXPECTED
        and r0.get("tie_break_used") is True
        and r0.get("last_place") == ["B", "C"]
        and r0.get("eliminated") == "B"
        and w_eq["winner"] == orig["winner"]
    )

    doc = {
        "probe": "probe1-nonmonotonicity",
        "unit_id": "CNL-0061",
        "nm7x3": {
            "fired": nm["fired"],
            "before_winner": nm["before_winner"],
            "after_winner": nm["after_winner"],
            "before_how": nm["before_how"],
            "after_how": nm["after_how"],
            "round0_last_place": r0.get("last_place"),
            "round0_eliminated": r0.get("eliminated"),
            "round0_elim_rule": r0.get("elim_rule"),
            "tie_break_used": r0.get("tie_break_used"),
        },
        "nm7x4": {
            "fired": nm4["fired"],
            "before_winner": nm4["before_winner"],
            "after_winner": nm4["after_winner"],
        },
        "majority_negative_control": {
            "fired": silent["fired"],
            "silent": silent["silent"],
            "before_winner": silent["before_winner"],
            "after_winner": silent["after_winner"],
            "verbatim": negative_verbatim,
            "does_on_reject_state": (
                "On majority-7 the non-monotonicity check is SILENT: raising A "
                "keeps winner=A. The state the check is meant to reject is "
                "NM-7x3, where it FIRES (C -> B)."
            ),
        },
        "census_n7_raise_to_first_hits": census_n7,
        "weighted_double_c_winner": w_eq["winner"],
        "pass": bool(ok),
    }
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        note = json.loads(text)
        doc["artifact_present"] = True
        doc["artifact_state"] = note.get("state")
        if "SUCCESS:CNL-0061" not in text:
            ok = False
            doc["pass"] = False
        if note.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            ok = False
            doc["pass"] = False
        recorded = (
            (note.get("worked_examples") or {}).get("nm7x3") or {}
        )
        if recorded.get("after_winner") not in (None, "B"):
            ok = False
            doc["pass"] = False
    else:
        doc["artifact_present"] = False

    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "nm7x3_fired="
        + str(nm["fired"])
        + " before="
        + str(nm["before_winner"])
        + " after="
        + str(nm["after_winner"])
        + " last_place="
        + ",".join(r0.get("last_place") or [])
        + " elim="
        + str(r0.get("eliminated"))
    )
    print("MAJORITY-NEGATIVE-CONTROL " + negative_verbatim)
    print(
        "nm7x4_fired="
        + str(nm4["fired"])
        + " census_n7="
        + str(census_n7)
        + " weighted_winner="
        + str(w_eq["winner"])
        + " majority_silent="
        + str(silent["silent"])
    )
    if not ok:
        print("FAILED:CNL-0061-probe1 non-monotonicity fixture did not discriminate")
        return 1
    print("SUCCESS:CNL-0061-probe1 non-monotonicity worked example and majority negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
