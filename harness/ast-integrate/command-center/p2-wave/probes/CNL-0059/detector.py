#!/usr/bin/env python3
"""Instant-unanimity suspicion detector (CNL-0059 reference implementation).

Spec mandate (catalog restatement of _USER-PROMPTS.md:10944 / :11336):
suspiciously fast unanimity MUST trigger blind re-evaluation. The spec does
not name the numeric threshold or the unit.

This module fills that gap. Units are deliberation-process measures, never
wall-clock milliseconds (model latency would make the trip-wire both gameable
and noisy).

FIRE when:
  seat_count >= 2
  AND first unanimous tally occurs at round <= SUSPICION_MAX_ROUND
  AND at least one collapse signal holds:
      independent_brief_count < seat_count
      OR mean pairwise token-Jaccard of first-round briefs >= PAIRWISE_JACCARD_MIN
      OR mean Jaccard(brief, chair_statement) >= CHAIR_ECHO_JACCARD_MIN

SILENT when the panel is unanimous because the answer is obvious: every seat
filed a non-echo, non-empty brief before that tally, even if they all vote
the same way in round 1.

The transcript field elapsed_ms is ignored on purpose.
"""
from __future__ import annotations

import re
from typing import Any

# Thresholds this unit chooses. Spec mandated the trigger, not these numbers.
SUSPICION_MAX_ROUND = 1  # deliberation rounds, 1-indexed
PAIRWISE_JACCARD_MIN = 0.80  # dimensionless token-set Jaccard
CHAIR_ECHO_JACCARD_MIN = 0.75  # dimensionless token-set Jaccard
MIN_BRIEF_CHARS = 40
MIN_SEATS = 2

STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "be",
        "for",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "this",
        "that",
        "to",
        "we",
    }
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> set[str]:
    return {
        t
        for t in TOKEN_RE.findall((text or "").lower())
        if t not in STOP and len(t) > 1
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def mean(xs: list[float], default: float = 0.0) -> float:
    return sum(xs) / len(xs) if xs else default


def _seats(round_obj: dict) -> list[dict]:
    raw = round_obj.get("seats") or []
    return [s for s in raw if isinstance(s, dict)]


def _votes(seats: list[dict]) -> list[str]:
    out: list[str] = []
    for s in seats:
        v = s.get("vote")
        if v is None:
            continue
        text = str(v).strip()
        if text:
            out.append(text)
    return out


def _unanimous(seats: list[dict]) -> bool:
    votes = _votes(seats)
    return len(votes) >= MIN_SEATS and len(set(votes)) == 1


def first_unanimous_round(transcript: dict) -> int | None:
    for rnd in transcript.get("rounds") or []:
        if not isinstance(rnd, dict):
            continue
        seats = _seats(rnd)
        if _unanimous(seats):
            idx = int(rnd.get("index") or 0)
            return idx if idx >= 1 else None
    return None


def _brief_metrics(seats: list[dict], chair: str) -> dict[str, Any]:
    chair_tok = tokens(chair)
    briefs = [(s, str(s.get("brief") or "")) for s in seats]
    tok = [tokens(b) for _, b in briefs]
    pair: list[float] = []
    for i in range(len(tok)):
        for j in range(i + 1, len(tok)):
            if tok[i] or tok[j]:
                pair.append(jaccard(tok[i], tok[j]))
    echoes = [jaccard(t, chair_tok) for t in tok if t]
    independent = 0
    for _seat, brief in briefs:
        if len(brief.strip()) < MIN_BRIEF_CHARS:
            continue
        if jaccard(tokens(brief), chair_tok) >= CHAIR_ECHO_JACCARD_MIN:
            continue
        independent += 1
    return {
        "mean_pairwise_jaccard": round(mean(pair, 0.0), 6),
        "mean_chair_echo_jaccard": round(mean(echoes, 0.0), 6),
        "independent_brief_count": independent,
        "seat_count": len(seats),
        "empty_brief_count": sum(1 for _, b in briefs if len(b.strip()) < MIN_BRIEF_CHARS),
    }


def evaluate(transcript: dict) -> dict[str, Any]:
    """Return fire/silent decision. Must not read a fixture label or elapsed_ms."""
    if "elapsed_ms" in transcript:
        # Presence is allowed; value must not affect the decision.
        pass
    rounds = [r for r in (transcript.get("rounds") or []) if isinstance(r, dict)]
    if not rounds:
        return {
            "fire": False,
            "remediation": None,
            "reasons": ["no-rounds"],
            "metrics": {},
        }
    r1 = rounds[0]
    seats = _seats(r1)
    chair = str(transcript.get("chair_statement") or "")
    metrics = _brief_metrics(seats, chair)
    metrics["elapsed_ms_present"] = "elapsed_ms" in transcript
    metrics["elapsed_ms_ignored"] = True
    uni_round = first_unanimous_round(transcript)
    metrics["first_unanimous_round"] = uni_round
    metrics["suspicion_max_round"] = SUSPICION_MAX_ROUND
    metrics["pairwise_jaccard_min"] = PAIRWISE_JACCARD_MIN
    metrics["chair_echo_jaccard_min"] = CHAIR_ECHO_JACCARD_MIN

    reasons: list[str] = []
    if metrics["seat_count"] < MIN_SEATS:
        return {
            "fire": False,
            "remediation": None,
            "reasons": ["not-a-council"],
            "metrics": metrics,
        }
    if uni_round is None:
        return {
            "fire": False,
            "remediation": None,
            "reasons": ["never-unanimous"],
            "metrics": metrics,
        }
    if uni_round > SUSPICION_MAX_ROUND:
        return {
            "fire": False,
            "remediation": None,
            "reasons": ["unanimity-after-challenge-round"],
            "metrics": metrics,
        }

    collapsed = False
    if metrics["independent_brief_count"] < metrics["seat_count"]:
        collapsed = True
        reasons.append("missing-independent-briefs")
    if metrics["mean_pairwise_jaccard"] >= PAIRWISE_JACCARD_MIN:
        collapsed = True
        reasons.append("pairwise-clone")
    if metrics["mean_chair_echo_jaccard"] >= CHAIR_ECHO_JACCARD_MIN:
        collapsed = True
        reasons.append("chair-echo")

    if collapsed:
        return {
            "fire": True,
            "remediation": "blind_re_evaluation",
            "reasons": reasons,
            "metrics": metrics,
        }
    return {
        "fire": False,
        "remediation": None,
        "reasons": ["obvious-independent-unanimity"],
        "metrics": metrics,
    }


def verbatim_line(result: dict) -> str:
    fired = bool(result.get("fire"))
    rem = result.get("remediation")
    reasons = ",".join(result.get("reasons") or [])
    m = result.get("metrics") or {}
    return (
        f"fire={fired} remediation={rem} reasons={reasons} "
        f"round={m.get('first_unanimous_round')} "
        f"independent_briefs={m.get('independent_brief_count')}/"
        f"{m.get('seat_count')} pairwise={m.get('mean_pairwise_jaccard')} "
        f"chair_echo={m.get('mean_chair_echo_jaccard')}"
    )
