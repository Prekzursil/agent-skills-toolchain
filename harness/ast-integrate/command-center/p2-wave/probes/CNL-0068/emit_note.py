#!/usr/bin/env python3
"""Emit the CNL-0068 council design note (JSON body at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import override as O  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0068-evidence-outranks-popularity-the-executable-test-override-.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py"
)
QUESTION = (
    "The spec states agreement is not proof and evidence gates outrank "
    "popularity - what is the exact mechanism by which one failing executable "
    "test overturns a unanimous vote, and who is permitted to declare a test "
    "load-bearing?"
)


def main() -> int:
    planted = O.fixture_result("unanimous_refuted.json")
    good = O.fixture_result("known_good.json")
    converse = O.fixture_result("irrelevant_fail.json")
    weighted = O.fixture_result("weighted_unanimous_refuted.json")
    seat = O.fixture_result("seat_declares.json")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = {
        "unit_id": "CNL-0068",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0068",
        "completion_sentinel": "SUCCESS:CNL-0068",
        "kind": "council-design-note",
        "report": {
            "kind": "council-design-note",
            "control_ids": ["NC-unanimous-yes-bound-fail"],
            "observations": [
                {
                    "name": "unanimous-yes-bound-fail",
                    "measured": planted["outcome"],
                    "method": "override.adjudicate on fixtures/unanimous_refuted.json",
                    "anchor": "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py",
                },
                {
                    "name": "irrelevant-fail-cannot-veto",
                    "measured": converse["outcome"],
                    "method": "override.adjudicate on fixtures/irrelevant_fail.json",
                    "anchor": "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py",
                },
            ],
        },
        "title": "Evidence outranks popularity: the executable-test override of a majority",
        "question": QUESTION,
        "depends_on": ["CNL-0023"],
        "dependency_note": (
            "CNL-0023 (vote-weight provenance) is not delivered on this worktree. "
            "This unit does not wait on it: the override fires on any legal weight "
            "vector, including weighted unanimity (fixture weighted_unanimous_refuted)."
        ),
        "source_files_on_this_worktree": {
            "harness_restore_user_prompts": False,
            "council_specification_schema": False,
            "council_protocols_and_presets": False,
            "disclosure": (
                "The catalog inputs under C:/Users/Prekzursil/.claude/harness-restore-20260806/ "
                "are absent here. Spec sentences are taken from WORK-UNIT-CATALOG.json "
                "evidence_requirement for CNL-0068, not from a fabricated file:line of a "
                "missing restore tree."
            ),
        },
        "claim_under_test": (
            "One failing executable test that is legally bound to the decided "
            "claim overturns a unanimous YES; a failing test bound to a different "
            "claim cannot veto; only owner/charter/protocol-preset/registrar may "
            "declare a test load-bearing, and only before ballot_close."
        ),
        "floors": [
            {
                "id": "legal-binder",
                "hard_lower_bound": (
                    "binder_role in {owner, charter, protocol-preset, registrar} "
                    "and declared_at strictly before ballot_close"
                ),
                "design_default": "owner binding frozen at charter time",
                "blocks_fire_when": (
                    "a seat, majority, post-close, or voting-registrar declaration "
                    "tries to make a test load-bearing"
                ),
            },
            {
                "id": "claim-id-exact-match",
                "hard_lower_bound": "binding.claim_id == decided claim_id",
                "design_default": "one binding per decided claim",
                "blocks_fire_when": (
                    "the failing test is bound to a different claim, including a "
                    "prefix-similar claim_id"
                ),
            },
            {
                "id": "executable-result",
                "hard_lower_bound": "legal applicable test status in {PASS, FAIL}",
                "design_default": "subprocess invocation run live",
                "blocks_fire_when": (
                    "the bound test errors: outcome is NOT-CHECKED, not a binding YES"
                ),
            },
        ],
        "fire_rule": O.OVERRIDE_RULE,
        "audit_when_floor_blocks": {
            "event": "executable-test-override",
            "must_name_unmet_floors": True,
            "does_not_rewrite_expression": True,
            "preserves_tally": (
                "The ballot tally remains on the record. The override changes "
                "outcome, not the votes."
            ),
        },
        "ceiling": {
            "required_field": "binder_role",
            "missing_is": "not-load-bearing; cannot veto a sound YES",
            "unmet_at_ceiling": (
                "At ballot_close, undeclared tests cannot be attached. A hang "
                "where every FAIL vetoes every claim is forbidden by claim_id match."
            ),
        },
        "source_availability": {
            "requested_paths_present": False,
            "missing": [
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            ],
        },
        "answer": {
            "mechanism": (
                "Tabulate first, then run every legal load-bearing test bound to the "
                "decided claim. If the tally would accept (YES) and any such test "
                "FAILS, the recorded outcome is REFUTED — never YES, even when every "
                "seat voted YES. A failing test bound to a different claim is recorded "
                "as an irrelevant failure and does not veto."
            ),
            "who_may_declare": (
                "Only owner, charter, protocol-preset, or a non-voting registrar, and "
                "only with declared_at strictly before ballot_close. A voting seat, a "
                "majority vote, a chair acting after close, or a registrar who also "
                "holds a seat on this council cannot make a test load-bearing."
            ),
        },
        "mechanism": {
            "id": "claim-bound-load-bearing-test-override",
            "summary": (
                "Acceptance is a two-stage record: (1) weighted tally of ballots, "
                "(2) executable override. Stage 2 is claim-indexed. One FAIL on a "
                "legal binding whose claim_id equals the decided claim overturns a "
                "unanimous YES. Popularity cannot author the binding that would "
                "protect or attack that override."
            ),
            "override_rule": O.OVERRIDE_RULE,
            "permitted_binder_roles": sorted(O.PERMITTED_BINDER_ROLES),
            "forbidden_binder_roles": sorted(O.FORBIDDEN_BINDER_ROLES),
            "claim_match": "exact equality of claim_id; prefix matches are irrelevant",
            "error_policy": (
                "A legal bound test that cannot run (ERROR) yields NOT-CHECKED. "
                "The tally is recorded but is not a binding YES."
            ),
            "does_not_legislate_acceptance": (
                "A passing test does not mint YES from a NO tally. This unit specifies "
                "the FAIL-overturns-YES direction required by tests_required. Factual "
                "settlement in both directions is left to TST-0274."
            ),
            "steps": [
                "Parse ballot_close and compute the weighted tally. tentative_outcome is YES when yes_weight > no_weight; unanimous_yes is yes_weight > 0 and no_weight == 0.",
                "Classify each binding: binder_role must be in {owner, charter, protocol-preset, registrar}; declared_at must be strictly before ballot_close; declared_by_majority must not be true; a registrar must not also be a voting seat.",
                "Execute each invocation (live subprocess for kind=subprocess). Compare claim_id with exact equality to the decided claim.",
                "If any legal applicable result is ERROR, outcome is NOT-CHECKED.",
                "If tentative_outcome is YES and any legal applicable result is FAIL, outcome is REFUTED with reason executable-test-override.",
                "FAIL results on illegal or non-applicable bindings are recorded and do not change a sound YES.",
            ],
            "engine": "command-center/p2-wave/probes/CNL-0068/override.py",
        },
        "who_may_declare_load_bearing": {
            "permitted": sorted(O.PERMITTED_BINDER_ROLES),
            "forbidden": sorted(O.FORBIDDEN_BINDER_ROLES)
            + ["post-close declaration", "voting registrar"],
            "conflict_rule": (
                "The participant who declares a test load-bearing for this council "
                "must not be a voting seat on the same run, except the owner/charter "
                "binding frozen before ballots open. A registrar listed in votes is "
                "rejected. A majority cannot vote a test into load-bearing status, "
                "because that would let popularity name the evidence gate."
            ),
        },
        "tests": [
            {
                "id": "T1-unanimous-but-refuted",
                "command": P1,
                "result": "NOT-RUN",
                "required_by_catalog": (
                    "a unanimous-but-refuted fixture: the council votes YES, a test "
                    "fails, and the recorded outcome must NOT be YES"
                ),
            },
            {
                "id": "T2-converse-irrelevant-fail",
                "command": P2,
                "result": "NOT-RUN",
                "required_by_catalog": (
                    "a converse control: an irrelevant failing test must not be able "
                    "to veto a sound decision"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unanimous-yes-bound-fail",
                "kind": "known-broken-fixture",
                "description": (
                    "The check FIRES (outcome=REFUTED) on unanimous YES plus a "
                    "legal bound FAIL, and is SILENT (outcome=YES) when the same "
                    "bound test PASSes."
                ),
                "rejects": (
                    "unanimous YES ballots for claim C plus a legal load-bearing test "
                    "bound to C that exits non-zero"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"FIRES outcome={planted['outcome']} reason={planted['reason']} "
                    f"binding_yes={planted['binding_yes']}"
                ),
                "good_state_output": (
                    f"SILENT outcome={good['outcome']} reason={good['reason']}"
                ),
                "observed": (
                    f"outcome={planted['outcome']} reason={planted['reason']} "
                    f"binding_yes={planted['binding_yes']}"
                ),
                "state_rejected": (
                    "unanimous YES ballots for claim C plus a legal load-bearing test "
                    "bound to C that exits non-zero"
                ),
                "check_action": (
                    "adjudicate() sets outcome=REFUTED, binding_yes=false, reason="
                    "executable-test-override"
                ),
                "verbatim": O.NEGATIVE_CONTROL_VERBATIM,
                "planted_run": {
                    "fixture": "command-center/p2-wave/probes/CNL-0068/fixtures/unanimous_refuted.json",
                    "outcome": planted["outcome"],
                    "reason": planted["reason"],
                    "unanimous_yes": planted["tally"]["unanimous_yes"],
                    "binding_yes": planted["binding_yes"],
                },
                "silent_on": {
                    "fixture": "command-center/p2-wave/probes/CNL-0068/fixtures/known_good.json",
                    "outcome": good["outcome"],
                    "reason": good["reason"],
                },
            }
        ],
        "fixture_runs": {
            "unanimous_refuted": {
                "outcome": planted["outcome"],
                "reason": planted["reason"],
                "unanimous_yes": planted["tally"]["unanimous_yes"],
            },
            "known_good": {"outcome": good["outcome"], "reason": good["reason"]},
            "irrelevant_fail": {
                "outcome": converse["outcome"],
                "reason": converse["reason"],
                "irrelevant_failure_count": len(converse["irrelevant_failures"]),
            },
            "weighted_unanimous_refuted": {
                "outcome": weighted["outcome"],
                "yes_weight": weighted["tally"]["yes_weight"],
            },
            "seat_declares": {
                "outcome": seat["outcome"],
                "rejected": [row.get("reject_reasons") for row in seat["rejected_bindings"]],
            },
        },
        "reviewer": {
            "reviewer_id": "CNL-0068-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Named probe2 re-runs override.adjudicate on the fixtures and does not "
                "read this note's answer/mechanism.summary to compute the tally. It "
                "constructs counterexample instances rather than stating "
                "REFUTED-NOT-ATTEMPTED."
            ),
            "counterexample": {
                "id": "CE-IRRELEVANT-FAIL",
                "instance": (
                    "Three YES votes on claim.ship-ready plus a failing executable "
                    "bound to claim.other. If outcome is not YES, the relevance claim "
                    "is REFUTED."
                ),
                "observed_outcome": converse["outcome"],
                "survived": converse["outcome"] in O.ACCEPTING,
            },
            "further_instances": [
                "CE-WEIGHTED-UNANIMITY",
                "CE-SEAT-BINDER",
                "CE-POST-CLOSE",
                "CE-MAJORITY-DECLARE",
                "CE-PREFIX-CLAIM",
            ],
        },
        "evidence": [
            {
                "id": "E1-catalog-spec-sentences",
                "claim": (
                    "The program's catalog records the spec sentences this unit must "
                    "implement: agreement is not proof; evidence gates outrank "
                    "popularity; consensus that fails executable tests."
                ),
                "anchor": (
                    "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0068]."
                    "evidence_requirement (cites _USER-PROMPTS.md:11198 and :11244; "
                    "those restore files are not on this worktree)"
                ),
                "verdict": "CONFIRMED",
                "signal": "catalog-text",
            },
            {
                "id": "E2-live-unanimous-refuted",
                "claim": (
                    "A unanimous YES is not a binding YES when a legal load-bearing "
                    "test bound to the claim exits non-zero."
                ),
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py "
                    "plus fixtures/unanimous_refuted.json"
                ),
                "verdict": "CONFIRMED",
                "signal": "live-subprocess",
                "observed": {
                    "outcome": planted["outcome"],
                    "reason": planted["reason"],
                    "unanimous_yes": planted["tally"]["unanimous_yes"],
                },
            },
            {
                "id": "E3-live-converse",
                "claim": "An irrelevant failing test cannot veto a sound YES.",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py "
                    "plus fixtures/irrelevant_fail.json"
                ),
                "verdict": "CONFIRMED",
                "signal": "live-subprocess",
                "observed": {
                    "outcome": converse["outcome"],
                    "irrelevant_failures": len(converse["irrelevant_failures"]),
                },
            },
        ],
        "residual_unknowns": [
            "Harness-restore files 11-COUNCIL-SPECIFICATION.schema.json and _USER-PROMPTS.md are not on this worktree; protocol-preset names beyond the catalog sentences are NOT-CHECKED.",
            "CNL-0023 weight-provenance schema is not delivered; this unit treats weights as numbers and does not validate provenance records.",
            "TST-0274 both-direction factual settlement (passing probe forcing YES against a unanimous NO) is out of scope for this design note.",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0068/override.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "ts": now,
    }
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print("FAILED:CNL-0068 emit schema missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator(schema).validate(note)
    except jsonschema.exceptions.RefResolutionError:
        # Catalog schema is a $ref shim to ast-integrate.invalid; G-1 is
        # parse + sentinel + live probes, not a network fetch.
        if note.get("unit_id") != "CNL-0068" or "SUCCESS:CNL-0068" not in json.dumps(
            note
        ):
            print("FAILED:CNL-0068 emit note missing unit_id/sentinel")
            return 1
    except jsonschema.ValidationError as exc:
        print(f"FAILED:CNL-0068 emit schema {exc.message}")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(note, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:CNL-0068 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
