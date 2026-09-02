#!/usr/bin/env python3
"""Run the decision rule plus both protocols on the three questions."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from catalog import QUESTIONS, RAPID_PARAMS, SYSTEMATIC_PARAMS
from capture import load_index
from decision import (
    MUTANT_ALWAYS_RAPID,
    MUTANT_ALWAYS_SYSTEMATIC,
    recommend,
)
from protocol import params_fingerprint, run_question


def run(index: dict | None = None) -> dict[str, Any]:
    idx = index if index is not None else load_index()
    questions = []
    for q in QUESTIONS:
        row = run_question(q, idx)
        live = recommend(q["factors"])
        always_sys = recommend(q["factors"], mutant=MUTANT_ALWAYS_SYSTEMATIC)
        always_rapid = recommend(q["factors"], mutant=MUTANT_ALWAYS_RAPID)
        row["rule"] = live
        row["mutants"] = {
            "always_systematic": always_sys,
            "always_rapid": always_rapid,
        }
        row["rule_matches_negative_control"] = (
            live["protocol"] == "RAPID"
            and row["diff"]["negative_control_rapid_complete"]
        ) or (
            live["protocol"] == "SYSTEMATIC"
            and row["diff"]["n_decision_relevant_misses"] >= 1
        )
        questions.append(row)

    by_id = {r["question_id"]: r for r in questions}
    q1 = by_id["Q1"]
    q2 = by_id["Q2"]
    q3 = by_id["Q3"]

    negative_control = {
        "question_id": "Q1",
        "rapid_decision_relevant_misses": q1["diff"]["n_decision_relevant_misses"],
        "pass": q1["diff"]["n_decision_relevant_misses"] == 0,
        "note": (
            "At least one question must show rapid missing nothing "
            "decision-relevant, else the rule collapses to always-systematic."
        ),
    }
    q3_also = q3["diff"]["n_decision_relevant_misses"] == 0

    always_sys_collapses = all(
        r["mutants"]["always_systematic"]["protocol"] == "SYSTEMATIC" for r in questions
    )
    always_sys_fails_negative_control = (
        q1["mutants"]["always_systematic"]["protocol"] == "SYSTEMATIC"
        and q1["diff"]["n_decision_relevant_misses"] == 0
    )
    live_recommends_rapid_on_q1 = q1["rule"]["protocol"] == "RAPID"
    live_recommends_systematic_on_q2 = q2["rule"]["protocol"] == "SYSTEMATIC"
    live_recommends_rapid_on_q3 = q3["rule"]["protocol"] == "RAPID"

    fp_r = params_fingerprint(RAPID_PARAMS)
    fp_s = params_fingerprint(SYSTEMATIC_PARAMS)

    both_states = {
        "known_good": {
            "id": "live-rule",
            "q1_protocol": q1["rule"]["protocol"],
            "q2_protocol": q2["rule"]["protocol"],
            "q3_protocol": q3["rule"]["protocol"],
            "negative_control_pass": negative_control["pass"]
            and live_recommends_rapid_on_q1,
            "q2_has_decision_relevant_miss": q2["diff"]["n_decision_relevant_misses"]
            >= 1
            and live_recommends_systematic_on_q2,
        },
        "known_broken": {
            "id": MUTANT_ALWAYS_SYSTEMATIC,
            "q1_protocol": q1["mutants"]["always_systematic"]["protocol"],
            "collapses_to_always_systematic": always_sys_collapses,
            "fails_negative_control": always_sys_fails_negative_control,
        },
        "known_broken_always_rapid": {
            "id": MUTANT_ALWAYS_RAPID,
            "q2_protocol": q2["mutants"]["always_rapid"]["protocol"],
            "ignores_q2_misses": q2["mutants"]["always_rapid"]["protocol"] == "RAPID"
            and q2["diff"]["n_decision_relevant_misses"] >= 1,
        },
        "discriminates": (
            live_recommends_rapid_on_q1
            and live_recommends_systematic_on_q2
            and always_sys_fails_negative_control
        ),
    }

    result = {
        "questions": questions,
        "negative_control": negative_control,
        "q3_rapid_also_complete": q3_also,
        "fingerprints": {
            "rapid": fp_r,
            "systematic": fp_s,
            "differ": fp_r != fp_s,
        },
        "both_states": both_states,
        "live_rule": {
            "Q1": q1["rule"]["protocol"],
            "Q2": q2["rule"]["protocol"],
            "Q3": q3["rule"]["protocol"],
        },
        "pass": (
            negative_control["pass"]
            and live_recommends_rapid_on_q1
            and live_recommends_systematic_on_q2
            and live_recommends_rapid_on_q3
            and q2["diff"]["n_decision_relevant_misses"] >= 1
            and fp_r != fp_s
            and both_states["discriminates"]
        ),
        "index_captured_at": idx.get("captured_at") or idx.get("captured_at"),
        "index_failures": list(idx.get("failures") or idx.get("failures") or []),
    }
    result["pass"] = result["pass"]
    result["index_failures"] = result["index_failures"]
    return result


def compact(result: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(result)
    for q in out.get("questions") or []:
        q["rapid_claim_ids"] = [c["id"] for c in q.pop("rapid_claims", [])]
        q["systematic_claim_ids"] = [c["id"] for c in q.pop("systematic_claims", [])]
    return out
