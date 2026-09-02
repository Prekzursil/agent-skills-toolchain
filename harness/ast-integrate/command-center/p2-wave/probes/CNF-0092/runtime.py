"""Deterministic council run: vote, evaluate trigger, remediate if fired."""
from __future__ import annotations

import json
from typing import Any

import fixtures as F
import unanimity as U


def snapshot_from_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    votes = {p["id"]: str(p["vote"]) for p in fixture["participants"]}
    briefs = {p["id"]: dict(p.get("brief") or {}) for p in fixture["participants"]}
    return {
        "fixture_id": fixture["id"],
        "question": fixture["question"],
        "round_index": 1,
        "votes": votes,
        "briefs": briefs,
    }


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot_from_fixture(fixture)
    votes = dict(snap["votes"])
    n_briefs, n_evidence = U._brief_counts(snap["briefs"])
    audit: list[dict[str, Any]] = [
        {
            "event": U.EVENT_ROUND_ONE_VOTE,
            "fixture_id": fixture["id"],
            "round": 1,
            "votes": dict(votes),
            "independent_briefs_submitted": n_briefs,
            "evidence_nodes_cited": n_evidence,
        }
    ]
    trigger = U.evaluate_trigger(snap)
    if trigger["fired"]:
        audit.append(
            {
                "event": U.EVENT_TRIGGER,
                "fixture_id": fixture["id"],
                "fired": True,
                "reason": trigger["reason"],
                "threshold": trigger["threshold"],
                "metrics": trigger["metrics"],
            }
        )
        rem = U.remediate(snap, trigger)
        audit.extend(rem["audit_events"])
        transcript = rem["transcript"]
        final = rem["final_verdict"]
        extra = {
            "outcome_changed": rem["outcome_changed"],
            "independent_position_recorded": rem["independent_position_recorded"],
            "independent_positions": rem["independent_positions"],
            "remediation": rem["remediation"],
        }
    else:
        audit.append(
            {
                "event": U.EVENT_SILENT,
                "fixture_id": fixture["id"],
                "fired": False,
                "reason": trigger["reason"],
                "threshold": trigger["threshold"],
                "metrics": trigger["metrics"],
            }
        )
        transcript = [
            {
                "round": 1,
                "kind": "vote",
                "blind": False,
                "votes": dict(votes),
                "independent_briefs": n_briefs,
            }
        ]
        final = U.majority(votes)
        extra = {
            "outcome_changed": False,
            "independent_position_recorded": False,
            "independent_positions": [],
            "remediation": "not-applicable:trigger-silent",
        }

    expected = bool(fixture["expected_trigger"])
    observed = bool(trigger["fired"])
    return {
        "fixture_id": fixture["id"],
        "fixture_class": fixture["class"],
        "title": fixture["title"],
        "question": fixture["question"],
        "completed": True,
        "expected_trigger": expected,
        "trigger_fired": observed,
        "trigger_match": expected == observed,
        "trigger": trigger,
        "votes": dict(votes),
        "round_one_votes": dict(votes),
        "transcript": transcript,
        "audit_events": audit,
        "final_verdict": final,
        **extra,
    }


def run_all() -> dict[str, Any]:
    runs = [run_fixture(fx) for fx in F.ALL_FIXTURES]
    by = {r["fixture_id"]: r for r in runs}
    instant = by[F.INSTANT_UNANIMITY["id"]]
    contested = by[F.CONTESTED["id"]]
    legitimate = by[F.POST_BRIEF_UNANIMITY["id"]]
    trigger_in_log = any(
        e.get("event") == U.EVENT_TRIGGER for e in instant["audit_events"]
    )
    blind_in_transcript = any(
        t.get("kind") == "blind_re_evaluation" for t in instant["transcript"]
    )
    return {
        "runs": runs,
        "by_id": by,
        "instant": instant,
        "contested": contested,
        "legitimate": legitimate,
        "instant_fired": bool(instant["trigger_fired"]),
        "contested_silent": not bool(contested["trigger_fired"]),
        "legitimate_silent": not bool(legitimate["trigger_fired"]),
        "trigger_recorded_in_audit_log": trigger_in_log,
        "blind_re_evaluation_in_transcript": blind_in_transcript,
        "independent_position_recorded": bool(
            instant.get("independent_position_recorded")
        ),
        "all_expected": all(r["trigger_match"] for r in runs),
    }


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "instant_fired": result["instant_fired"],
        "contested_silent": result["contested_silent"],
        "legitimate_silent": result["legitimate_silent"],
        "trigger_recorded_in_audit_log": result["trigger_recorded_in_audit_log"],
        "blind_re_evaluation_in_transcript": result["blind_re_evaluation_in_transcript"],
        "independent_position_recorded": result["independent_position_recorded"],
        "all_expected": result["all_expected"],
        "instant_votes": result["instant"]["round_one_votes"],
        "contested_votes": result["contested"]["round_one_votes"],
        "legitimate_votes": result["legitimate"]["round_one_votes"],
        "threshold": dict(U.THRESHOLD),
    }


if __name__ == "__main__":
    doc = compact(run_all())
    print(json.dumps(doc, indent=2, sort_keys=True))
