#!/usr/bin/env python3
"""Probe 2: SC-13 amendment via generic ruling slot; independent encoding review.

Does not special-case condition 13 inside the evaluator. Reviews encodings of
the other 20 against held-out catalog/CC-0024 quotes.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluator as Ev  # noqa: E402
import predicate_table as PT  # noqa: E402

EVALUABLE_IDS = (1, 4, 5, 7, 8, 11, 12, 13, 14, 15, 16, 17, 18, 19)
ABSENT_IDS = (2, 3, 6, 9, 10, 20, 21)

# Held-out phrases from CC-0024 extract and catalog citations — not imported
# from predicate_table.py.
HELD_OUT = {
    1: {
        "confidence": "QUOTED",
        "must_contain": [
            "IMPLEMENTED",
            "SUPERSEDED",
            "REJECTED-WITH-OWNER-REASONING",
        ],
    },
    2: {"confidence": "ABSENT-VERBATIM"},
    3: {"confidence": "ABSENT-VERBATIM"},
    4: {"confidence": "QUOTED", "must_contain": ["no required test is red"]},
    5: {
        "confidence": "QUOTED",
        "must_contain": ["negative control", "observed"],
    },
    6: {"confidence": "ABSENT-VERBATIM"},
    7: {"confidence": "RECONSTRUCTED", "must_contain": ["NOT-CHECKED"]},
    8: {
        "confidence": "QUOTED",
        "must_contain": ["improvement", "regression"],
    },
    9: {"confidence": "ABSENT-VERBATIM"},
    10: {"confidence": "ABSENT-VERBATIM"},
    11: {"confidence": "RECONSTRUCTED", "must_contain": ["scanner"]},
    12: {"confidence": "QUOTED", "must_contain": ["docs and code agree"]},
    14: {"confidence": "QUOTED", "must_contain": ["rollback is tested"]},
    15: {
        "confidence": "QUOTED",
        "must_contain": ["settling experiment", "impact"],
    },
    16: {"confidence": "QUOTED", "must_contain": ["160"]},
    17: {"confidence": "QUOTED", "must_contain": ["96"]},
    18: {"confidence": "QUOTED", "must_contain": ["48"]},
    19: {"confidence": "QUOTED", "must_contain": ["64"]},
    20: {"confidence": "ABSENT-VERBATIM"},
    21: {"confidence": "ABSENT-VERBATIM"},
}

FORBIDDEN_EVALUATOR = (
    r"\b(id|condition_id|cid)\s*==\s*13\b",
    r"\b13\s*==\s*(id|condition_id|cid)\b",
    r"spec_line\s*==\s*11390",
    r"11390\s*==\s*spec_line",
    r"if .*\b13\b.*:",
)


def fail(msg: str) -> int:
    print(f"FAILED:CC-0015-probe2 {msg}")
    return 1


def good_state() -> dict:
    s = Ev.blank_state()
    s["selected_option_ids"] = ["OPT-A", "OPT-B"]
    s["dispositions"] = {
        "OPT-A": "IMPLEMENTED",
        "OPT-B": "SUPERSEDED",
    }
    s["required_tests"] = [{"id": "t1", "status": "green"}]
    s["suites"] = [{"id": "s1", "negative_control_observed_fail": True}]
    s["compatibility_cells"] = [
        {"id": "c1", "mark": "SUPPORTED", "test_run": "run-1"}
    ]
    s["benchmark"] = {"verdict": "IMPROVED", "run_ids": ["r1"]}
    s["vuln_scan_fresh"] = True
    s["license_scan_fresh"] = True
    s["docs_code_agree"] = True
    s["canary_succeeded"] = False
    s["marketplace_release_succeeded"] = False
    s["merged_pr"] = True
    s["receipts"] = {
        "REL-0004": {"state": "SUCCESS"},
        "REL-0005": {"state": "SUCCESS"},
        "REL-0006": {"state": "SUCCESS"},
    }
    s["rulings"] = {"REL-0003": {"recorded": True}}
    s["rollback_tested"] = True
    s["unknowns"] = [
        {
            "id": "U1",
            "settling_experiment": "named-exp",
            "impact": "owner-visible",
        }
    ]
    s["counts"] = {
        "workflow_candidates_classified": 160,
        "blueprints_executable": 96,
        "council_protocols": 48,
        "presets": 64,
    }
    s["protocol_ids"] = [f"P{i}" for i in range(48)]
    s["preset_ids"] = [f"S{i}" for i in range(64)]
    s["release_mode"] = "PR-ONLY"
    s["canary_channel_present"] = False
    return s


def no_ruling_state() -> dict:
    s = good_state()
    s["rulings"] = {}
    s["merged_pr"] = None
    s["receipts"] = {}
    return s


def ruling_missing_receipts_state() -> dict:
    s = good_state()
    s["receipts"] = {}
    return s


def mutate_false(sid: int, state: dict) -> dict:
    s = copy.deepcopy(state)
    if sid == 1:
        s["dispositions"]["OPT-B"] = "OPEN"
    elif sid == 4:
        s["required_tests"][0] = {"id": "t1", "status": "red"}
    elif sid == 5:
        s["suites"][0]["negative_control_observed_fail"] = False
    elif sid == 7:
        s["compatibility_cells"][0] = {
            "id": "c1",
            "mark": "SUPPORTED",
            "test_run": "",
        }
    elif sid == 8:
        s["benchmark"]["verdict"] = "REGRESSED"
    elif sid == 11:
        s["vuln_scan_fresh"] = False
    elif sid == 12:
        s["docs_code_agree"] = False
    elif sid == 13:
        s["merged_pr"] = False
    elif sid == 14:
        s["rollback_tested"] = False
    elif sid == 15:
        s["unknowns"][0]["settling_experiment"] = ""
    elif sid == 16:
        s["counts"]["workflow_candidates_classified"] = 12
    elif sid == 17:
        s["counts"]["blueprints_executable"] = 1
    elif sid == 18:
        s["preset_ids"] = list(s["protocol_ids"])
    elif sid == 19:
        s["counts"]["presets"] = 3
    else:
        raise RuntimeError(f"no mutation for {sid}")
    return s


def row_by_id(result: dict, cid: int) -> dict:
    for row in result["conditions"]:
        if row["id"] == cid:
            return row
    raise KeyError(cid)


def main() -> int:
    src = (HERE / "evaluator.py").read_text(encoding="utf-8")
    for pat in FORBIDDEN_EVALUATOR:
        if re.search(pat, src):
            return fail(f"evaluator-special-case {pat}")
    if "11390" in src:
        return fail("evaluator-mentions-11390")

    table = PT.encodings()
    by_id = {e["id"]: e for e in table}

    # Independent encoding review of the other 20 (not condition 13's live text).
    for cid, held in HELD_OUT.items():
        enc = by_id[cid]
        if enc["text_confidence"] != held["confidence"]:
            return fail(
                f"confidence id={cid} got={enc['text_confidence']} "
                f"want={held['confidence']}"
            )
        text = (enc.get("text") or "").lower()
        for needle in held.get("must_contain") or []:
            if needle.lower() not in text:
                return fail(f"held-out-miss id={cid} needle={needle!r}")
        if not enc.get("settling_probe") or not enc.get("probe_cost"):
            return fail(f"review-incomplete id={cid}")

    sc13 = by_id[13]
    if sc13.get("as_written_satisfiability") != "UNSATISFIABLE-AS-WRITTEN":
        return fail("sc13-as-written-not-flagged")
    if (sc13.get("amendment") or {}).get("ruling_id") != "REL-0003":
        return fail("sc13-amendment-slot")

    r_no = Ev.run(no_ruling_state(), table)
    r_yes = Ev.run(good_state(), table)
    r_miss = Ev.run(ruling_missing_receipts_state(), table)
    n13 = row_by_id(r_no, 13)
    y13 = row_by_id(r_yes, 13)
    m13 = row_by_id(r_miss, 13)

    if n13.get("unsatisfiable_as_written") is not True:
        return fail("sc13-unsat-flag-absent-without-ruling")
    if n13["verdict"] == "TRUE":
        return fail("sc13-as-written-true-under-pr-only")
    if n13.get("amendment_applied") is True:
        return fail("sc13-amendment-applied-without-ruling")

    if y13.get("amendment_applied") is not True:
        return fail("sc13-amendment-not-applied")
    if y13["verdict"] != "TRUE":
        return fail(f"sc13-amended-not-true {y13['verdict']} {y13['evidence_pointer']}")
    if y13.get("unsatisfiable_as_written") is True:
        return fail("sc13-unsat-flag-stuck-after-ruling")
    if "canary" in (y13.get("text") or "").lower() and "rel-0004" not in (
        y13.get("text") or ""
    ).lower():
        return fail("sc13-live-text-still-as-written")

    if m13["verdict"] != "NOT-CHECKED":
        return fail(f"sc13-missing-receipts={m13['verdict']}")
    if m13.get("amendment_applied") is not True:
        return fail("sc13-missing-receipts-should-still-use-amended-spec")

    # Same evaluator, no id branch: every evaluable encoding flips FALSE.
    good = good_state()
    base = Ev.run(good, table)
    for cid in EVALUABLE_IDS:
        row = row_by_id(base, cid)
        if row["verdict"] != "TRUE":
            return fail(
                f"evaluable-not-true id={cid} {row['verdict']} "
                f"{row['evidence_pointer']}"
            )
        mutated = Ev.run(mutate_false(cid, good), table)
        mv = row_by_id(mutated, cid)
        if mv["verdict"] != "FALSE":
            return fail(
                f"mutation-did-not-flip id={cid} {mv['verdict']} "
                f"{mv['evidence_pointer']}"
            )

    for cid in ABSENT_IDS:
        for result in (base, r_no, r_yes):
            v = row_by_id(result, cid)["verdict"]
            if v != "NOT-CHECKED":
                return fail(f"absent-not-nc id={cid} {v}")

    print(
        "sc13_no_ruling "
        f"unsat={n13['unsatisfiable_as_written']} verdict={n13['verdict']} "
        f"amended_true={y13['verdict']} missing_receipts={m13['verdict']} "
        f"evaluable_flipped={len(EVALUABLE_IDS)} absent_nc={len(ABSENT_IDS)}"
    )
    print("SUCCESS:CC-0015-probe2 sc13-amendment and encoding review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
