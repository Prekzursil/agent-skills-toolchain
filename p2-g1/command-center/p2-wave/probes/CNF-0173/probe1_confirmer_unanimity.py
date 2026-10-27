#!/usr/bin/env python3
"""Probe 1: confirmer-authored fast-unanimity vs live antifail bind.

Requires a named control observable (re-eval round or recruited critic) from
the confirmer oracle, a live-bind attempt, and an honest non-BLOCKED receipt
that does not claim a production firing that did not happen.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import scenarios as S  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0173.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0173-probe1 {msg}")
    return 1


def main() -> int:
    sc = S.seawall_clone_panel()
    S.assert_not_reused(sc)
    for needle in S.FORBIDDEN_REUSE_SUBSTRINGS:
        if needle in sc["id"].lower():
            return fail(f"reused fixture token {needle}")

    live = H.bind_live()
    ev = H.evaluate_oracle(sc)
    instant = ev["instant_unanimity"]
    print(
        json.dumps(
            {
                "probe": "probe1-confirmer-unanimity",
                "unit_id": "CNF-0173",
                "scenario_id": sc["id"],
                "author": sc["author"],
                "oracle_instant_fired": instant["fired"],
                "oracle_controls": ev["controls_fired"],
                "observable": instant.get("observable"),
                "live_any_present": live["any_module_present"],
                "live_any_fired": live["any_live_control_fired"],
                "live_unanimity_present": live["modules"]["unanimity"]["present"],
            },
            sort_keys=True,
        )
    )
    if not instant["fired"]:
        return fail("confirmer seawall scenario did not trip instant_unanimity oracle")
    obs = instant.get("observable") or {}
    if not obs.get("reevaluation_round_id"):
        return fail("no re-evaluation round id in observable")
    if not obs.get("recruited_critic"):
        return fail("no recruited critic identity in observable")
    if obs.get("kind") != "blind_re_evaluation":
        return fail("observable kind is not blind_re_evaluation")
    if not obs.get("second_pass_changed_outcome"):
        return fail("planted wrong consensus was not overturned on second pass")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0173":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:CNF-0173" not in text:
        return fail("sentinel-absent")
    if not (doc.get("source_probe") or {}).get("fingerprint"):
        return fail("empty source_probe")
    art_obs = doc.get("observable") or {}
    if art_obs.get("reevaluation_round_id") != obs.get("reevaluation_round_id"):
        return fail("artifact observable round id mismatch")
    if art_obs.get("recruited_critic") != obs.get("recruited_critic"):
        return fail("artifact critic mismatch")
    live_art = (doc.get("live_bind") or {}).get("any_module_present")
    if bool(live_art) != bool(live["any_module_present"]):
        return fail("artifact live_bind present flag mismatch")
    if live["any_live_control_fired"] and doc.get("named_control_scope") != "live-production":
        return fail("live fired but artifact did not claim live-production scope")
    if (not live["any_live_control_fired"]) and doc.get("named_control_scope") == "live-production":
        return fail("artifact overclaims live-production firing")
    if doc.get("verdict") == "CONFIRMED" and not live["any_live_control_fired"]:
        return fail("CONFIRMED without a live control firing (overclaim)")

    print(
        "control=instant_unanimity "
        f"round={obs.get('reevaluation_round_id')} "
        f"critic={obs.get('recruited_critic')} "
        f"live_present={live['any_module_present']} "
        f"verdict={doc.get('verdict')}"
    )
    print("SUCCESS:CNF-0173-probe1 confirmer unanimity scenario and honest live bind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
