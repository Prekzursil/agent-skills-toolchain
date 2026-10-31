"""Conflict-of-interest recusal for council tallies (TST-0271)."""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping

SCHEME_ID = "coi-recusal-v1"
KINDS = ("authored_the_artifact", "vendor_under_evaluation", "same_partition")


class ConflictError(Exception):
    pass


def naive_count_all(ballots: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for b in ballots:
        counts[str(b.get("choice"))] += 1
    return dict(counts)


def _conflicted_seats(seats: Iterable[Mapping[str, Any]], artifact: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    authors = {str(x) for x in (artifact.get("authors") or [])}
    owner = str(artifact.get("proposal_owner_id") or "")
    vendor = str(artifact.get("vendor_under_evaluation") or "")
    art_id = str(artifact.get("artifact_id") or "")
    out: dict[str, dict[str, Any]] = {}
    for seat in seats:
        if "conflicts" not in seat:
            raise ConflictError("conflicts field missing")
        sid = str(seat.get("seat_id") or "")
        reasons = []
        sources = []
        for c in seat.get("conflicts") or []:
            kind = str(c.get("kind") or "")
            if kind == "authored_the_artifact" and (
                c.get("artifact_id") == art_id or sid in authors or sid == owner
            ):
                reasons.append(kind)
                sources.append("declared")
        if sid in authors or sid == owner:
            if "authored_the_artifact" not in reasons:
                reasons.append("authored_the_artifact")
                sources.append("provenance")
        if vendor and str(seat.get("vendor") or "") == vendor:
            reasons.append("vendor_under_evaluation")
            sources.append("declared" if seat.get("conflicts") else "hidden")
        if reasons:
            out[sid] = {"kinds": reasons, "sources": sources, "seat": dict(seat)}
    return out


def _tally(
    seats: Iterable[Mapping[str, Any]],
    artifact: Mapping[str, Any],
    ballots: Iterable[Mapping[str, Any]],
    *,
    recuse: bool,
) -> dict[str, Any]:
    conflicted = _conflicted_seats(seats, artifact)
    counting: list[str] = []
    excluded: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    ballots = list(ballots)
    for b in ballots:
        sid = str(b.get("seat_id") or "")
        if recuse and sid in conflicted:
            info = conflicted[sid]
            kinds = info["kinds"]
            src = ",".join(info["sources"])
            audit = f"CONFLICT {sid} kind={kinds[0]} {src}"
            excluded.append(
                {
                    "seat_id": sid,
                    "choice": b.get("choice"),
                    "audit": audit,
                    "sources": info["sources"],
                    "kinds": info["kinds"],
                    "counting": False,
                    "weight": 0,
                }
            )
            continue
        counting.append(sid)
        counts[str(b.get("choice"))] += 1
    return {
        "counts": dict(counts),
        "n_submitted": len(ballots),
        "n_counting": len(counting),
        "n_excluded": len(excluded),
        "counting_seat_ids": counting,
        "excluded_seat_ids": [e["seat_id"] for e in excluded],
        "excluded": excluded,
        "scheme": SCHEME_ID,
    }


def enforce(seats, artifact, ballots) -> dict[str, Any]:
    return _tally(seats, artifact, ballots, recuse=True)


def warning_only_mutant(seats, artifact, ballots) -> dict[str, Any]:
    tally = _tally(seats, artifact, ballots, recuse=False)
    tally["warning"] = "conflict noted but ballot still counted"
    return tally


def assert_no_conflicted_counting_vote(tally: Mapping[str, Any]) -> None:
    excluded = set(tally.get("excluded_seat_ids") or [])
    counting = set(tally.get("counting_seat_ids") or [])
    if excluded & counting:
        raise ConflictError("conflicted seat still counting")
    if tally.get("warning") and not excluded:
        raise ConflictError("warning-only mutant kept conflicted ballot")
    for row in tally.get("excluded") or []:
        if row.get("counting") is True or int(row.get("weight") or 0) != 0:
            raise ConflictError("excluded row still weighted")
        if "CONFLICT" not in str(row.get("audit") or ""):
            raise ConflictError("excluded row missing CONFLICT audit")
