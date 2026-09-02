"""Minimum-engagement floor detector for council transcripts.

Distinguishes a structured nothing-to-add yield from disengagement.
Fires on filler-masquerade, consent-by-silence, no speech-act, or
inactivity-without-yield. Silent when every seat either contributed
substance or issued a structured yield, and no seat is counted as
consenting without an explicit vote.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

YIELD_ACTS = frozenset({"YIELD", "PASS"})
YIELD_REASONS = frozenset(
    {
        "no-new-information",
        "already-stated-by-peer",
        "outside-competence",
        "awaiting-evidence",
    }
)
VOTE_VALUES = frozenset({"AYE", "NAY", "ABSTAIN"})
FILLER_BODIES = frozenset(
    {
        "+1",
        "agreed",
        "agree",
        "ok",
        "okay",
        "lgtm",
        "ack",
        "thanks",
        "yes",
        "noted",
        "same",
        "this",
        "i agree",
        "sounds good",
    }
)


def load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES / name
    return json.loads(path.read_text(encoding="utf-8"))


def classify(turn: dict[str, Any] | None) -> str:
    if not turn:
        return "ABSENT"
    if turn.get("absent") is True:
        return "ABSENT"
    act = str(turn.get("speech_act") or "").upper().strip()
    body = " ".join(str(turn.get("body") or "").split()).strip()
    body_l = body.lower()

    if act in {"", "SILENCE"} and not body:
        return "ABSENT"

    if act in YIELD_ACTS:
        reason = str(turn.get("reason_code") or "")
        ref = str(turn.get("referent_id") or "")
        if reason in YIELD_REASONS and ref:
            return "STRUCTURED_YIELD"
        return "FILLER"

    if act == "VOTE":
        vote = str(turn.get("vote") or "").upper()
        rationale = str(turn.get("rationale") or body)
        if vote in VOTE_VALUES and len(rationale.split()) >= 4:
            return "SUBSTANTIVE"
        return "FILLER"

    if act in {"CLAIM", "OBJECT", "CITE"}:
        has_struct = bool(
            turn.get("claims") or turn.get("objections") or turn.get("citations")
        )
        if has_struct and len(body.split()) >= 4:
            return "SUBSTANTIVE"
        return "FILLER"

    if act == "ACK" or body_l in FILLER_BODIES:
        return "FILLER"
    if not body:
        return "ABSENT"
    return "FILLER"


def _explicit_vote(turn: dict[str, Any], kind: str) -> str | None:
    vote = str(turn.get("vote") or "").upper()
    if kind != "SUBSTANTIVE":
        return None
    if str(turn.get("speech_act") or "").upper() == "VOTE" and vote in VOTE_VALUES:
        return vote
    if vote in VOTE_VALUES:
        return vote
    return None


def scan(fixture: dict[str, Any]) -> dict[str, Any]:
    seats = list(fixture["seats"])
    rounds = list(fixture["rounds"])
    min_speech = int(fixture.get("min_speech_acts", 1))
    max_inact = int(fixture.get("max_inactivity", 2))
    agreeing = set(fixture.get("consensus", {}).get("agreeing") or [])

    per: dict[str, dict[str, Any]] = {
        s: {
            "substantive": 0,
            "structured_yield": 0,
            "filler": 0,
            "absent": 0,
            "classes": [],
            "explicit_vote": None,
            "last_speech_round": 0,
            "reasons": [],
        }
        for s in seats
    }
    n_rounds = len(rounds)

    for rnd in rounds:
        rno = int(rnd["round"])
        seen: set[str] = set()
        for turn in rnd.get("turns") or []:
            seat = str(turn["seat"])
            seen.add(seat)
            kind = classify(turn)
            per[seat]["classes"].append(
                {"round": rno, "kind": kind, "act": turn.get("speech_act")}
            )
            if kind == "SUBSTANTIVE":
                per[seat]["substantive"] += 1
                per[seat]["last_speech_round"] = rno
            elif kind == "STRUCTURED_YIELD":
                per[seat]["structured_yield"] += 1
                per[seat]["last_speech_round"] = rno
            elif kind == "ABSENT":
                per[seat]["absent"] += 1
            else:
                per[seat]["filler"] += 1
            vote = _explicit_vote(turn, kind)
            if vote:
                per[seat]["explicit_vote"] = vote
        for seat in seats:
            if seat not in seen:
                per[seat]["absent"] += 1
                per[seat]["classes"].append(
                    {"round": rno, "kind": "ABSENT", "act": None}
                )

    fired_seats: list[str] = []
    for seat, st in per.items():
        speech = int(st["substantive"]) + int(st["structured_yield"])
        reasons: list[str] = []
        if speech < min_speech:
            reasons.append("no-speech-act")
        if int(st["filler"]) >= 3 and speech == 0:
            reasons.append("filler-masquerade")
        if seat in agreeing and not st["explicit_vote"]:
            reasons.append("consent-by-silence")
        trail = 0
        for row in reversed(st["classes"]):
            if row["kind"] in {"SUBSTANTIVE", "STRUCTURED_YIELD"}:
                break
            trail += 1
        st["inactivity_streak"] = trail
        last = int(st["last_speech_round"])
        if (
            speech >= 1
            and last > 0
            and (n_rounds - last) >= max_inact
            and trail >= max_inact
        ):
            reasons.append("inactivity-without-yield")
        st["speech_acts"] = speech
        st["reasons"] = reasons
        st["in_agreeing"] = seat in agreeing
        if reasons:
            fired_seats.append(seat)

    fired = bool(fired_seats)
    return {
        "fixture_id": fixture.get("id"),
        "expected": fixture.get("expected"),
        "fired": fired,
        "silent": not fired,
        "fired_seats": fired_seats,
        "n_rounds": n_rounds,
        "roster": seats,
        "agreeing": sorted(agreeing),
        "seats": {
            s: {k: v for k, v in st.items() if k != "classes"}
            for s, st in per.items()
        },
        "runtime": _runtime(fired_seats, per, agreeing),
    }


def _runtime(
    fired_seats: list[str],
    per: dict[str, dict[str, Any]],
    agreeing: set[str],
) -> dict[str, Any]:
    yielded = [
        s
        for s, st in per.items()
        if int(st["structured_yield"]) > 0 and s not in fired_seats
    ]
    return {
        "escalate_or_mark_absent": sorted(fired_seats),
        "accept_structured_yield": sorted(yielded),
        "exclude_from_consenting_set": sorted(fired_seats),
        "consenting_must_have_explicit_vote": True,
        "disengaged_remain_in_roster_for_quorum": True,
    }


def scan_file(name: str) -> dict[str, Any]:
    return scan(load_fixture(name))


def list_fixtures() -> list[str]:
    return sorted(p.name for p in FIXTURES.glob("*.json"))


def battery() -> dict[str, Any]:
    planted: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    for name in list_fixtures():
        fx = load_fixture(name)
        result = scan(fx)
        result["file"] = name
        if str(fx.get("expected") or "").upper() == "FIRE":
            planted.append(result)
        else:
            clean.append(result)
    fp = sum(1 for r in clean if r["fired"])
    n_clean = len(clean)
    rate = (fp / n_clean) if n_clean else 1.0
    return {
        "planted": planted,
        "clean": clean,
        "false_positive_count": fp,
        "clean_count": n_clean,
        "false_positive_rate": rate,
        "planted_all_fired": all(r["fired"] for r in planted) and bool(planted),
        "clean_all_silent": all(r["silent"] for r in clean) and bool(clean),
    }
