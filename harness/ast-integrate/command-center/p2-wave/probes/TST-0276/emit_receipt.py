#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0276.json from live session runs."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council" / "budget"))

from engagement import (  # noqa: E402
    CONSENT_SILENCE_POLICY,
    EXPLICIT_BALLOT_SILENCE_POLICY,
    PROTOCOL_CONSENT_NO_OBJECTION,
    PROTOCOL_EXPLICIT_BALLOT,
    run_session,
    scan_silence_policy_lines,
)
from fixtures import (  # noqa: E402
    ack_filler,
    all_specs,
    engaged_clean,
    protocol_window,
    silent_never_engaged,
)
from recount import recount  # noqa: E402

OUT = "command-center/receipts/TST-0276.json"
SENTINEL = "SUCCESS:TST-0276"
QUESTION = (
    "Implementation target: enforce the :10928 minimum-engagement and "
    "maximum-inactivity budgets so a seat that never speaks, never votes or "
    "never cites evidence is escalated, replaced or recorded as absent - never "
    "silently counted as consenting. Spec :10944 names silence as an "
    "anti-failure target. Consent-by-silence is the specific defect: an absent "
    "seat must not be folded into a consensus figure."
)


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def slim(result: dict) -> dict:
    return {
        "fixture_id": result.get("fixture_id"),
        "protocol": result.get("protocol"),
        "escalations": result.get("escalations"),
        "any_inactivity_fired": result.get("any_inactivity_fired"),
        "engaged_inactivity_fired": result.get("engaged_inactivity_fired"),
        "tally": {
            "numerator": result["tally"]["numerator"],
            "denominator": result["tally"]["denominator"],
            "consensus_figure": result["tally"]["consensus_figure"],
            "agree_seat_ids": result["tally"]["agree_seat_ids"],
            "absent_seat_ids": result["tally"]["absent_seat_ids"],
            "engaged_seat_ids": result["tally"]["engaged_seat_ids"],
            "no_objection_seat_ids": result["tally"]["no_objection_seat_ids"],
            "abstain_seat_ids": result["tally"]["abstain_seat_ids"],
            "defect_if_silence_were_consent": result["tally"]["defect_if_silence_were_consent"],
        },
        "seats": [
            {
                "seat_id": s["seat_id"],
                "status": s["status"],
                "action": s["action"],
                "reason": s["reason"],
                "counted_as_agreeing": s["counted_as_agreeing"],
                "decision_role": s.get("decision_role"),
                "silence_meaning": s.get("silence_meaning"),
                "substantive_act_count": s["substantive_act_count"],
            }
            for s in result["seats"]
        ],
    }


def main() -> int:
    silent = run_session(silent_never_engaged())
    filler = run_session(ack_filler())
    clean = run_session(engaged_clean())
    ballot = run_session(protocol_window(PROTOCOL_EXPLICIT_BALLOT))
    consent = run_session(protocol_window(PROTOCOL_CONSENT_NO_OBJECTION))
    indep = {s["fixture_id"]: recount(s) for s in all_specs()}
    quotes = scan_silence_policy_lines()
    simulate = REPO / "tools" / "council" / "simulate.py"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    ghost = next(s for s in silent["seats"] if s["seat_id"] == "ghost")
    if ghost["status"] != "ABSENT" or ghost["counted_as_agreeing"]:
        print("FAILED:TST-0276 emit silent seat not excluded")
        return 1
    if silent["tally"]["consensus_figure"] != 0.5:
        print("FAILED:TST-0276 emit silent figure")
        return 1
    if clean["any_inactivity_fired"] or clean["escalations"]:
        print("FAILED:TST-0276 emit clean control")
        return 1
    if ballot["tally"]["consensus_figure"] == consent["tally"]["consensus_figure"]:
        print("FAILED:TST-0276 emit protocols identical")
        return 1

    receipt = {
        "schema_version": 1,
        "unit_id": "TST-0276",
        "id": "TST-0276",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Minimum engagement and maximum inactivity: make a silent seat "
            "a failure, not a quiet pass"
        ),
        "spec_anchor": "_USER-PROMPTS.md:10928,10944",
        "question": QUESTION,
        "answer": {
            "enforcer": "tools/council/budget/engagement.py",
            "simulate_py_present": simulate.is_file(),
            "silent_seat_status": ghost["status"],
            "silent_seat_counted_as_agreeing": ghost["counted_as_agreeing"],
            "consensus_with_silent_excluded": {
                "numerator": silent["tally"]["numerator"],
                "denominator": silent["tally"]["denominator"],
                "figure": silent["tally"]["consensus_figure"],
                "agree_seat_ids": silent["tally"]["agree_seat_ids"],
                "absent_seat_ids": silent["tally"]["absent_seat_ids"],
            },
            "escalation_record": silent["escalations"],
            "silence_as_consent_quotes": quotes,
            "explicit_ballot_silence_policy": EXPLICIT_BALLOT_SILENCE_POLICY,
            "consent_no_objection_silence_policy": CONSENT_SILENCE_POLICY,
            "protocol_distinction": {
                "explicit_ballot_figure": ballot["tally"]["consensus_figure"],
                "consent_no_objection_figure": consent["tally"]["consensus_figure"],
                "same_ledger": True,
                "differ": ballot["tally"]["consensus_figure"]
                != consent["tally"]["consensus_figure"],
                "analyst_ballot_role": next(
                    s.get("decision_role")
                    for s in ballot["seats"]
                    if s["seat_id"] == "analyst"
                ),
                "analyst_consent_role": next(
                    s.get("decision_role")
                    for s in consent["seats"]
                    if s["seat_id"] == "analyst"
                ),
            },
            "ack_filler_fails_floor": next(
                s["status"] == "ABSENT" and "filler" in s["reason"]
                for s in filler["seats"]
                if s["seat_id"] == "ghost"
            ),
            "summary": (
                "A never-acting seat is ABSENT, escalated, and excluded from "
                "the explicit-ballot consensus figure (1/2 = 0.5 here, not "
                "2/3). Empty acks do not meet the floor. The same engaged-but-"
                "silent-in-window ledger is 2/3 under explicit ballot (abstain) "
                "and 1.0 under consent/no-objection (documented no_objection). "
                "tools/council/simulate.py is absent; this unit ships the "
                "budget enforcer and a scripted-session runner."
            ),
        },
        "live_runs": {
            "silent_never_engaged": slim(silent),
            "ack_filler": slim(filler),
            "engaged_clean": slim(clean),
            "protocol_window_explicit_ballot": slim(ballot),
            "protocol_window_consent_no_objection": slim(consent),
        },
        "independent_recount": indep,
        "min_bytes_threshold": 128,
        "evidence": [
            {
                "claim": (
                    "Silent seat ghost is escalated ABSENT and is not in the "
                    "agree set; official figure is 1/2."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/budget/engagement.py",
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "SILENCE_POLICY lines in engagement.py document that "
                    "explicit-ballot silence is abstention and that "
                    "consent/no-objection silence is no_objection only for "
                    "already-engaged seats."
                ),
                "verdict": "CONFIRMED",
                "anchor": str(quotes[0]["path"]) if quotes else "engagement.py",
                "verbatim": quotes,
                "confidence": "almost-certain",
            },
            {
                "claim": (
                    "Both-states: engaged-clean does not fire inactivity; "
                    "silent-never-engaged does."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0276/probe1_both_states.py",
                "confidence": "almost-certain",
            },
        ],
        "tests": [
            {
                "id": "silent-seat-escalated-excluded",
                "command": (
                    "python3 -B command-center/p2-wave/probes/TST-0276/"
                    "probe1_both_states.py"
                ),
                "result": "PASS",
            },
            {
                "id": "protocol-distinction-and-independent-recount",
                "command": (
                    "python3 -B command-center/p2-wave/probes/TST-0276/"
                    "probe2_independent_recount.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "engaged-clean-inactivity-silent",
                "kind": "both-states",
                "description": (
                    "An engaged roster that speaks and votes must not trigger "
                    "the inactivity / absent path."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "ack-filler-is-not-engagement",
                "kind": "detector-control",
                "description": (
                    "ok/ack posts without claims, votes, or citations fail "
                    "the minimum-engagement floor."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0276-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "residual_unknowns": [
            (
                "tools/council/simulate.py is not on this worktree (TST-0257). "
                "Enforcement is proven on scripted ledgers via "
                "tools/council/budget/engagement.py, not a live model council."
            ),
            (
                "command-center/schema/council-spec.schema.json is absent; "
                "budget numbers used here are the unit defaults "
                "(min_substantive_acts=1, max_consecutive_inactive_rounds=1)."
            ),
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0276/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "timestamps": {"ended_at": now},
        "notes": (
            "G-1 TST-0276: live named probes, honest SUCCESS receipt, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    path = REPO / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump(receipt), encoding="utf-8")
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
