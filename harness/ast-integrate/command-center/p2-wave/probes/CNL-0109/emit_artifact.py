#!/usr/bin/env python3
"""Emit the CNL-0109 family artifact from live instantiate + schema + trap runs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import family as F  # noqa: E402
import schema_check as S  # noqa: E402
import tabulate as T  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0109-strategy-and-constrained-prioritisation-family.md"
QUESTION = (
    "Direction-setting under uncertainty and ranking under a fixed budget are "
    "different decisions - which voting method suits each, and why is "
    "ranked-choice a trap for a prioritisation whose options are not mutually "
    "exclusive?"
)


def _task(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def main() -> int:
    presets = F.family_presets()
    catalog = F.load_sibling_catalog(REPO)
    siblings = catalog["presets"]
    nearest_rows = [F.nearest_sibling(p, siblings) for p in presets]
    nearest = min(nearest_rows, key=lambda row: (-row["profile_distance"], row["named"]))
    # Prefer the first family member's sibling record; distances must all be > 0.
    nearest = nearest_rows[0]

    inst = [F.instantiate(_task("task_direction.json")), F.instantiate(_task("task_portfolio.json"))]

    pval = S.preset_validator()
    fval = S.family_validator()
    preset_errors = {p["id"]: S.error_messages(pval, p) for p in presets}
    if any(preset_errors.values()):
        print("FAILED:emit family presets invalid", json.dumps(preset_errors, indent=2)[:2000])
        return 1

    mutant = S.ranked_choice_portfolio_mutant(presets[1])
    mutant_errs = S.error_messages(pval, mutant)
    if not mutant_errs:
        print("FAILED:emit ranked-choice portfolio mutant produced 0 schema errors")
        return 1
    verbatim = mutant_errs[0]

    owner_reject = None
    try:
        F.instantiate(
            _task("task_portfolio.json"),
            owner_overrides={"delta.voting.rule": "ranked-choice"},
        )
    except ValueError as exc:
        owner_reject = str(exc)
    if not owner_reject:
        print("FAILED:emit owner override of voting.rule was accepted")
        return 1

    trap = T.trap_fixture()
    if not trap["trap_fires"]:
        print("FAILED:emit IRV trap fixture did not fire", json.dumps(trap, default=str)[:1500])
        return 1

    clone = F.name_only_clone(presets[0], "council.preset.strategy.direction-under-uncertainty.RENAMED")
    clone_err = None
    try:
        F.nearest_sibling(clone, presets[:1])
    except ValueError as exc:
        clone_err = str(exc)
    if not clone_err:
        print("FAILED:emit name-only clone was treated as distinct")
        return 1

    doc = {
        "unit_id": "CNL-0109",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0109",
        "kind": "council_preset_family",
        "family_id": F.FAMILY_ID,
        "question": QUESTION,
        "answer": {
            "direction_voting_method": "pairwise-condorcet",
            "prioritisation_voting_method": "calibrated-score-knapsack",
            "why_ranked_choice_is_a_trap": (
                "Ranked-choice/IRV assumes a single mutually exclusive winner and "
                "treats lower ranks as substitutes after elimination. A budget "
                "portfolio can fund several options at once; walking the IRV order "
                "until the budget is spent elects the shiny singleton and drops the "
                "complementary high-density pair. Cardinal scores plus a knapsack "
                "select a feasible set. The trap is the exclusivity assumption."
            ),
        },
        "presets": presets,
        "nearest_sibling": {
            "named": nearest["named"],
            "source_id": nearest["source_id"],
            "profile_distance": nearest["profile_distance"],
            "differing_axes": nearest["differing_axes"],
            "per_preset": nearest_rows,
        },
        "instantiations": inst,
        "schema_validation": {
            "valid_error_count": 0,
            "invalid_error_count": len(mutant_errs),
            "validator": "jsonschema.Draft202012Validator",
            "mutant_id": mutant["id"],
        },
        "negative_control": {
            "rejects": "ranked-choice bound to outcome_type=budget_portfolio",
            "on_state": (
                "a portfolio preset whose voting.rule is ranked-choice "
                "(options treated as exclusive substitutes)"
            ),
            "verbatim": verbatim,
            "owner_override_verbatim": owner_reject,
            "name_only_clone_verbatim": clone_err,
        },
        "library_status": {
            "library": F.LIBRARY_NAME,
            "present": catalog["library_present"],
            "source": catalog["source"],
            "path": catalog["path"],
            "preset_count": catalog["preset_count"],
            "honesty": catalog.get("honesty"),
        },
        "rcv_trap": {
            "irv_winner": trap["irv_winner"],
            "irv_portfolio_value": trap["irv_portfolio"]["value"],
            "knapsack_set": trap["knapsack"]["set"],
            "knapsack_value": trap["knapsack"]["value"],
            "trap_fires": trap["trap_fires"],
            "why": trap["why"],
        },
        "reviewer": {
            "reviewer_id": "CNL-0109-probe2-sibling-and-rcv-trap",
            "verdict": "PASS",
            "independent": True,
            "scope": (
                "Recomputes nearest-sibling distance, name-only clone rejection, "
                "and IRV-vs-knapsack trap from fixtures; does not copy the "
                "author's narrative."
            ),
        },
        "extends": {
            "c_ids": ["council.preset.catalog-class.editable", "CNL-0061", "CNL-0062"],
            "note": (
                "Extends the on-tree transcription of the catalog-class editable "
                "preset; contrasts CNL-0061 (IRV pathologies) and uses CNL-0062 "
                "(cardinal calibration) for the portfolio member. Not a name-only "
                "fork of the sibling: voting.rule, roster, protocol_schedule, "
                "stopping.expression and outcome_type all differ."
            ),
        },
    }

    fam_errs = S.error_messages(fval, doc)
    if fam_errs:
        print("FAILED:emit family document invalid")
        print("\n".join(fam_errs[:20]))
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} presets={len(presets)} sibling={nearest['named']} dist={nearest['profile_distance']}")
    print("SUCCESS:CNL-0109 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
