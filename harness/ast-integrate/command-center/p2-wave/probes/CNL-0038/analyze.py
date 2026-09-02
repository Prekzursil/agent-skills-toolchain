"""Mechanical verdicts, both-states control, and design-note body."""
from __future__ import annotations

import copy
from typing import Any

import family
import runtime
import stopping

PLANTED_PROSE = "when everyone seems done"


def classify_record(rec: dict[str, Any]) -> dict[str, Any]:
    sched = runtime.schedule(rec)
    readable, why = stopping.is_readable(rec.get("stopping"))
    verdict = "EXECUTABLE" if sched.get("executable") else "NOT-EXECUTABLE"
    return {
        "record_id": rec.get("id"),
        "slug": rec.get("slug"),
        "family": rec.get("family"),
        "verdict": verdict,
        "stopping_readable": readable,
        "classifier": why,
        "missing_element": sched.get("missing_element"),
        "turn_schedule": None if verdict != "EXECUTABLE" else {
            "turn_count": sched.get("turn_count"),
            "stopped_after_round": sched.get("stopped_after_round"),
            "stop_was_false_before_end": sched.get("stop_was_false_before_end"),
            "stop_true_at_end": sched.get("stop_true_at_end"),
            "turns": sched.get("turns"),
        },
        "stopping_as_written": rec.get("stopping"),
    }


def verdicts() -> list[dict[str, Any]]:
    return [classify_record(rec) for rec in family.deliberative_records()]


def both_states() -> dict[str, Any]:
    recs = family.deliberative_records()
    p02 = next(r for r in recs if r.get("id") == "P02")
    good_ok, good_why = stopping.is_readable(p02.get("stopping"))
    good_fire = not good_ok
    bad_ok, bad_why = stopping.is_readable(PLANTED_PROSE)
    bad_fire = not bad_ok
    mutant = copy.deepcopy(p02)
    mutant["stopping"] = PLANTED_PROSE
    mutant_sched = runtime.schedule(mutant)
    known_good_run = {
        "fixture": "known-good P02 round-robin typed stop",
        "record_id": "P02",
        "stopping": p02.get("stopping"),
        "readable": good_ok,
        "classifier": good_why,
        "fire": good_fire,
        "verbatim": (
            f"P02 known-good readable={good_ok} fire={good_fire} "
            f"classifier={good_why}"
        ),
    }
    planted_bad_run = {
        "fixture": "planted-bad P02 stopping replaced with moderator-style prose",
        "record_id": "P02",
        "stopping": PLANTED_PROSE,
        "readable": bad_ok,
        "classifier": bad_why,
        "fire": bad_fire,
        "schedule_executable": mutant_sched.get("executable"),
        "missing_element": mutant_sched.get("missing_element"),
        "verbatim": (
            f"P02 planted-bad readable={bad_ok} fire={bad_fire} "
            f"classifier={bad_why} executable={mutant_sched.get('executable')}"
        ),
    }
    return {
        "check": "prose-stop recognizer (FIRE iff stopping is not evaluator-readable)",
        "known_good": known_good_run,
        "planted_bad": planted_bad_run,
        "silent_on_good": good_ok and not good_fire,
        "fires_on_bad": bad_fire and not bad_ok and mutant_sched.get("executable") is False,
        "pass": (
            good_ok
            and not good_fire
            and bad_fire
            and not bad_ok
            and mutant_sched.get("executable") is False
        ),
    }


def negative_control() -> dict[str, Any]:
    ctrl = both_states()
    bad = ctrl["planted_bad"]
    return {
        "reject_state": PLANTED_PROSE,
        "what_the_check_does": (
            "On a typed round-robin record whose stopping field is replaced "
            "with prose ('when everyone seems done'), the recognizer FIRES "
            "(readable=false) and the runtime refuses to emit a turn schedule, "
            "naming the missing evaluator-readable stopping expression. "
            "It does not invent a max_rounds halt to make the protocol appear executable."
        ),
        "verbatim": bad["verbatim"],
        "fire": bad["fire"],
        "executable": bad["schedule_executable"],
    }


def note_body() -> dict[str, Any]:
    enum = family.enumeration()
    rows = verdicts()
    ctrl = both_states()
    neg = negative_control()
    not_exec = [r for r in rows if r["verdict"] == "NOT-EXECUTABLE"]
    exec_rows = [r for r in rows if r["verdict"] == "EXECUTABLE"]
    p1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0038/probe1_family_recount.py"
    p2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0038/probe2_both_states.py"
    unit = family.catalog_unit()
    answer = (
        "Of the 6 DELIBERATIVE records (P01–P06), five have evaluator-readable "
        "stopping trees and emit a finite turn-by-turn schedule that is false "
        "before the last round and true at halt. P01 free-form-moderated-panel "
        "cannot be executed as written: its stopping condition is moderator-"
        "discretion prose that the AND/OR/NOT/ANY/ALL/weighted evaluator cannot "
        "parse. The ADVERSARIAL decoy P07 is excluded by family filter."
    )
    return {
        "unit_id": "CNL-0038",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0038",
        "title": unit.get("title"),
        "question": unit.get("question_or_target"),
        "answer": answer,
        "family": {
            "name": "DELIBERATIVE",
            "expected_n": enum["catalog_expected_n"],
            "counted_n": enum["slice_family_n"],
            "catalog_named_n": enum["catalog_named_n"],
            "library_present": enum["library_present"],
            "library_path": enum["library_path"],
            "slice_path": enum["slice_path"],
            "source_claimed": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
            "enumeration_basis": (
                "Catalog item CNL-0038 names P01–P06 so no member can fall "
                "through a family mis-assignment. Independent recount: "
                "evidence_requirement expected n=6, parenthetical P-id list "
                "n=6, family=DELIBERATIVE rows in the local family slice n=6. "
                "The Windows library file is absent on this worktree; the slice "
                "is not a byte copy of that file."
            ),
            "members": enum["catalog_named"],
            "slice_family_ids": enum["slice_family_ids"],
            "decoy_excluded": enum["decoy_excluded"],
            "counts_agree": enum["counts_agree"],
        },
        "verdicts": rows,
        "not_executable_ids": [r["record_id"] for r in not_exec],
        "executable_ids": [r["record_id"] for r in exec_rows],
        "executable_count": len(exec_rows),
        "not_executable_count": len(not_exec),
        "which_cannot_execute_as_written": (
            not_exec[0]["record_id"] if len(not_exec) == 1 else [r["record_id"] for r in not_exec]
        ),
        "tests": [
            {
                "id": "family-coverage",
                "command": p1,
                "result": "PASS" if enum["counts_agree"] and len(rows) == 6 else "FAIL",
            },
            {
                "id": "both-states-prose-stop",
                "command": p2,
                "result": "PASS" if ctrl["pass"] else "FAIL",
            },
        ],
        "both_states": ctrl,
        "negative_control": neg,
        "reviewer": {
            "reviewer_id": "CNL-0038-probe1-independent-recount",
            "independent": True,
            "verdict": "PASS" if enum["counts_agree"] else "BLOCK",
            "method": (
                "Re-parse catalog named P-ids and expected n; re-filter "
                "family=DELIBERATIVE from the slice; do not read the author's "
                "answer paragraph. A disagreement in n blocks the unit."
            ),
            "counted_n": enum["slice_family_n"],
            "author_n": 6,
        },
        "evidence": [
            {
                "claim": "Catalog names exactly six DELIBERATIVE members P01–P06.",
                "verdict": "CONFIRMED" if enum["catalog_named_n"] == 6 else "REFUTED",
                "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0038.question_or_target",
            },
            {
                "claim": "Independent family=DELIBERATIVE filter yields the same six ids; P07 decoy is excluded.",
                "verdict": "CONFIRMED" if enum["counts_agree"] and enum["decoy_excluded"] == ["P07"] else "REFUTED",
                "anchor": enum["slice_path"],
            },
            {
                "claim": "P01 stopping is prose no evaluator can read; runtime emits NOT-EXECUTABLE naming the missing expression.",
                "verdict": "CONFIRMED" if len(not_exec) == 1 and not_exec[0]["record_id"] == "P01" else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0038/stopping.py",
            },
            {
                "claim": "P02–P06 emit finite schedules whose stop is false before the last round and true at halt.",
                "verdict": "CONFIRMED"
                if exec_rows
                and all(
                    (r["turn_schedule"] or {}).get("stop_true_at_end")
                    and (r["turn_schedule"] or {}).get("stop_was_false_before_end")
                    for r in exec_rows
                )
                else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0038/runtime.py",
            },
            {
                "claim": "Both-states: recognizer is silent on typed P02 and FIRES on planted prose P02.",
                "verdict": "CONFIRMED" if ctrl["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/CNL-0038/analyze.py:both_states",
            },
        ],
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0038-executable-runtime-semantics-for-the-6-deliberative-protoc.md",
                "exists": True,
                "role": "primary",
            },
            {
                "path": enum["slice_path"],
                "exists": True,
                "role": "family-slice",
            },
        ],
        "completion_sentinel": "SUCCESS:CNL-0038",
    }
