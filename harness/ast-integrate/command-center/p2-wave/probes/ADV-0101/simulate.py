#!/usr/bin/env python3
"""Paired opposite-failure councils + independent information-gain.

The evaluator stops when the expression is TRUE. Minimum-deliberation
floors are measured separately so a premature stop is observable.

Information-gain counts new unique utterance tokens and never reads the
evaluator's consensus / no_new_objection_rounds fields.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from stopping import SPEC_EXPRESSIONS, evaluate

SIM_CAP = 24
FLOORS = {
    "min_rounds": 3,
    "min_independent_briefs": 2,
    "min_evidence_items": 1,
}

WORD_RE = re.compile(r"[a-z0-9]+")

PROOF_OK = {
    "contradiction",
    "exhaustive_finite_search_with_bound",
    "reduction_to_known_impossible",
}
PROOF_NOT = {"unsuccessful_search", "we_could_not_find_it", "search_failed"}

INSTANT_UTTERANCE = "AGREE: ship it now. No further discussion is needed."
ENDLESS_PARAPHRASES = [
    "We should keep talking about shipping it without adding a new claim.",
    "Continuing the same point: shipping remains the topic under discussion.",
    "Restating: the council is still circling the ship-it remark.",
    "Again: no new content, only the previous ship-it remark rephrased.",
]


def _tokens(text: str) -> set[str]:
    return set(WORD_RE.findall(text.lower()))


def info_gain_step(utterances: list[str], prior: set[str]) -> dict[str, Any]:
    tokens: set[str] = set()
    for u in utterances:
        tokens |= _tokens(u)
    new = tokens - prior
    return {
        "new_unique_count": len(new),
        "union_size_after": len(prior | tokens),
        "tokens": tokens,
    }


def proof_holds(artifact: dict[str, Any] | None) -> bool:
    if not artifact:
        return False
    if artifact.get("kind") in PROOF_NOT:
        return False
    return bool(artifact.get("kind") in PROOF_OK and artifact.get("body"))


def floors_met(state: dict[str, Any]) -> dict[str, Any]:
    ok = (
        int(state.get("round") or 0) >= FLOORS["min_rounds"]
        and int(state.get("independent_briefs") or 0)
        >= FLOORS["min_independent_briefs"]
        and int(state.get("evidence_items") or 0) >= FLOORS["min_evidence_items"]
    )
    return {
        "met": ok,
        "required": dict(FLOORS),
        "observed": {
            "round": state.get("round"),
            "independent_briefs": state.get("independent_briefs"),
            "evidence_items": state.get("evidence_items"),
        },
    }


def _base_state() -> dict[str, Any]:
    return {
        "round": 0,
        "unique_ideas": 0,
        "completeness_score": 0.0,
        "consensus": 0.0,
        "no_new_objection_rounds": 0,
        "unanimity": False,
        "max_rounds": 0,
        "quality_gate": None,
        "unresolved_load_bearing_counterexample": 1,
        "evidence_saturation": False,
        "time_minutes": 0,
        "proof_of_impossibility": False,
        "independent_briefs": 0,
        "evidence_items": 0,
        "idea_ledger": [],
        "answered_subquestions": 0,
        "declared_subquestions": 3,
        "proof_artifact": None,
    }


def _apply_ledger(state: dict[str, Any]) -> None:
    state["unique_ideas"] = len(set(state["idea_ledger"]))
    denom = max(1, int(state["declared_subquestions"]))
    state["completeness_score"] = round(
        float(state["answered_subquestions"]) / denom, 4
    )
    state["proof_of_impossibility"] = proof_holds(state.get("proof_artifact"))
    state["max_rounds"] = state["round"]


def bindings(state: dict[str, Any]) -> dict[str, Any]:
    b: dict[str, Any] = {
        "unique_ideas": state["unique_ideas"],
        "completeness_score": state["completeness_score"],
        "consensus": state["consensus"],
        "no_new_objection_rounds": state["no_new_objection_rounds"],
        "unanimity": state["unanimity"],
        "max_rounds": state["max_rounds"],
        "unresolved_load_bearing_counterexample": state[
            "unresolved_load_bearing_counterexample"
        ],
        "evidence_saturation": state["evidence_saturation"],
        "time_minutes": state["time_minutes"],
        "proof_of_impossibility": state["proof_of_impossibility"],
    }
    if state["quality_gate"] is not None:
        b["quality_gate"] = state["quality_gate"]
    return b


def instant_round(state: dict[str, Any], rnd: int) -> list[str]:
    state["round"] = rnd
    state["unanimity"] = True
    state["consensus"] = 1.0
    state["no_new_objection_rounds"] = rnd
    state["time_minutes"] = rnd
    if rnd == 1:
        state["idea_ledger"] = ["ship-it"]
    state["independent_briefs"] = 0
    state["evidence_items"] = 0
    state["answered_subquestions"] = 0
    state["quality_gate"] = None
    state["unresolved_load_bearing_counterexample"] = 1
    state["evidence_saturation"] = False
    state["proof_artifact"] = {"kind": "unsuccessful_search", "body": "looked, failed"}
    _apply_ledger(state)
    return [INSTANT_UTTERANCE, INSTANT_UTTERANCE, INSTANT_UTTERANCE]


def endless_round(state: dict[str, Any], rnd: int) -> list[str]:
    state["round"] = rnd
    state["unanimity"] = False
    state["consensus"] = 0.97
    state["no_new_objection_rounds"] = rnd
    # Stalled clock: low-info hang must not sneak into the 180-minute timer.
    state["time_minutes"] = min(5, rnd)
    if rnd == 1:
        state["idea_ledger"] = ["ship-it"]
    state["independent_briefs"] = 0
    state["evidence_items"] = 0
    state["answered_subquestions"] = 0
    state["quality_gate"] = None
    state["unresolved_load_bearing_counterexample"] = 1
    state["evidence_saturation"] = False
    state["proof_artifact"] = {"kind": "we_could_not_find_it", "body": ""}
    _apply_ledger(state)
    # Identical restatement: lexical novelty after round 1 must be zero.
    line = ENDLESS_PARAPHRASES[0]
    return [line, line, line]


def healthy_round(state: dict[str, Any], rnd: int) -> list[str]:
    state["round"] = rnd
    state["unanimity"] = False
    state["consensus"] = min(0.5 + 0.05 * rnd, 0.8)
    state["no_new_objection_rounds"] = 0
    state["time_minutes"] = rnd * 8
    state["idea_ledger"].append(f"distinct-idea-{rnd}-mechanism")
    if rnd <= 3:
        state["answered_subquestions"] = rnd
        state["independent_briefs"] = rnd
        state["evidence_items"] = rnd
    if rnd >= 5:
        while len(set(state["idea_ledger"])) < 100:
            state["idea_ledger"].append(f"injected-idea-{len(state['idea_ledger'])}")
        state["answered_subquestions"] = 3
        state["declared_subquestions"] = 3
        state["quality_gate"] = "PASS"
        state["unresolved_load_bearing_counterexample"] = 0
        state["evidence_saturation"] = True
        state["independent_briefs"] = 3
        state["evidence_items"] = 3
        state["consensus"] = 0.96
        state["no_new_objection_rounds"] = 2
        state["unanimity"] = True
        state["proof_artifact"] = {
            "kind": "contradiction",
            "body": "A and not-A derived from bound exhaustive cases 1..N",
        }
        state["time_minutes"] = 180
    _apply_ledger(state)
    utt = (
        f"New mechanism idea-{rnd} addresses subquestion with evidence "
        f"citation-{rnd} and a distinct lemma."
    )
    return [
        utt,
        f"critique of idea-{rnd} with a new objection",
        f"scribe notes idea-{rnd}",
    ]


COUNCILS = {
    "instant_agree": instant_round,
    "endless_low_info": endless_round,
    "healthy_progress": healthy_round,
}


def _run_one(expr: dict[str, str], council_id: str) -> dict[str, Any]:
    state = _base_state()
    step = COUNCILS[council_id]
    prior: set[str] = set()
    rounds: list[dict[str, Any]] = []
    stop_reason = "sim_cap"
    stopped_at = None
    premature = False
    expr_true_at: int | None = None
    for rnd in range(1, SIM_CAP + 1):
        utterances = step(state, rnd)
        gain = info_gain_step(utterances, prior)
        prior |= gain["tokens"]
        ev = evaluate(expr["text"], bindings(state))
        floor = floors_met(state)
        rec = {
            "round": rnd,
            "utterances": utterances,
            "bindings": bindings(state),
            "floors": floor,
            "eval": {"value": ev["value"], "stop": ev["stop"]},
            "info_gain_new_unique_count": gain["new_unique_count"],
            "info_gain_union_size_after": gain["union_size_after"],
        }
        rounds.append(rec)
        if ev["stop"] and expr_true_at is None:
            expr_true_at = rnd
        if ev["stop"]:
            stop_reason = "expression"
            stopped_at = rnd
            premature = not floor["met"]
            break
    total_new_after_r1 = sum(r["info_gain_new_unique_count"] for r in rounds[1:])
    evaluator_stopped = stop_reason == "expression"
    return {
        "council_id": council_id,
        "expression_id": expr["id"],
        "expression": expr["text"],
        "stopped_at": stopped_at,
        "stop_reason": stop_reason,
        "premature_stop": premature,
        "expr_true_at": expr_true_at,
        "sim_cap": SIM_CAP,
        "rounds_run": len(rounds),
        "failed_to_stop": stop_reason == "sim_cap",
        "info_gain_after_round1_total": total_new_after_r1,
        "evaluator_stopped": evaluator_stopped,
        "divergence_zero_gain_but_evaluator_stop": bool(
            evaluator_stopped and total_new_after_r1 == 0 and (stopped_at or 0) >= 2
        ),
        "divergence_zero_gain_evaluator_never_stops": bool(
            stop_reason == "sim_cap" and total_new_after_r1 == 0
        ),
        "proof_fired": bool(state.get("proof_of_impossibility")),
        "proof_artifact_kind": (state.get("proof_artifact") or {}).get("kind"),
        "final_bindings": bindings(state),
        "final_floors": floors_met(state),
        "rounds": rounds,
    }


def run_all() -> dict[str, Any]:
    expression_runs: list[dict[str, Any]] = []
    for expr in SPEC_EXPRESSIONS:
        row: dict[str, Any] = {"expression": expr, "councils": {}}
        for cid in ("instant_agree", "endless_low_info", "healthy_progress"):
            row["councils"][cid] = _run_one(expr, cid)
        expression_runs.append(row)

    premature_hits: list[str] = []
    endless_hits: list[str] = []
    divergences: list[dict[str, Any]] = []
    for row in expression_runs:
        inst = row["councils"]["instant_agree"]
        end = row["councils"]["endless_low_info"]
        if inst["premature_stop"]:
            premature_hits.append(row["expression"]["id"])
        if end["failed_to_stop"] or end["divergence_zero_gain_but_evaluator_stop"]:
            endless_hits.append(row["expression"]["id"])
        if (
            end["divergence_zero_gain_but_evaluator_stop"]
            or end["divergence_zero_gain_evaluator_never_stops"]
        ):
            divergences.append(
                {
                    "expression_id": row["expression"]["id"],
                    "zero_gain_but_stop": end["divergence_zero_gain_but_evaluator_stop"],
                    "zero_gain_never_stops": end[
                        "divergence_zero_gain_evaluator_never_stops"
                    ],
                    "stop_reason": end["stop_reason"],
                    "stopped_at": end["stopped_at"],
                    "info_gain_after_round1_total": end["info_gain_after_round1_total"],
                }
            )

    e6 = next(r for r in expression_runs if r["expression"]["id"] == "E6")
    premature_verdict = "CONFIRMED" if premature_hits else "REFUTED"
    endless_verdict = "CONFIRMED" if endless_hits else "REFUTED"
    if premature_verdict == "CONFIRMED" and endless_verdict == "CONFIRMED":
        overall = "CONFIRMED"
    elif premature_verdict == "REFUTED" and endless_verdict == "REFUTED":
        overall = "REFUTED"
    else:
        overall = "PARTIAL"

    return {
        "expression_runs": expression_runs,
        "premature_hits": premature_hits,
        "endless_hits": endless_hits,
        "info_gain_divergences": divergences,
        "premature_verdict": premature_verdict,
        "endless_verdict": endless_verdict,
        "overall_verdict": overall,
        "e6_unsuccessful_search_did_not_fire": (
            e6["councils"]["instant_agree"]["proof_fired"] is False
            and e6["councils"]["endless_low_info"]["proof_fired"] is False
        ),
        "e6_real_proof_fires_on_healthy": e6["councils"]["healthy_progress"][
            "proof_fired"
        ]
        is True,
        "all_six_exercised": [e["expression"]["id"] for e in expression_runs],
        "skipped_expressions": [],
        "release_mode": "PR-ONLY",
        "unsatisfiable_under_release_mode": [],
    }


def compact_runs(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for row in bundle["expression_runs"]:
        councils = {}
        for cid, run in row["councils"].items():
            councils[cid] = {k: v for k, v in run.items() if k != "rounds"}
            councils[cid]["round_summaries"] = [
                {
                    "round": r["round"],
                    "eval": r["eval"],
                    "floors_met": r["floors"]["met"],
                    "info_gain_new_unique_count": r["info_gain_new_unique_count"],
                    "bindings": r["bindings"],
                }
                for r in run["rounds"]
            ]
        out.append({"expression": deepcopy(row["expression"]), "councils": councils})
    return out
