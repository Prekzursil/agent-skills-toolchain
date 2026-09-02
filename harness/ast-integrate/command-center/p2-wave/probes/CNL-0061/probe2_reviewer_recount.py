#!/usr/bin/env python3
"""Probe 2: independent recount + later-no-harm both-states.

Reviewer re-tabulates the JSON fixtures with irv_reviewer (mutating queues),
not by reading the author's argument. A winner disagreement blocks the unit.

Later-no-harm: SILENT on IRV (pathology does not occur). FIRES on the planted
second-place-plurality bait, proving the checker is not vacuous.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import irv_author as A  # noqa: E402
import irv_reviewer as R  # noqa: E402
import pathology as P  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0061-ranked-choice-tabulation-and-its-known-pathologies.md"
)
OUT = HERE / "probe2-reviewer-recount.raw.json"
REVIEWER_SRC = (HERE / "irv_reviewer.py").read_text(encoding="utf-8")


def _pair(name0: str, name1: str, raised: str) -> dict:
    a0 = F.load_named(name0)
    a1 = F.load_named(name1)
    author = P.nonmonotonicity_check(
        A.tabulate, a0["options"], F.as_ballots(a0), F.as_ballots(a1), raised
    )
    review = P.nonmonotonicity_check(
        R.recount, a0["options"], F.as_ballots(a0), F.as_ballots(a1), raised
    )
    return {
        "author_before": author["before_winner"],
        "author_after": author["after_winner"],
        "reviewer_before": review["before_winner"],
        "reviewer_after": review["after_winner"],
        "author_fired": author["fired"],
        "reviewer_fired": review["fired"],
        "agree": (
            author["before_winner"] == review["before_winner"]
            and author["after_winner"] == review["after_winner"]
            and author["fired"] == review["fired"]
        ),
    }


def lnh_random_trials(n_trials: int = 400) -> int:
    rng = random.Random(61)
    violations = 0
    for nopt, nv in ((3, 7), (3, 11), (4, 11), (5, 13)):
        opts = [chr(65 + i) for i in range(nopt)]
        from itertools import permutations

        types = list(permutations(opts))
        for _ in range(n_trials // 4):
            ranks = [list(rng.choice(types)) for _ in range(nv)]
            truncated = [(ranks[0][:1], 1.0)] + [(r, 1.0) for r in ranks[1:]]
            completed = [(ranks[0], 1.0)] + [(r, 1.0) for r in ranks[1:]]
            chk = P.later_no_harm_check(
                R.recount, opts, truncated, completed, ranks[0][0]
            )
            if chk["fired"]:
                violations += 1
    return violations


def main() -> int:
    F.write_fixture_files()
    if re.search(r"^\s*(import irv_author|from irv_author\b)", REVIEWER_SRC, re.M):
        print("FAILED:CNL-0061-probe2 reviewer imports author tabulator")
        return 1

    nm3 = _pair("nm-7x3-original", "nm-7x3-raised", "C")
    maj = _pair("majority-7-original", "majority-7-raised", "A")
    nm4 = _pair("nm-7x4-original", "nm-7x4-raised", "D")

    tr = F.load_named("lnh-irv-truncated")
    co = F.load_named("lnh-irv-completed")
    lnh_irv = P.later_no_harm_check(
        R.recount,
        tr["options"],
        F.as_ballots(tr),
        F.as_ballots(co),
        tr["first_choice"],
    )
    lnh_irv_author = P.later_no_harm_check(
        A.tabulate,
        tr["options"],
        F.as_ballots(tr),
        F.as_ballots(co),
        tr["first_choice"],
    )
    bt = F.load_named("lnh-bait-truncated")
    bc = F.load_named("lnh-bait-completed")
    lnh_bait = P.later_no_harm_check(
        P.second_place_plurality,
        bt["options"],
        F.as_ballots(bt),
        F.as_ballots(bc),
        bt["first_choice"],
    )
    random_viol = lnh_random_trials()

    negative_verbatim = json.dumps(
        {
            "fixture": "lnh-bait-second-place-plurality",
            "fired": lnh_bait["fired"],
            "silent": lnh_bait["silent"],
            "before_winner": lnh_bait["before_winner"],
            "after_winner": lnh_bait["after_winner"],
            "first_choice": lnh_bait["first_choice"],
            "method": "second-place-plurality",
        },
        sort_keys=True,
    )
    irv_lnh_verbatim = json.dumps(
        {
            "fixture": "lnh-irv-truncated-then-completed",
            "fired": lnh_irv["fired"],
            "silent": lnh_irv["silent"],
            "before_winner": lnh_irv["before_winner"],
            "after_winner": lnh_irv["after_winner"],
            "first_choice": lnh_irv["first_choice"],
            "method": "IRV-COUNCIL-v1-reviewer-queues",
        },
        sort_keys=True,
    )

    ok = (
        nm3["agree"]
        and maj["agree"]
        and nm4["agree"]
        and nm3["reviewer_fired"]
        and nm3["reviewer_before"] == "C"
        and nm3["reviewer_after"] == "B"
        and maj["reviewer_fired"] is False
        and lnh_irv["silent"]
        and lnh_irv_author["silent"]
        and lnh_bait["fired"]
        and lnh_bait["before_winner"] == "A"
        and lnh_bait["after_winner"] == "B"
        and random_viol == 0
    )

    doc = {
        "probe": "probe2-reviewer-recount",
        "unit_id": "CNL-0061",
        "reviewer_independent": True,
        "reviewer_mechanism": "mutating-rank-queues-plus-on-disk-json-fixtures",
        "nm7x3": nm3,
        "majority": maj,
        "nm7x4": nm4,
        "later_no_harm_irv": {
            "fired": lnh_irv["fired"],
            "silent": lnh_irv["silent"],
            "verbatim": irv_lnh_verbatim,
        },
        "later_no_harm_bait": {
            "fired": lnh_bait["fired"],
            "silent": lnh_bait["silent"],
            "verbatim": negative_verbatim,
            "does_on_reject_state": (
                "The LNH check FIRES on second-place-plurality: truncated "
                "winner=A, after completing A>B winner=B. On IRV the same "
                "checker is SILENT."
            ),
        },
        "random_irv_lnh_violations": random_viol,
        "reviewer_reran_control": True,
        "pass": bool(ok),
    }
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        note = json.loads(text)
        if "SUCCESS:CNL-0061" not in text:
            ok = False
            doc["pass"] = False
        recorded = (note.get("pathologies") or {}).get("later_no_harm") or {}
        if recorded.get("occurs_at_roster_3_to_15") is True:
            ok = False
            doc["pass"] = False
            doc["overclaim"] = "artifact claimed later-no-harm occurs under IRV"
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("RECOUNT-NM7X3 " + json.dumps(nm3, sort_keys=True))
    print("RECOUNT-MAJORITY " + json.dumps(maj, sort_keys=True))
    print("LNH-IRV " + irv_lnh_verbatim)
    print("LNH-BAIT-NEGATIVE-CONTROL " + negative_verbatim)
    print("random_irv_lnh_violations=" + str(random_viol))
    if not ok:
        print("FAILED:CNL-0061-probe2 reviewer recount or LNH both-states failed")
        return 1
    print("SUCCESS:CNL-0061-probe2 independent recount and later-no-harm both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
