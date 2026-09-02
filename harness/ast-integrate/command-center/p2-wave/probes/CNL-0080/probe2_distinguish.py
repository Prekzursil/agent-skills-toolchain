#!/usr/bin/env python3
"""Probe 2: independent re-tabulation of timer vs unanimity distinguishability.

Does not trust probe1's narrative. Recomputes the four-row OR truth table from
raw ballots + round_index with a parser-free predicate, then checks the
negative control: a consumer that treats stopped as unanimous must FIRE on the
timer fixture and stay SILENT on genuine agreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from a10_grammar import CNL_0080_EXPR  # noqa: E402
from engine import (  # noqa: E402
    AGREEMENT,
    CONTINUE,
    TIMER_EXHAUSTION,
    bind_tautology,
    evaluate_fixture,
    naive_consumer_treats_stop_as_unanimity,
    overclaim_detector,
    unanimity_from_ballots,
)
from fixtures_lib import by_id, load_all  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0080-executable-stopping-example-unanimity-true-or-max-rounds-1.schema.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0080-probe2 {msg}")
    return 1


def independent_pred(unanimity: bool, round_index: int) -> bool:
    """Parser-free OR. Mechanically different from eval_ast."""
    return bool(unanimity) or (int(round_index) == 12)


def independent_outcome(unanimity: bool, round_index: int) -> dict:
    u = bool(unanimity)
    t = int(round_index) == 12
    if not (u or t):
        return {
            "stopped": False,
            "outcome_kind": CONTINUE,
            "stop_reason": None,
            "unanimity": u,
        }
    if u and t:
        return {
            "stopped": True,
            "outcome_kind": "AGREEMENT_AT_CEILING",
            "stop_reason": "BOTH",
            "unanimity": u,
        }
    if u:
        return {
            "stopped": True,
            "outcome_kind": AGREEMENT,
            "stop_reason": "UNANIMITY",
            "unanimity": u,
        }
    return {
        "stopped": True,
        "outcome_kind": TIMER_EXHAUSTION,
        "stop_reason": "MAX_ROUNDS",
        "unanimity": u,
    }


def main() -> int:
    rows = []
    for fx in load_all():
        u = unanimity_from_ballots(fx["seats"], fx["ballots"])
        pred = independent_pred(u, fx["round_index"])
        indep = independent_outcome(u, fx["round_index"])
        live = evaluate_fixture(fx)
        # Instant-unanimity is AGREEMENT in the parser-free table; live engine
        # overlays CNL-0059 and holds finalization. That overlay is required.
        if fx["id"] == "instant-unanimity-round-1":
            match = (
                live.get("expression_true") is True
                and live.get("unanimity") is True
                and live.get("outcome_kind") == "AGREEMENT_HELD_FOR_REVALUATION"
                and live.get("instant_unanimity_trigger") is True
                and indep["outcome_kind"] == AGREEMENT
            )
        else:
            match = (
                live.get("expression_true") is pred
                and live.get("unanimity") is u
                and live.get("outcome_kind") == indep["outcome_kind"]
                and live.get("stop_reason") == indep["stop_reason"]
            )
        rows.append(
            {
                "id": fx["id"],
                "computed_unanimity": u,
                "round_index": fx["round_index"],
                "independent_true": pred,
                "live_true": live.get("expression_true"),
                "independent_kind": indep["outcome_kind"],
                "live_kind": live.get("outcome_kind"),
                "match": match,
            }
        )
        print(
            f"recount id={fx['id']} u={u} round={fx['round_index']} "
            f"indep_true={pred} live_true={live.get('expression_true')} "
            f"indep_kind={indep['outcome_kind']} live_kind={live.get('outcome_kind')} "
            f"match={match}"
        )
        print("VERBATIM live " + json.dumps(live, sort_keys=True, default=str))

    if any(not r["match"] for r in rows):
        return fail("independent recount disagrees with live engine")

    timer = evaluate_fixture(by_id("fire-timer"))
    agree = evaluate_fixture(by_id("fire-unanimity"))
    if timer["consumer_key"] == agree["consumer_key"]:
        return fail("consumer_key collision timer vs agreement")
    if timer["outcome_kind"] == agree["outcome_kind"]:
        return fail("outcome_kind not distinguishable")
    if timer["unanimity"] is not False:
        return fail("timer record reports unanimity")
    if agree["unanimity"] is not True:
        return fail("agreement record lost unanimity")

    nc_timer = overclaim_detector(timer, naive_consumer_treats_stop_as_unanimity(timer))
    nc_agree = overclaim_detector(agree, naive_consumer_treats_stop_as_unanimity(agree))
    print("VERBATIM negative_control_timer " + json.dumps(nc_timer, sort_keys=True))
    print("VERBATIM negative_control_agree " + json.dumps(nc_agree, sort_keys=True))
    if nc_timer.get("fired") is not True:
        return fail("negative control silent on timer-as-unanimity overclaim")
    if nc_agree.get("fired") is not False:
        return fail("negative control FIRED on genuine agreement (false positive)")

    taut = evaluate_fixture(by_id("silent-contested"), bind=bind_tautology)
    print("VERBATIM tautology_bind " + json.dumps(taut, sort_keys=True, default=str))
    if taut.get("rejected") is not True:
        return fail("tautology bind of max_rounds to configured ceiling was accepted")

    if not ART.is_file():
        return fail("catalog artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    answer = doc.get("answer") or {}
    if answer.get("timer_distinguishable_from_unanimity") is not True:
        return fail("artifact does not record distinguishability")
    if (doc.get("expression") or {}).get("verbatim") != CNL_0080_EXPR:
        return fail("artifact expression drift")
    print(
        "negative_control: FIRE on timer-overclaim, SILENT on genuine agreement; "
        f"tautology_rejected={taut.get('rejected')}"
    )
    print("SUCCESS:CNL-0080-probe2 independent recount distinguishability")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
