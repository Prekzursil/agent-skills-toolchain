#!/usr/bin/env python3
"""Emit the CNL-0078 CouncilSpec stopping-example schema from live fixture runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import SPEC_EXPRESSIONS, accepted_unchanged  # noqa: E402
from census import census_completeness_score  # noqa: E402
from evaluate import bound_eval, mixed_unbound  # noqa: E402
from fixtures import FIXTURES, REQUIRED  # noqa: E402
from recount import recount  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0078-executable-stopping-example-unique-ideas-100-and-completen.schema.json"
)
EXPR = "unique_ideas >= 100 AND completeness_score >= 0.90"


def compact(run: dict) -> dict:
    keep = [
        "expression",
        "verdict",
        "fired",
        "naive_and",
        "bound",
        "unique_ideas",
        "completeness_score",
        "completeness_parts",
        "unique_identity",
        "completeness_identity",
        "n_raw",
        "completeness_gamed",
    ]
    return {k: run[k] for k in keep}


def main() -> int:
    runs = {}
    for name, builder in FIXTURES.items():
        ledger = builder()
        bound = bound_eval(ledger, REQUIRED)
        indep = recount(ledger, REQUIRED)
        if indep["unique_ideas"] != bound["unique_ideas"]:
            print(
                f"FAILED:emit recount unique {name}: "
                f"{indep['unique_ideas']} != {bound['unique_ideas']}"
            )
            return 1
        if indep["completeness_score"] != bound["completeness_score"]:
            print(
                f"FAILED:emit recount completeness {name}: "
                f"{indep['completeness_score']} != {bound['completeness_score']}"
            )
            return 1
        rec = compact(bound)
        rec["independent_recount"] = {
            "method": indep["method"],
            "unique_ideas": indep["unique_ideas"],
            "completeness_score": indep["completeness_score"],
        }
        rec["verbatim"] = (
            f"{name}: verdict={bound['verdict']} fired={bound['fired']} "
            f"unique_ideas={bound['unique_ideas']} "
            f"completeness_score={bound['completeness_score']} "
            f"n_raw={bound['n_raw']} bound={bound['bound']}"
        )
        if name == "disagree":
            unbound = mixed_unbound(ledger, REQUIRED)
            rec["mixed_raw_gamed"] = compact(unbound)
            rec["mixed_raw_gamed"]["verbatim"] = (
                f"disagree-mixed: verdict={unbound['verdict']} "
                f"fired={unbound['fired']} naive_and={unbound['naive_and']} "
                f"unique_ideas={unbound['unique_ideas']} "
                f"completeness_score={unbound['completeness_score']}"
            )
        runs[name] = rec

    expected = {
        "fire": ("FIRE", True),
        "silent_incomplete": ("SILENT", False),
        "silent_low_unique": ("SILENT", False),
        "planted_bad": ("SILENT", False),
        "disagree": ("SILENT", False),
    }
    for name, (verdict, fired) in expected.items():
        got = runs[name]
        if got["verdict"] != verdict or got["fired"] is not fired:
            print(f"FAILED:emit {name} expected {verdict}/{fired} got {got['verdict']}/{got['fired']}")
            return 1
    mixed = runs["disagree"]["mixed_raw_gamed"]
    if mixed["verdict"] != "UNBOUND" or mixed["fired"] is not False:
        print(f"FAILED:emit disagree mixed not UNBOUND: {mixed}")
        return 1
    if mixed["naive_and"] is not True:
        print(
            "FAILED:emit disagree mixed naive_and should be True "
            "(conjunction SATISFIABLE under disagreeing identities, refused at bind)"
        )
        return 1

    parse_rows = []
    for line, src in SPEC_EXPRESSIONS:
        info = accepted_unchanged(src)
        if not info["accepted"] or not info["tokens_match"] or not info["src_preserved"]:
            print(f"FAILED:emit parse {line}: {info}")
            return 1
        parse_rows.append(
            {
                "spec_line": f"_USER-PROMPTS.md:{line}",
                "expression": src,
                "accepted_unchanged": True,
                "pretty": info["pretty"],
                "identifiers": info["identifiers"],
            }
        )

    pop = census_completeness_score(REPO)
    if pop["hit_count"] != 0:
        print(f"FAILED:emit unexpected completeness_score producer: {pop['hits']}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fire_v = runs["fire"]["verbatim"]
    silent_v = runs["silent_incomplete"]["verbatim"]
    planted_v = runs["planted_bad"]["verbatim"]
    mixed_v = mixed["verbatim"]

    doc = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": (
            "https://ast-integrate.local/command-center/design/council/"
            "CNL-0078-executable-stopping-example-unique-ideas-100-and-completen.schema.json"
        ),
        "title": "Executable stopping example: unique_ideas >= 100 AND completeness_score >= 0.90",
        "unit_id": "CNL-0078",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0078",
        "completion_sentinel": "SUCCESS:CNL-0078",
        "ts": now,
        "question": (
            "What makes this expression executable end to end - specifically, which "
            "component of completeness_score is not yet defined anywhere, and does the "
            "conjunction ever become satisfiable if the idea counter and the completeness "
            "scorer disagree about what an idea is?"
        ),
        "verbatim_expression": EXPR,
        "spec_anchor": {
            "path": "_USER-PROMPTS.md",
            "lines": "10937-10942",
            "cited_line": 10937,
            "quoted": EXPR,
            "six_examples": parse_rows,
        },
        "answer": {
            "undefined_component": "coverage_domain_identity",
            "undefined_component_detail": pop["undefined_component_reason"],
            "live_census": pop,
            "executable_because": (
                "A10 grammar accepts the spec string unchanged; unique_ideas is the "
                "canonical-mechanism cluster count (Jaccard is a corroborating second "
                "signal, never a merge against a different mechanism); completeness_score "
                "is min(subquestion coverage, category coverage, evidence-class coverage) "
                "unioned over those same clusters; the AND fires only when both metrics "
                "share IDENTITY_CANONICAL."
            ),
            "conjunction_if_identities_disagree": (
                "Yes, the naive conjunction CAN be true: on the disagree fixture, raw-row "
                "unique_ideas=100 and gamed-tag completeness_score=1.0 so naive_and=true. "
                "That fire is invalid. The bound evaluator returns UNBOUND (does not FIRE) "
                "whenever unique_ideas and completeness_score were not computed under the "
                "same canonical-mechanism identity. Disagreement is therefore never a "
                "satisfied stop."
            ),
            "residual_unknown": (
                "Human-label calibration of completeness_score (TST-0282 kappa) is not "
                "defined on this worktree and is NOT used as a gate. Operational coverage "
                "is the executable definition for this example."
            ),
        },
        "bindings": {
            "unique_ideas": {
                "identity": "canonical-mechanism-v1",
                "signals": [
                    "mechanism key (params excluded so one-parameter forks collapse)",
                    "token Jaccard corroboration at 0.72 (rename/paraphrase; silent on full rewrite)",
                ],
                "threshold": 100,
            },
            "completeness_score": {
                "identity": "canonical-mechanism-v1",
                "formula": "min(subquestions_hit/declared, categories_hit/required, evidence_classes_hit/required)",
                "threshold": 0.90,
                "missing_before_this_unit": "coverage_domain_identity",
            },
            "bind_rule": (
                "FIRE only if unique_identity == completeness_identity == canonical-mechanism-v1 "
                "and both identity hashes match; otherwise UNBOUND/SILENT."
            ),
        },
        "type": "object",
        "required": ["stopping_expr", "bindings", "identity"],
        "additionalProperties": False,
        "properties": {
            "stopping_expr": {"type": "string", "const": EXPR},
            "identity": {"type": "string", "const": "canonical-mechanism-v1"},
            "bindings": {"type": "object"},
        },
        "$defs": {
            "stopping_expr": {
                "type": "string",
                "description": "A10 grammar source; must parse unchanged.",
                "const": EXPR,
            }
        },
        "fixture_runs": runs,
        "evidence": [
            {
                "kind": "spec-quote",
                "path": "_USER-PROMPTS.md",
                "line": 10937,
                "snippet": EXPR,
            },
            {
                "kind": "fixture-run",
                "name": "fire",
                "verbatim": fire_v,
            },
            {
                "kind": "fixture-run",
                "name": "silent_incomplete",
                "verbatim": silent_v,
            },
            {
                "kind": "negative-control",
                "name": "planted_bad",
                "verbatim": planted_v,
                "rejects": (
                    "On the planted-bad ledger of 8 mechanisms × 13 wording variants "
                    "(104 raw rows) with categories restricted to C0–C1, the bound "
                    "evaluator collapses unique_ideas to 8 and completeness_score to "
                    "0.20, so the expression stays SILENT. The check is meant to reject "
                    "quota-filling by trivial variants; a raw-row counter would report "
                    "unique_ideas=104. Observed: SILENT."
                ),
            },
            {
                "kind": "identity-disagree",
                "name": "disagree-mixed",
                "verbatim": mixed_v,
            },
        ],
        "tests": [
            {
                "id": "T-FIRE-SILENT",
                "name": "Expression FIRE on true fixture, SILENT on false",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0078/probe1_fire_silent.py"
                ),
            },
            {
                "id": "T-A10-PARSE-RECOUNT",
                "name": "A10 parse unchanged + independent mechanism recount",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/CNL-0078/probe2_parse_recount.py"
                ),
            },
        ],
        "negative_control": {
            "id": "CNL0078-C1",
            "state_meant_to_reject": (
                "100-idea quota filled with wording variants of 8 mechanisms"
            ),
            "what_the_check_does": runs["planted_bad"]["verbatim"],
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "note": (
                "fired_on_bad_state means the detector *activates as a reject*: "
                "verdict=SILENT on planted-bad. silent_on_good_state means FIRE "
                "is reserved for the genuine 100-distinct complete ledger."
            ),
        },
        "reviewer": {
            "reviewer_id": "CNL-0078-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "groupby-mechanism-field-only, no Jaccard, no author's cluster helper; "
                "a disagreement in unique_ideas or completeness_score blocks the unit."
            ),
        },
        "dependencies_noted": {
            "CNL-0051": "semantic unique-idea identity (mechanism + corroborating Jaccard)",
            "CNL-0054": "category coverage as one completeness leg",
            "CNL-0076": "end-of-round, side-effect-free evaluation of the stopping expression",
            "CNL-0010": "A10 grammar implemented locally because CNL-0010 artifact is absent",
        },
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} fire={runs['fire']['verdict']} planted={runs['planted_bad']['verdict']}")
    print("SUCCESS:CNL-0078 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
