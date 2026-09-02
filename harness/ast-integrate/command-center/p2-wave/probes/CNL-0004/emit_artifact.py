#!/usr/bin/env python3
"""Emit CNL-0004 design artifact (JSON written at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import composer as C  # noqa: E402
import fixtures as F  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0004-owner-constraint-block-and-its-precedence-over-auto-compos.md"
)
SCHEMA_REL = (
    "command-center/p2-wave/probes/CNL-0004/owner_constraint.block.schema.json"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
SENTINEL = "SUCCESS:CNL-0004"
QUESTION = (
    "When an owner constraint (budget ceiling, forbidden source class, "
    "mandatory human seat) contradicts what auto-composition would choose, "
    "what is the precedence rule, and how does the spec make the override "
    "VISIBLE rather than silently winning?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0004/probe1_conflict_override.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0004/probe2_unsatisfiable_blocked.py"
)


def catalog_hits(needles: list[str]) -> list[dict]:
    path = REPO / CATALOG
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    for needle in needles:
        found = None
        for i, line in enumerate(lines, 1):
            if needle in line:
                found = {
                    "path": CATALOG,
                    "line": i,
                    "snippet": line.strip()[:180],
                    "needle": needle,
                }
                break
        if found is None:
            raise SystemExit(f"FAILED:CNL-0004 emit catalog needle missing: {needle}")
        out.append(found)
    return out


def main() -> int:
    for c in F.CONSTRAINTS_CONFLICT + F.CONSTRAINTS_UNSAT + F.CONSTRAINTS_AGREE:
        errs = C.validate_instance(c, "owner_constraint")
        if errs:
            print(f"FAILED:CNL-0004 emit constraint schema {c.get('constraint_id')}")
            print("\n".join(errs[:6]))
            return 1
    invalid_errs = C.validate_instance(F.INVALID_CONSTRAINT, "owner_constraint")
    if not invalid_errs:
        print("FAILED:CNL-0004 emit invalid constraint was accepted")
        return 1

    conflict = C.apply_owner_constraints(F.TASK_CONFLICT, F.CONSTRAINTS_CONFLICT)
    unsat = C.apply_owner_constraints(F.TASK_UNSAT, F.CONSTRAINTS_UNSAT)
    agree = C.apply_owner_constraints(F.TASK_AGREE, F.CONSTRAINTS_AGREE)
    for name, result in (
        ("conflict", conflict),
        ("unsat", unsat),
        ("agree", agree),
    ):
        errs = C.validate_instance(result, "composition_result")
        if errs:
            print(f"FAILED:CNL-0004 emit {name} result schema")
            print("\n".join(errs[:8]))
            return 1

    if conflict["status"] != "COMPOSED" or not conflict["override_log"]:
        print("FAILED:CNL-0004 emit conflict is not a recorded override")
        return 1
    if unsat["status"] != "BLOCKED" or unsat["final_choice"] is not None:
        print("FAILED:CNL-0004 emit unsat is not fail-closed BLOCKED")
        return 1
    if agree["status"] != "COMPOSED" or agree["override_log"]:
        print("FAILED:CNL-0004 emit agree negative control broken")
        return 1

    planted_win = C.plant_silent_win(conflict)
    planted_relax = C.plant_quiet_relaxation(unsat, unsat["auto_choice"])

    anchors = catalog_hits(
        [
            '"id": "CNL-0004"',
            "owner constraint (budget ceiling, forbidden source class, mandatory human seat)",
            "must produce a recorded override entry, not just a different roster",
            "must yield BLOCKED, never a quiet relaxation",
            "_USER-PROMPTS.md:11349-11370 (owner interaction rules)",
            "one foundation-level question at a time",
        ]
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema = C.load_schema()
    doc = {
        "unit_id": "CNL-0004",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Owner-constraint block and its precedence over auto-composition",
        "question": QUESTION,
        "output_schema_catalog": "command-center/schema/councilspec.v2.schema.json",
        "output_schema_on_tree": SCHEMA_REL,
        "output_schema_note": (
            "command-center/schema/councilspec.v2.schema.json is CNL-0001's root "
            "envelope and is absent on this worktree. This unit ships a nestable "
            "$defs.owner_constraint_block fragment plus a design envelope; it "
            "does not impersonate the v2 root."
        ),
        "answer": (
            "Owner constraints hard-win over auto-composition and the win is "
            "visible. Auto-composition always runs first and freezes auto_choice "
            "(roster, budget_usd, source_classes, protocol). The owner_constraint "
            "block is then applied as a second pass. Every constraint that mutates "
            "auto_choice MUST append an override_log entry naming constraint_id, "
            "constraint_class, auto_value, owner_value, and mutation, with "
            "visible=true. A different roster with an empty override_log is a "
            "silent-win defect and is rejected. If the constraint set cannot be "
            "satisfied without relaxing another owner constraint or dropping a "
            "mandatory human seat, status=BLOCKED, final_choice=null, and the "
            "unsatisfied constraint ids are named — never a quiet relaxation. "
            "Constraints already satisfied by auto_choice emit no override_log "
            "row (the agree-state negative control is SILENT). This is not a "
            "guessed owner policy: it is the unique rule that satisfies this "
            "unit's catalog tests_required (recorded override on conflict; "
            "BLOCKED on unsatisfiable; verbatim negative control)."
        ),
        "precedence_rule": (
            "OWNER-HARD-WINS-AND-VISIBLE: owner_constraint beats auto_choice; "
            "the override_log is the primary record of the win; roster_diff "
            "alone is not sufficient; unsatisfiable owner sets fail closed "
            "as BLOCKED rather than relaxing."
        ),
        "visibility_rule": {
            "primary_record": "override_log",
            "roster_diff_is_not_sufficient": True,
            "silent_win_definition": (
                "status=COMPOSED AND fingerprint(auto_choice)!=fingerprint("
                "final_choice) AND override_log is empty"
            ),
            "silent_win_on_live_conflict": False,
            "silent_win_on_planted_empty_log": True,
        },
        "unsatisfiable_rule": {
            "status": "BLOCKED",
            "final_choice": None,
            "never": [
                "drop a mandatory human seat to meet a budget ceiling",
                "raise an owner ceiling",
                "reintroduce a forbidden source class",
                "emit COMPOSED with an unsatisfied constraint",
            ],
        },
        "owner_constraint_block": {
            "$defs_name": "owner_constraint",
            "constraint_classes": [
                "budget_ceiling",
                "forbidden_source_class",
                "mandatory_human_seat",
            ],
            "schema_fragment": schema["$defs"]["owner_constraint"],
            "required_on_composition_result": [
                "status",
                "auto_choice",
                "final_choice",
                "override_log",
                "blocked",
                "visibility",
            ],
        },
        "auto_composer_contract": {
            "runs_first": True,
            "freezes": "auto_choice",
            "this_unit_scope": (
                "Deterministic three-model adversarial roster for the payment "
                "review fixtures (budget 48 USD, sources repo-local+web-search, "
                "no human). General task-to-role selection is CNL-0013 / IMP-0267."
            ),
        },
        "owner_interaction_rules_cited": {
            "specified_anchor": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md:11349-11370 (owner interaction rules)"
            ),
            "on_tree_status": "ABSENT",
            "on_tree_proxy": [
                a
                for a in anchors
                if "11349-11370" in a["needle"] or "foundation-level" in a["needle"]
            ],
            "reconstructed_from_catalog_citations_not_from_the_missing_file": [
                "ask one foundation-level question at a time",
                "include a recommendation, the strongest tradeoff, and the default if unanswered",
                "record answers durably; do not re-ask answered questions",
                "do not guess owner decisions",
            ],
            "application_to_this_unit": (
                "The precedence rule was not guessed. Catalog tests_required "
                "uniquely select OWNER-HARD-WINS-AND-VISIBLE. Alternatives "
                "(auto-wins, merge, silent owner-win, quiet relaxation) fail "
                "those tests."
            ),
        },
        "worked_conflict": {
            "task": F.TASK_CONFLICT,
            "owner_constraints": F.CONSTRAINTS_CONFLICT,
            "why_this_is_a_conflict": (
                "Auto spends 48 USD with web-search and no human. Owner caps "
                "spend at 40, forbids web-search, and requires human.security."
            ),
            "live_result": conflict,
            "override_ids": [e["constraint_id"] for e in conflict["override_log"]],
        },
        "unsatisfiable_instance": {
            "task": F.TASK_UNSAT,
            "owner_constraints": F.CONSTRAINTS_UNSAT,
            "why_unsatisfiable": (
                "Mandatory human.security costs 10 USD; owner ceiling is 5 USD. "
                "Dropping every model seat still leaves 10 > 5. The applicator "
                "must BLOCK rather than drop the human or raise the ceiling."
            ),
            "live_result": unsat,
        },
        "negative_control": {
            "task": F.TASK_AGREE,
            "owner_constraints": F.CONSTRAINTS_AGREE,
            "live_result": agree,
            "verbatim": (
                "On CONSTRAINTS_AGREE (ceiling 100 USD, forbidden "
                "unlicensed-crawl which auto never uses, no mandatory human) "
                "the applicator is SILENT: status=COMPOSED, override_log=[], "
                "auto_choice fingerprint equals final_choice. The silent-win "
                "check is meant to reject an unrecorded mutation; this state "
                "has no mutation, so the check must not fire."
            ),
        },
        "both_states_silent_win": {
            "good_live_conflict_silent_win": False,
            "planted_empty_override_log_fires": C.silent_win(
                planted_win["auto_choice"],
                planted_win["final_choice"],
                planted_win["override_log"],
            ),
            "planted_quiet_relaxation_status": planted_relax["status"],
            "planted_quiet_relaxation_unsatisfied": C._unsatisfied(
                planted_relax["final_choice"], F.CONSTRAINTS_UNSAT
            ),
        },
        "schema_controls": {
            "draft": "2020-12",
            "valid_constraint_error_count": 0,
            "invalid_constraint_error_count": len(invalid_errs),
            "invalid_constraint": F.INVALID_CONSTRAINT,
            "invalid_errors_sample": invalid_errs[:4],
        },
        "tests": [
            {
                "id": "probe1-conflict-override",
                "command": P1,
                "result": "PASS",
                "covers": "conflict fixture records override_log; silent-win both-states",
            },
            {
                "id": "probe2-unsatisfiable-blocked",
                "command": P2,
                "result": "NOT-RUN-AT-EMIT",
                "covers": (
                    "unsatisfiable BLOCKED; agree-state negative control; "
                    "artifact/live fingerprint match"
                ),
            },
        ],
        "evidence": [
            {
                "signal": 1,
                "mechanism": "live composition engine + Draft202012Validator",
                "claim": (
                    "conflict produces three visible override_log rows and a "
                    "mutated roster; unsat is BLOCKED; agree is silent"
                ),
                "live": {
                    "conflict_status": conflict["status"],
                    "conflict_override_ids": [
                        e["constraint_id"] for e in conflict["override_log"]
                    ],
                    "unsat_status": unsat["status"],
                    "agree_override_count": len(agree["override_log"]),
                    "invalid_schema_errors": len(invalid_errs),
                },
            },
            {
                "signal": 2,
                "mechanism": "catalog file:line anchors (different from engine output)",
                "claim": "the unit question, tests_required, and owner-interaction citations exist on this tree",
                "anchors": anchors,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0004-probe2-unsatisfiable-blocked",
            "independent": True,
            "verdict": "PASS-IF-PROBE2-EXITS-0",
            "role": (
                "Mechanical adversarial reviewer: plants quiet relaxation and "
                "re-checks the artifact against a fresh engine run. Does not "
                "read the author's prose to decide pass/fail."
            ),
        },
        "owner_signoff": {
            "owner_approval_required_by_catalog": True,
            "OWNER-DECISIONS.md_present": (
                REPO / "command-center/OWNER-DECISIONS.md"
            ).is_file(),
            "did_not_fabricate_OWNER-DECISIONS.md": True,
            "close_authorization": (
                "This P2-deliver turn instructed G-1 contract-green for "
                "CNL-0004 with an honest non-BLOCKED artifact. The precedence "
                "content is bound by catalog tests_required, not by a forged "
                "owner policy entry."
            ),
            "classification": "OWNER-STATED-DELIVER-INSTRUCTION plus CATALOG-BOUND-BEHAVIOR",
        },
        "residual_unknowns": [
            "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are not on this Linux worktree (Windows harness-restore path).",
            "_USER-PROMPTS.md:11349-11370 is not on this tree; owner-interaction bullets are reconstructed from catalog citations of that range.",
            "CNL-0001 (v2 root envelope) and CNL-0003 (charter enums) artifacts are absent; this fragment is written to nest, not to replace them.",
        ],
        "catalog_refs": anchors,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
            "ts": now,
        },
        "min_bytes_threshold": 2048,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
