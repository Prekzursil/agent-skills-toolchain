#!/usr/bin/env python3
"""CNL-0057 mechanical core: when a vote manufactures a number that is not a finding.

A vote is the wrong closing procedure when the object of the council is not a
preference among valid options. In those cases plurality/mean still emit a
winner or a center, which is a social statistic, not the missing fact.

Synthesis-only never emits `winner`. It owes the reader live hypotheses, seat
provenance, a census labeled as census, and the next measurement that would
settle the remainder.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Decision classes where taking a vote is actively harmful: the tally is a
# manufactured number (or a manufactured unique cause) that does not exist as
# a finding of the object domain.
VOTE_HARMFUL = frozenset(
    {
        "diagnosis",
        "scalar_estimate",
        "evidence_interpretation",
        "meaning_of_text",
        "incommensurable_synthesis",
        "mixed_unsplit",
    }
)

# Decision classes where a vote is a legitimate aggregation of preferences.
VOTE_OK = frozenset(
    {
        "preference_choice",
        "resource_allocation",
        "procedure_selection",
    }
)

# What the detector is built to reject. Quoted verbatim by probe2.
REJECTS = (
    "vote-as-decision on a vote-harmful decision_class "
    "(plurality winner or mean scalar emitted as the council decision)"
)
FIRE = "FIRE manufactured_tally"
SILENT = "SILENT"

SYNTHESIS_OBLIGATIONS = (
    "live_hypotheses",
    "seat_provenance",
    "census_not_winner",
    "no_tally_statement",
    "dissent_preserved",
    "next_measurement",
)


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fixture {name} is not an object")
    return data


def ballot_fingerprint(session: dict[str, Any]) -> str:
    ballots = list(session.get("ballots") or [])
    canonical = json.dumps(ballots, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify(session: dict[str, Any]) -> str:
    dc = str(session.get("decision_class") or "")
    if dc in VOTE_HARMFUL:
        return "vote_harmful"
    if dc in VOTE_OK:
        return "vote_ok"
    raise ValueError(f"unknown decision_class {dc!r}")


def plurality(session: dict[str, Any]) -> dict[str, Any]:
    ballots = list(session.get("ballots") or [])
    if not ballots:
        raise ValueError("no ballots")
    counts = Counter(str(b["choice"]) for b in ballots)
    top_n = counts.most_common(1)[0][1]
    winners = sorted(k for k, v in counts.items() if v == top_n)
    return {
        "kind": "vote",
        "tally": dict(sorted(counts.items())),
        "winner": winners[0] if len(winners) == 1 else None,
        "tied_winners": winners if len(winners) != 1 else [],
        "n_ballots": len(ballots),
    }


def mean_scalar(session: dict[str, Any]) -> dict[str, Any]:
    ballots = list(session.get("ballots") or [])
    values = [float(b["value"]) for b in ballots]
    manufactured = sum(values) / float(len(values))
    held = sorted(set(values))
    return {
        "kind": "vote",
        "held_values": held,
        "manufactured_scalar": manufactured,
        "held_by_any_seat": manufactured in set(values),
        "n_ballots": len(ballots),
    }


def vote(session: dict[str, Any]) -> dict[str, Any]:
    """Closing procedure that emits a decision-tally. Harmful on VOTE_HARMFUL."""
    out = plurality(session)
    if str(session.get("decision_class") or "") == "scalar_estimate":
        out.update(mean_scalar(session))
        out["kind"] = "vote"
    return out


def synthesis(session: dict[str, Any]) -> dict[str, Any]:
    """Closing procedure that refuses a winner. Census is descriptive only."""
    ballots = list(session.get("ballots") or [])
    claims = []
    for b in ballots:
        claim: Any = b.get("value") if "value" in b else b.get("choice")
        claims.append(
            {
                "seat": b["seat"],
                "claim": claim,
                "evidence_hash": b.get("evidence_hash"),
            }
        )
    keys = [str(c["claim"]) for c in claims]
    census = dict(sorted(Counter(keys).items()))
    live = sorted(set(keys))
    return {
        "kind": "synthesis_only",
        "tally_forbidden": True,
        "winner": None,
        "live_hypotheses": live,
        "census": census,
        "census_label": "census_not_vote_outcome",
        "claims": claims,
        "owed": list(SYNTHESIS_OBLIGATIONS),
        "no_tally_statement": (
            "No vote was taken. A tally would manufacture a unique cause or a "
            "center that is not a finding of this decision_class."
        ),
        "next_measurement": session.get(
            "next_measurement",
            "name the observation that would drop a live hypothesis",
        ),
    }


def attribute_reason(session_a: dict[str, Any], session_b: dict[str, Any]) -> str:
    """Disagreement is 'method' only when the ballot bytes are identical."""
    if ballot_fingerprint(session_a) != ballot_fingerprint(session_b):
        return "participants"
    return "method"


def methods_disagree(session: dict[str, Any]) -> dict[str, Any]:
    v = vote(session)
    s = synthesis(session)
    # Same seats and ballots; two procedures. Vote names a winner (or a mean
    # no seat held). Synthesis refuses winner and keeps the live set.
    if str(session.get("decision_class") or "") == "scalar_estimate":
        manufactured = v.get("manufactured_scalar")
        held = set(v.get("held_values") or [])
        disagree = manufactured not in held
        detail = "mean_not_in_held_values"
    else:
        vote_winner = v.get("winner")
        live = list(s.get("live_hypotheses") or [])
        disagree = vote_winner is not None and (
            s.get("winner") is None or live != [vote_winner]
        )
        detail = "vote_winner_hides_live_set"
    reason = "method" if disagree else "none"
    return {
        "disagree": disagree,
        "reason": reason,
        "detail": detail,
        "ballot_fingerprint": ballot_fingerprint(session),
        "vote": v,
        "synthesis": s,
    }


def detect(session: dict[str, Any]) -> dict[str, Any]:
    """FIRE iff a vote-harmful class is closed with method=vote."""
    kind = classify(session)
    method = str(session.get("method") or "")
    if kind == "vote_harmful" and method == "vote":
        return {
            "fires": True,
            "output": FIRE,
            "code": "manufactured_tally",
            "rejects": REJECTS,
            "decision_class": session.get("decision_class"),
            "method": method,
        }
    return {
        "fires": False,
        "output": SILENT,
        "code": "ok",
        "rejects": REJECTS,
        "decision_class": session.get("decision_class"),
        "method": method,
    }
