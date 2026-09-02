"""Shared IMP-0282 fixtures and live session runners."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from council.topology.chair import (  # noqa: E402
    ChairLedSession,
    expected_chair_sequence,
    independent_submission_check,
    power_probe,
    run_session,
)

ROSTER = ("alice", "bob", "cara", "drew")
DISSENTER = "drew"
N_ROUNDS = 8
MODULE = "tools/council/topology/chair.py"
RECEIPT = "command-center/receipts/IMP-0282.json"


def even_session() -> ChairLedSession:
    return run_session(ROSTER, N_ROUNDS, policy="even", dissenter_id=DISSENTER)


def skewed_session() -> ChairLedSession:
    return run_session(ROSTER, N_ROUNDS, policy="skewed", dissenter_id=DISSENTER)


def rotation_ok(session: ChairLedSession) -> dict[str, Any]:
    expected = expected_chair_sequence(ROSTER, N_ROUNDS, rotate_every=1)
    observed = list(session.chair_history[:N_ROUNDS])
    return {
        "expected": expected,
        "observed": observed,
        "pass": observed == expected,
    }


def unrecognized_still_present(session: ChairLedSession, participant_id: str) -> dict[str, Any]:
    art = session.artifact()
    journal = [s for s in session.submissions if s.participant_id == participant_id]
    rows = [
        row
        for row in art["submissions"]
        if isinstance(row, dict) and row.get("participant_id") == participant_id
    ]
    recs = [r for r in session.recognitions if r.participant_id == participant_id]
    return {
        "participant_id": participant_id,
        "journal_submissions": len(journal),
        "artifact_submissions": len(rows),
        "recognitions": len(recs),
        "all_present": len(journal) == len(rows) == N_ROUNDS,
        "suppressed_from_floor": len(recs) == 0,
        "pass": len(journal) == len(rows) == N_ROUNDS,
    }


def drop_unrecognized_mutant_fires(session: ChairLedSession) -> dict[str, Any]:
    """Negative control: an artifact that drops unrecognised rows must FAIL presence."""
    art = session.artifact()
    mutant = dict(art)
    mutant["submissions"] = [
        row for row in art["submissions"] if row.get("recognized_this_round")
    ]
    live = independent_submission_check(session.submissions, art)
    bad = independent_submission_check(session.submissions, mutant)
    return {
        "live_pass": bool(live["pass"]),
        "mutant_pass": bool(bad["pass"]),
        "mutant_missing": list(bad["missing_from_artifact"]),
        "fired_on_mutant": bad["pass"] is False,
        "silent_on_live": live["pass"] is True,
        "pass": live["pass"] is True and bad["pass"] is False,
    }


def evaluate_probe1() -> dict[str, Any]:
    powers = power_probe(ROSTER)
    even = even_session()
    rot = rotation_ok(even)
    dist = even.distribution()
    presence = independent_submission_check(even.submissions, even.artifact())
    mutant = drop_unrecognized_mutant_fires(even)
    shares = {p: dist[p]["recognition_share"] for p in ROSTER}
    recs = {p: dist[p]["recognitions"] for p in ROSTER}
    even_counts_balanced = all(recs[p] == N_ROUNDS // len(ROSTER) for p in ROSTER)
    ok = (
        bool(powers["pass"])
        and bool(rot["pass"])
        and bool(presence["pass"])
        and bool(mutant["pass"])
        and even_counts_balanced
        and presence["journal_count"] == N_ROUNDS * len(ROSTER)
    )
    return {
        "powers": powers,
        "rotation": rot,
        "recognition_counts": recs,
        "recognition_shares": shares,
        "presence": presence,
        "mutant_drop_unrecognized": mutant,
        "even_counts_balanced": even_counts_balanced,
        "pass": ok,
    }


def evaluate_probe2() -> dict[str, Any]:
    even = even_session()
    skew = skewed_session()
    even_g = even.capture_guard()
    skew_g = skew.capture_guard()
    drew = unrecognized_still_present(skew, DISSENTER)
    even_presence = independent_submission_check(even.submissions, even.artifact())
    skew_presence = independent_submission_check(skew.submissions, skew.artifact())
    fire_on_skew = skew_g.flagged is True and DISSENTER in skew_g.starved
    silent_on_even = even_g.flagged is False and even_g.starved == ()
    ok = (
        fire_on_skew
        and silent_on_even
        and bool(drew["pass"])
        and drew["suppressed_from_floor"] is True
        and bool(even_presence["pass"])
        and bool(skew_presence["pass"])
    )
    return {
        "even_guard": even_g.as_dict(),
        "skew_guard": skew_g.as_dict(),
        "fire_on_skew": fire_on_skew,
        "silent_on_even": silent_on_even,
        "dissenter_submissions": drew,
        "even_presence": even_presence,
        "skew_presence": skew_presence,
        "negative_control": (
            "On the captured-chair fixture (drew starved versus the fair "
            "schedule) the guard returns flagged=true. On the even-handed "
            "chair the guard returns flagged=false."
        ),
        "pass": ok,
    }
