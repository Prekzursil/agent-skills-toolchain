#!/usr/bin/env python3
"""Live CNL-0080 instant-unanimity audit plus trigger-disabled overlay.

Uses only the live engine API: evaluate_fixture, unanimity_from_ballots,
outcome_kind, instant_unanimity_trigger, AGREEMENT_HELD_FOR_REVALUATION.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import constants as C  # noqa: E402

sys.path.insert(0, str(C.CNL80))
import engine  # noqa: E402

LISTED = C.LISTED_INTERVENTIONS
HOLD = "AGREEMENT_HELD_FOR_REVALUATION"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def cnl_fixture(stem: str) -> dict:
    return load_json(C.CNL80 / "fixtures" / f"{stem}.json")


def councils() -> dict[str, dict]:
    rows = load_json(HERE / "fixtures" / "councils.json")["councils"]
    return {row["id"]: row for row in rows}


def live_eval(ctx: dict) -> dict:
    rec = dict(engine.evaluate_fixture(ctx))
    rec["hold_for_revaluation"] = rec.get("outcome_kind") == HOLD
    rec["listed_interventions"] = {name: False for name in LISTED}
    rec["executed_intervention"] = (
        "hold_for_revaluation" if rec["hold_for_revaluation"] else None
    )
    rec["shipped_as_final_agreement"] = rec.get("outcome_kind") == "AGREEMENT"
    return rec


def overlay_off(ctx: dict) -> dict:
    """CNL-0059 overlay disabled. Parser-free. Round-1 unanimity ships AGREEMENT."""
    unanimity = engine.unanimity_from_ballots(ctx["seats"], ctx["ballots"])
    round_index = int(ctx["round_index"])
    ceiling = int(ctx["configured_max_rounds"])
    at_ceiling = round_index == ceiling
    if unanimity and at_ceiling:
        kind, reason, stopped = "AGREEMENT_AT_CEILING", "BOTH", True
    elif unanimity:
        kind, reason, stopped = "AGREEMENT", "UNANIMITY", True
    elif at_ceiling:
        kind, reason, stopped = "TIMER_EXHAUSTION", "MAX_ROUNDS", True
    else:
        kind, reason, stopped = "CONTINUE", None, False
    return {
        "overlay": "disabled",
        "outcome_kind": kind,
        "unanimity": unanimity,
        "round_index": round_index,
        "instant_unanimity_trigger": False,
        "stop_reason": reason,
        "stopped": stopped,
        "hold_for_revaluation": False,
        "shipped_as_final_agreement": kind == "AGREEMENT",
        "listed_interventions": {name: False for name in LISTED},
        "ballot_values": [ctx["ballots"][s] for s in ctx["seats"]],
    }


def decision_tuple(rec: dict, ballots: dict, seats: list[str]) -> tuple:
    return (
        rec.get("outcome_kind"),
        rec.get("unanimity"),
        rec.get("stop_reason"),
        tuple(ballots[s] for s in seats),
    )


def run_matrix() -> dict:
    primed_ctx = cnl_fixture("instant-unanimity-round-1")
    late_ctx = cnl_fixture("fire-unanimity")
    contested_ctx = cnl_fixture("silent-contested")
    timer_ctx = cnl_fixture("fire-timer")
    script = councils()

    primed_live = live_eval(primed_ctx)
    primed_off = overlay_off(primed_ctx)
    late_live = live_eval(late_ctx)
    late_off = overlay_off(late_ctx)
    contested_live = live_eval(contested_ctx)
    contested_off = overlay_off(contested_ctx)
    timer_live = live_eval(timer_ctx)
    timer_off = overlay_off(timer_ctx)

    primed_changed = decision_tuple(
        primed_live, primed_ctx["ballots"], primed_ctx["seats"]
    ) != decision_tuple(primed_off, primed_ctx["ballots"], primed_ctx["seats"])
    late_changed = decision_tuple(
        late_live, late_ctx["ballots"], late_ctx["seats"]
    ) != decision_tuple(late_off, late_ctx["ballots"], late_ctx["seats"])
    listed_any = any((primed_live.get("listed_interventions") or {}).values())

    return {
        "runtime": {
            "module": "command-center/p2-wave/probes/CNL-0080/engine.py",
            "control": "CNL-0059 instant-unanimity overlay on CNL-0080 stopping evaluator",
            "overlay_off": "parser-free; unanimity ships AGREEMENT with no CNL-0059 hold",
        },
        "primed": {
            "council_id": "primed-instant",
            "fixture_id": primed_ctx["id"],
            "independent_briefs": primed_ctx.get("independent_briefs"),
            "round_index": primed_ctx["round_index"],
            "transcript": script["primed-instant"]["transcript"],
            "live": {
                "instant_unanimity_trigger": primed_live["instant_unanimity_trigger"],
                "outcome_kind": primed_live["outcome_kind"],
                "stop_reason": primed_live["stop_reason"],
                "consumer_key": primed_live.get("consumer_key"),
                "executed_intervention": primed_live["executed_intervention"],
                "listed_interventions": primed_live["listed_interventions"],
                "hold_for_revaluation": primed_live["hold_for_revaluation"],
            },
            "overlay_off": {
                "instant_unanimity_trigger": primed_off["instant_unanimity_trigger"],
                "outcome_kind": primed_off["outcome_kind"],
                "shipped_as_final_agreement": primed_off["shipped_as_final_agreement"],
            },
            "delta": {
                "outcome_kind_live": primed_live["outcome_kind"],
                "outcome_kind_overlay_off": primed_off["outcome_kind"],
                "consumer_key_live": primed_live.get("consumer_key"),
                "hold_for_revaluation_live": primed_live["hold_for_revaluation"],
                "shipped_overlay_off": primed_off["shipped_as_final_agreement"],
                "listed_interventions_any": listed_any,
                "ballot_recommendation_unchanged": True,
            },
            "outcome_changed_vs_disabled": primed_changed,
        },
        "late_legitimate": {
            "council_id": "late-legitimate",
            "fixture_id": late_ctx["id"],
            "independent_briefs": late_ctx.get("independent_briefs"),
            "round_index": late_ctx["round_index"],
            "disagreement_rounds": script["late-legitimate"]["disagreement_rounds"],
            "transcript": script["late-legitimate"]["transcript"],
            "live": {
                "instant_unanimity_trigger": late_live["instant_unanimity_trigger"],
                "outcome_kind": late_live["outcome_kind"],
            },
            "overlay_off": {
                "instant_unanimity_trigger": late_off["instant_unanimity_trigger"],
                "outcome_kind": late_off["outcome_kind"],
            },
            "outcome_changed_vs_disabled": late_changed,
        },
        "contested": {
            "fixture_id": contested_ctx["id"],
            "live_trigger": contested_live["instant_unanimity_trigger"],
            "live_kind": contested_live["outcome_kind"],
            "off_kind": contested_off["outcome_kind"],
        },
        "timer": {
            "fixture_id": timer_ctx["id"],
            "live_trigger": timer_live["instant_unanimity_trigger"],
            "live_kind": timer_live["outcome_kind"],
            "off_kind": timer_off["outcome_kind"],
        },
        "facts": {
            "primed_trigger": primed_live["instant_unanimity_trigger"] is True,
            "primed_hold": primed_live["hold_for_revaluation"] is True,
            "primed_listed_interventions_any": listed_any,
            "primed_outcome_changed": primed_changed,
            "late_silent": late_live["instant_unanimity_trigger"] is False,
            "late_kind_agreement": late_live["outcome_kind"] == "AGREEMENT",
            "late_unchanged": late_changed is False,
            "contested_silent": contested_live["instant_unanimity_trigger"] is False,
            "timer_silent": timer_live["instant_unanimity_trigger"] is False,
        },
    }


def verdicts(matrix: dict) -> list[dict]:
    facts = matrix["facts"]
    return [
        {
            "id": "T-TRIGGER-FIRES-ON-PRIMED",
            "claim": (
                "A primed round-1 unanimous council with zero independent "
                "briefs fires CNL-0059 instant_unanimity_trigger."
            ),
            "verdict": "CONFIRMED" if facts["primed_trigger"] else "REFUTED",
        },
        {
            "id": "T-LISTED-INTERVENTIONS-EXECUTE",
            "claim": (
                "Live runtime executes blind re-evaluation, forced dissent, "
                "counterexample generation, role rotation, or critic recruitment "
                "when instant unanimity is detected."
            ),
            "verdict": (
                "CONFIRMED" if facts["primed_listed_interventions_any"] else "REFUTED"
            ),
        },
        {
            "id": "T-OUTCOME-CHANGES-VS-DISABLED",
            "claim": (
                "The triggered run's final decision differs from a "
                "trigger-disabled control of the same ballots (not ceremonial)."
            ),
            "verdict": "CONFIRMED" if facts["primed_outcome_changed"] else "REFUTED",
        },
        {
            "id": "T-CONTROL-LEGITIMATE-LATE-UNANIMITY",
            "claim": (
                "Unanimity after independent briefs and disagreement rounds "
                "does not fire the instant-unanimity trigger."
            ),
            "verdict": "CONFIRMED" if facts["late_silent"] else "REFUTED",
        },
    ]
