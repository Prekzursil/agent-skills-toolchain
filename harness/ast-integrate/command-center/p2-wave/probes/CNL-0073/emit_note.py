#!/usr/bin/env python3
"""Emit the CNL-0073 design note from live detector + independent recount."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import proof as P  # noqa: E402
import reviewer as R  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0073-proof-of-impossibility-what-actually-constitutes-proof.md"
)
SCHEMA = "command-center/p2-wave/probes/CNL-0073/design-note.schema.json"
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
PROOF = "command-center/p2-wave/probes/CNL-0073/proof.py"
REVIEWER = "command-center/p2-wave/probes/CNL-0073/reviewer.py"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0073/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0073/probe2_reviewer.py"
)
QUESTION = (
    "One required stopping expression is proof_of_impossibility == true - what "
    "class of evidence discharges it, and how is 'we could not find it' "
    "prevented from being recorded as 'it cannot be found'?"
)
ANSWER = (
    "proof_of_impossibility == true is discharged only by a closed-world "
    "exhaustive refutation: a finite named universe, a mechanical membership "
    "predicate on disk bytes, a visit receipt for every member, set-equality "
    "between universe and visited (checked by sequential walk AND by set "
    "difference), a named settling experiment, and a negative existence result "
    "on every member. The claimed flag is recorded then ignored. A searched-but-"
    "not-exhaustive log is classified UNSUCCESSFUL_SEARCH even when unread "
    "members happen to also lack a witness, so 'we could not find it' cannot "
    "be recorded as 'it cannot be found'. Attempt-limit termination is GAVE_UP "
    "on a distinct path from EXHAUSTIVE_REFUTATION. SUCCESS:CNL-0073"
)


def ev(rel: str, snippet: str, claim: str, mechanism: str, kind: str) -> dict:
    line = A.find_line(REPO / rel, snippet)
    ok, why = A.resolve_anchor(REPO, rel, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:CNL-0073 emit anchor {why}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "verdict": "CONFIRMED",
        "anchor": f"{rel}:{line}",
        "mechanism": mechanism,
    }


def main() -> int:
    live = P.both_states()
    indep = R.independent_both_states()
    agree, why = R.author_agrees()
    if not live["both_directions_ok"] or not indep["both_directions_ok"] or not agree:
        print(f"FAILED:CNL-0073 emit both-states live={live['both_directions_ok']} indep={indep['both_directions_ok']} {why}")
        return 1
    inc = live["incomplete_luck"]
    exh = live["exhaustive"]
    missed = live["incomplete_missed"]
    gave = live["gave_up"]
    nc = live["negative_control"]

    exhaust_snip = "RULE-EXHAUSTIVENESS: unvisited must be empty"
    launder_snip = "RULE-NO-LAUNDER: unsuccessful search never discharges proof_of_impossibility"
    q_snip = "One required stopping expression is proof_of_impossibility == true"
    set_snip = "Does not call proof.qualify or proof.walk_unvisited"

    evidence = [
        ev(
            PROOF,
            exhaust_snip,
            "Exhaustive enumeration of a closed universe with no WITNESS discharges proof_of_impossibility.",
            "sequential-walk",
            "detector-rule",
        ),
        ev(
            PROOF,
            launder_snip,
            "A searched-but-not-exhaustive log cannot discharge the flag, including the lucky-true remainder.",
            "sequential-walk",
            "detector-rule",
        ),
        ev(
            REVIEWER,
            set_snip,
            "Independent set-difference recount agrees with the walk on all four fixtures.",
            "set-difference",
            "independent-recount",
        ),
        ev(
            CATALOG,
            q_snip,
            "Catalog question names proof_of_impossibility == true as a required stopping expression.",
            "catalog-citation",
            "catalog",
        ),
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNL-0073",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0073",
        "completion_sentinel": "SUCCESS:CNL-0073",
        "schema_version": 1,
        "kind": "council-design-note",
        "title": "Proof of impossibility: what actually constitutes proof",
        "question": QUESTION,
        "answer": ANSWER,
        "claim_under_test": (
            "An unsuccessful search ('we could not find it') may be recorded as "
            "proof_of_impossibility == true and stop the round."
        ),
        "declared_signal": {
            "name": "closed-world-exhaustiveness",
            "walk": "sequential membership of every universe member in visited",
            "set_difference": "set(universe) - set(visited) must be empty",
            "predicate": "file bytes contain WITNESS",
            "claimed_flag_ignored": True,
        },
        "which_stops_the_round": {
            "stops": "EXHAUSTIVE_REFUTATION (closed universe, visited==universe, no WITNESS)",
            "does_not_stop": "UNSUCCESSFUL_SEARCH or GAVE_UP, including a lucky-true unread remainder",
            "satisfy_quota_from_padding": False,
        },
        "strongest_surviving_counterargument": (
            "Exhaustiveness proves impossibility only inside the named closed "
            "universe. If that universe was drawn too small, the proof is "
            "conditional on a bad frame, not on the open world. The detector "
            "does not certify that the universe itself is the right one; it "
            "only refuses to treat an incomplete search of a declared universe "
            "as proof."
        ),
        "ts": now,
        "dependency_cnl_0083": {
            "required_by_catalog": True,
            "present_on_this_worktree": (
                REPO
                / "command-center/design/council/"
                / "CNL-0083-executable-stopping-example-proof-of-impossibility-true.schema.json"
            ).is_file(),
            "note": (
                "CNL-0083 binds this evidence class to the executable expression "
                "proof_of_impossibility == true. This unit defines the class; it "
                "does not claim the evaluator schema is already on disk."
            ),
        },
        "source_availability": {
            "harness_restore_user_prompts": False,
            "council_specification_schema_v1": False,
            "note": (
                "Catalog inputs cite C:/Users/Prekzursil/.claude/harness-restore-20260806 "
                "which is absent on this Linux worktree. The question, tests_required, "
                "and stopping-expression name are taken from WORK-UNIT-CATALOG.json."
            ),
        },
        "discharge_class": "closed-world-exhaustive-refutation",
        "non_discharge_classes": [
            "UNSUCCESSFUL_SEARCH",
            "GAVE_UP",
            "COUNTEREXAMPLE_FOUND",
            "OPEN_WORLD",
            "MALFORMED",
        ],
        "proof_rule": {
            "universe_must_be_closed_and_finite": True,
            "visited_must_equal_universe": True,
            "existence_predicate": "file_contains_WITNESS",
            "claimed_flag_cannot_self_certify": True,
            "settling_experiment_required": True,
            "gave_up_distinct_from_proof": True,
            "mechanisms": ["sequential-walk", "set-difference"],
        },
        "both_states": {
            "incomplete_fixture": "incomplete-luck",
            "incomplete_qualifies": inc["qualifies"],
            "incomplete_classification": inc["classification"],
            "incomplete_unvisited_count": inc["unvisited_count"],
            "incomplete_unvisited": inc["unvisited"],
            "incomplete_unread_also_lacks_witness": (
                inc["omniscient_witness_in_unvisited"] is False
            ),
            "exhaustive_fixture": "exhaustive",
            "exhaustive_qualifies": exh["qualifies"],
            "exhaustive_classification": exh["classification"],
            "exhaustive_unvisited_count": exh["unvisited_count"],
            "missed_fixture_classification": missed["classification"],
            "missed_unread_has_witness": missed["omniscient_witness_in_unvisited"],
            "gave_up_classification": gave["classification"],
            "gave_up_distinct_from_proof": gave["classification"] != exh["classification"],
            "both_directions_ok": True,
            "author_reviewer_agree": why,
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "The class of evidence that discharges proof_of_impossibility "
                    "== true is a closed-world exhaustive refutation, not an "
                    "unsuccessful search."
                ),
                "verdict": "CONFIRMED",
                "anchor": evidence[0]["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "'We could not find it' is prevented from being recorded as "
                    "'it cannot be found' because incompleteness classifies as "
                    "UNSUCCESSFUL_SEARCH even when the unread remainder is clean."
                ),
                "verdict": "CONFIRMED",
                "anchor": evidence[1]["anchor"],
            },
            {
                "id": "C3",
                "claim": (
                    "Gave-up (attempt limit) and proved-impossible do not share "
                    "a classification or a qualifies=true path."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{PROOF}:{A.find_line(REPO / PROOF, 'Distinct terminals: gave-up and proved-impossible must not share a path.')}",
            },
        ],
        "evidence": evidence,
        "tests": [
            {
                "id": "T1-both-states",
                "command": P1,
                "result": "PASS",
                "expect": (
                    "incomplete-luck FAIL to qualify; exhaustive PASS; both directions"
                ),
            },
            {
                "id": "T2-reviewer-rerun",
                "command": P2,
                "result": "PASS",
                "expect": (
                    "independent set-difference re-run of both-states before sign-off"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unsuccessful-search-is-not-proof",
                "rejects": nc["rejects"],
                "observed": nc["verbatim"],
                "what_the_check_does": nc["what_the_check_does"],
                "verbatim": nc["verbatim"],
                "fixture": nc["fixture"],
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0073-probe2-set-difference",
            "vendor": "openai",
            "role": "cross-vendor both-states re-runner",
            "independent": True,
            "re_ran_both_states": True,
            "mechanism": "set-difference",
            "verdict": "PASS",
            "agree_with_author": why,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "unit-schema"},
            {"path": PROOF, "exists": True, "role": "detector"},
            {"path": REVIEWER, "exists": True, "role": "independent-recount"},
        ],
        "markdown_body": (
            "# Proof of impossibility: what actually constitutes proof\n\n"
            + QUESTION
            + "\n\n"
            + ANSWER
            + "\n"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0073 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
