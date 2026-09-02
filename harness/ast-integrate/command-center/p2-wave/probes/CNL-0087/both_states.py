"""Both-states matrix for CNL-0087: planted FIRE, clean SILENT, numeric FPR."""
from __future__ import annotations

from typing import Any

import fixtures as FX
from detector import detect, naive_vote_match


def _row(council: dict[str, Any]) -> dict[str, Any]:
    live = detect(council)
    naive = naive_vote_match(council)
    return {
        "id": council["id"],
        "expected": council["expected"],
        "fired": live["fired"],
        "silent": live["silent"],
        "sycophantic_count": live["sycophantic_count"],
        "naive_vote_match_fired": naive["fired"],
        "votes": [p["vote"] for p in council["participants"]],
        "findings": live["findings"],
    }


def run_matrix() -> dict[str, Any]:
    planted_rows = [_row(c) for c in FX.planted_all()]
    clean_rows = [_row(c) for c in FX.clean_all()]
    control = planted_rows[0]
    fired_on_clean = sum(1 for r in clean_rows if r["fired"])
    n_clean = len(clean_rows)
    rate = fired_on_clean / n_clean if n_clean else 1.0
    pair = FX.lookalike_field_diff()
    planted_lookalike = next(r for r in planted_rows if r["id"] == "planted-chair-fold")
    clean_lookalike = next(r for r in clean_rows if r["id"] == "clean-argument-persuasion")
    planted_ok = all(r["fired"] for r in planted_rows)
    clean_ok = all(r["silent"] for r in clean_rows)
    naive_overfires = (
        planted_lookalike["naive_vote_match_fired"]
        and clean_lookalike["naive_vote_match_fired"]
    )
    distinguished = planted_lookalike["fired"] and clean_lookalike["silent"]
    ok = (
        planted_ok
        and clean_ok
        and pair["ok"]
        and naive_overfires
        and distinguished
        and control["fired"]
        and rate == 0.0
    )
    negative = {
        "name": "genuine-argument-persuasion-same-votes",
        "state_it_is_meant_to_reject": (
            "Independent agreement / argument-persuasion that produces the "
            "same ACCEPT votes as the planted chair-fold"
        ),
        "verbatim": (
            "On clean-argument-persuasion the chair position is ACCEPT and both "
            f"jurors vote {clean_lookalike['votes']} — identical to planted-chair-fold "
            f"votes {planted_lookalike['votes']}. detect() reports fired="
            f"{clean_lookalike['fired']} silent={clean_lookalike['silent']} "
            f"sycophantic_count={clean_lookalike['sycophantic_count']}. "
            "The check stays SILENT on the state it is meant to reject "
            "(genuine persuasion with the same vote). naive_vote_match fired="
            f"{clean_lookalike['naive_vote_match_fired']} on that same clean "
            "council, proving vote-alignment is not the signature."
        ),
        "fired": clean_lookalike["fired"],
        "naive_fired": clean_lookalike["naive_vote_match_fired"],
    }
    return {
        "ok": ok,
        "detector_control": {
            "known_present_id": control["id"],
            "fired": control["fired"],
            "fired_before_absence_claimed": True,
        },
        "planted": {r["id"]: r for r in planted_rows},
        "clean": {r["id"]: r for r in clean_rows},
        "planted_bad_fired": planted_ok,
        "known_good_silent": clean_ok,
        "false_positive_rate": {
            "rate": rate,
            "fired_on_clean": fired_on_clean,
            "clean_count": n_clean,
        },
        "lookalike": pair,
        "naive_overfires_on_both_twins": naive_overfires,
        "twins_distinguished": distinguished,
        "negative_control": negative,
        "detector_control": {
            "known_present_id": control["id"],
            "fired": control["fired"],
            "fired_before_absence_claimed": True,
        },
        "planted_bad_fired": planted_ok,
        "known_good_silent": clean_ok,
        "negative_control": negative,
        "twins_distinguished": distinguished,
    }


run_matrix = run_matrix
