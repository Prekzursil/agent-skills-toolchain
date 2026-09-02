#!/usr/bin/env python3
"""Deterministic recorded councils and planted controls for IMP-0321.

Twenty recorded transcripts are dumped to fixtures/recorded.json.
Planted helpers feed probe 1 threshold tests; they are not in the census.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
RECORDED_PATH = FIXTURES / "recorded.json"

FILLER_CYCLE = [
    "Noted. I agree with that. Sounds good to me. No objection at all.",
    "Likewise. Happy to proceed. I have nothing to add. Please continue.",
    "Yes. Okay. Acknowledged. That sounds right. Seconded. Keep going.",
    "As previously said. I concur. Please continue. I agree. Noted.",
    "That sounds right. No objection. Likewise. Happy to proceed. Yes.",
    "I have nothing to add. Okay. Acknowledged. Seconded. Please continue.",
    "Sounds good to me. I agree. Keep going. As previously said. Noted.",
    "Happy to proceed. That sounds right. I concur. No objection. Yes.",
]

SEATS4 = ["architect", "skeptic", "pragmatist", "critic"]
SEATS3 = ["architect", "skeptic", "pragmatist"]
SEATS5 = ["architect", "skeptic", "pragmatist", "critic", "historian"]
SEATS6 = ["architect", "skeptic", "pragmatist", "critic", "historian", "operator"]


def filler_block(n_sentences: int) -> str:
    if n_sentences <= 0:
        return ""
    parts = [FILLER_CYCLE[i % len(FILLER_CYCLE)] for i in range(n_sentences)]
    return " ".join(parts)


def claim_turn(seat: str, cid: str, topic: str, extra: str = "") -> dict[str, Any]:
    text = (
        f"Claim: {topic}. Therefore the recorded outcome should count this as a "
        f"substantive contribution from {seat}. Evidence: fixture {cid} seat {seat}."
    )
    if extra:
        text = f"{text} {extra}"
    return {
        "seat": seat,
        "text": text,
        "claims": [topic],
        "evidence_cites": [f"{cid}:{seat}"],
    }


def filler_turn(seat: str, n_sentences: int) -> dict[str, Any]:
    return {
        "seat": seat,
        "text": filler_block(n_sentences),
        "claims": [],
        "evidence_cites": [],
    }


def council(
    cid: str, label: str, participants: list[str], turns: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "council_id": cid,
        "label": label,
        "participants": participants,
        "turns": turns,
    }


def even_council(cid: str = "planted-even", n: int = 4, rounds: int = 4) -> dict[str, Any]:
    seats = (SEATS4 + ["historian", "operator"])[:n]
    topics = [
        "turn order must be kernel-owned",
        "quota bounds airtime not surviving claims",
        "filler acknowledgements are not engagement",
        "silence is a seat with no surviving claims",
        "evidence cites must survive redaction",
        "disagreement of measures is a finding",
    ]
    turns: list[dict[str, Any]] = []
    for r in range(rounds):
        for i, seat in enumerate(seats):
            topic = topics[(r + i) % len(topics)]
            turns.append(claim_turn(seat, cid, f"{topic} (round {r})"))
    return council(cid, "even-balanced", seats, turns)


def volume_filler_monopoly() -> dict[str, Any]:
    cid = "planted-volume-filler"
    turns: list[dict[str, Any]] = []
    for r in range(3):
        turns.append(filler_turn("architect", 36))
        turns.append(claim_turn("skeptic", cid, f"kernel records every turn r{r}"))
        turns.append(claim_turn("pragmatist", cid, f"quota is not outcome share r{r}"))
        turns.append(claim_turn("critic", cid, f"filler must score zero substance r{r}"))
    return council(cid, "volume-monopoly-filler-chair", SEATS4, turns)


def substance_terse_monopoly() -> dict[str, Any]:
    cid = "planted-substance-terse"
    turns: list[dict[str, Any]] = []
    for r in range(4):
        turns.append(filler_turn("architect", 18))
        turns.append(
            claim_turn(
                "skeptic",
                cid,
                f"surviving-claim share is the outcome metric r{r}",
                extra=(
                    "Claim: token volume is the wrong dominance axis. "
                    "Evidence: measured filler pads add tokens and zero claims."
                ),
            )
        )
        turns.append(filler_turn("pragmatist", 16))
        turns.append(filler_turn("critic", 16))
    return council(cid, "substance-monopoly-terse-skeptic", SEATS4, turns)


def silent_seat() -> dict[str, Any]:
    cid = "planted-silent"
    turns = []
    for r in range(3):
        for seat in ("architect", "skeptic", "pragmatist"):
            turns.append(claim_turn(seat, cid, f"three-voice round {r}"))
    return council(cid, "silent-critic", SEATS4, turns)


def below_dominance_volume() -> dict[str, Any]:
    cid = "planted-below-2x"
    turns = [
        claim_turn("architect", cid, "mild extra airtime still under twice fair share"),
        filler_turn("architect", 4),
        claim_turn("skeptic", cid, "skeptic keeps a surviving claim"),
        claim_turn("pragmatist", cid, "pragmatist keeps a surviving claim"),
        claim_turn("critic", cid, "critic keeps a surviving claim"),
    ]
    return council(cid, "below-dominance-threshold", SEATS4, turns)


def above_dominance_volume() -> dict[str, Any]:
    cid = "planted-above-2x"
    turns = [
        claim_turn("architect", cid, "this seat is built to exceed twice fair volume"),
        filler_turn("architect", 48),
        claim_turn("skeptic", cid, "skeptic keeps a surviving claim"),
        claim_turn("pragmatist", cid, "pragmatist keeps a surviving claim"),
        claim_turn("critic", cid, "critic keeps a surviving claim"),
    ]
    return council(cid, "above-dominance-threshold", SEATS4, turns)


def recorded_councils() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    out.append(even_council("rec-01", n=4, rounds=4))

    t: list[dict[str, Any]] = []
    for r in range(3):
        t.append(filler_turn("architect", 22))
        t.append(claim_turn("skeptic", "rec-02", f"record the turn event r{r}"))
        t.append(claim_turn("pragmatist", "rec-02", f"do not bypass the kernel r{r}"))
        t.append(claim_turn("critic", "rec-02", f"count claims not tokens r{r}"))
    out.append(council("rec-02", "volume-filler-architect", SEATS4, t))

    t = []
    for r in range(4):
        t.append(filler_turn("architect", 14))
        t.append(
            claim_turn(
                "skeptic",
                "rec-03",
                f"terse surviving claim r{r}",
                extra=(
                    "Claim: influence is surviving-claim share. "
                    "Evidence: rec-03 skeptic cites."
                ),
            )
        )
        t.append(filler_turn("pragmatist", 14))
        t.append(filler_turn("critic", 12))
    out.append(council("rec-03", "substance-terse-skeptic", SEATS4, t))

    t = []
    for r in range(3):
        for seat in ("architect", "skeptic", "pragmatist"):
            t.append(claim_turn(seat, "rec-04", f"critic never speaks r{r}"))
    out.append(council("rec-04", "silent-critic-zero-turns", SEATS4, t))

    t = []
    for r in range(3):
        t.append(claim_turn("architect", "rec-05", f"architect claim r{r}"))
        t.append(claim_turn("skeptic", "rec-05", f"skeptic claim r{r}"))
        t.append(claim_turn("pragmatist", "rec-05", f"pragmatist claim r{r}"))
        t.append(filler_turn("critic", 6))
    out.append(council("rec-05", "critic-filler-only", SEATS4, t))

    t = []
    for r in range(4):
        t.append(
            claim_turn(
                "architect",
                "rec-06",
                f"architect both loud and loaded r{r}",
                extra=(
                    filler_block(10)
                    + " Claim: this seat also carries the surviving claims. "
                    "Evidence: rec-06 architect bundle."
                ),
            )
        )
        t.append(claim_turn("skeptic", "rec-06", f"short skeptic r{r}"))
        t.append(claim_turn("pragmatist", "rec-06", f"short pragmatist r{r}"))
        t.append(claim_turn("critic", "rec-06", f"short critic r{r}"))
    out.append(council("rec-06", "agreeing-monopoly-architect", SEATS4, t))

    out.append(even_council("rec-07", n=3, rounds=4))

    t = []
    for r in range(2):
        t.append(claim_turn("architect", "rec-08", f"slight extra r{r}"))
        t.append(filler_turn("architect", 3))
        for seat in ("skeptic", "pragmatist", "critic", "historian"):
            t.append(claim_turn(seat, "rec-08", f"{seat} balanced r{r}"))
    out.append(council("rec-08", "five-seat-below-threshold", SEATS5, t))

    t = [filler_turn("architect", 20)]
    for r in range(3):
        for seat in SEATS4:
            t.append(claim_turn(seat, "rec-09", f"after opening pad r{r} {seat}"))
    out.append(council("rec-09", "opening-filler-then-even-substance", SEATS4, t))

    t = []
    for r in range(3):
        for seat in ("architect", "skeptic", "pragmatist"):
            t.append(filler_turn(seat, 10))
        t.append(
            claim_turn(
                "critic",
                "rec-10",
                f"closing critic lands the claims r{r}",
                extra=(
                    "Claim: last speaker can own substance without owning volume. "
                    "Evidence: rec-10 critic cites."
                ),
            )
        )
    out.append(council("rec-10", "last-speaker-substance", SEATS4, t))

    t = []
    for r in range(2):
        for seat in ("architect", "skeptic", "pragmatist", "critic", "historian"):
            t.append(claim_turn(seat, "rec-11", f"{seat} present r{r}"))
    out.append(council("rec-11", "six-seat-operator-silent", SEATS6, t))

    t = []
    for r in range(3):
        t.append(filler_turn("architect", 18))
        t.append(
            claim_turn(
                "skeptic",
                "rec-12",
                f"skeptic owns surviving claims r{r}",
                extra=(
                    "Claim: volume-loudest is not substance-loudest. Evidence: rec-12."
                ),
            )
        )
        t.append(claim_turn("pragmatist", "rec-12", f"pragmatist one claim r{r}"))
        t.append(filler_turn("critic", 8))
    out.append(council("rec-12", "competing-winners-volume-vs-substance", SEATS4, t))

    t = []
    for r in range(3):
        t.append(filler_turn("architect", 12))
        t.append(
            claim_turn(
                "skeptic",
                "rec-13",
                f"skeptic packed claims r{r}",
                extra=(
                    "Claim: equal tokens can hide unequal claims. "
                    "Evidence: rec-13 skeptic. Claim: a second surviving claim sits here."
                ),
            )
        )
        t.append(filler_turn("pragmatist", 12))
        t.append(filler_turn("critic", 12))
    out.append(council("rec-13", "equal-tokens-unequal-claims", SEATS4, t))

    t = []
    for r in range(3):
        t.append(
            {
                "seat": "architect",
                "text": (
                    "We should maybe consider a number of possible directions in a "
                    "fairly open-ended way without committing to a recorded claim or "
                    "pointing at a fixture, while continuing to speak at length about "
                    f"process in general for round {r}."
                ),
                "claims": [],
                "evidence_cites": [],
            }
        )
        t.append(
            claim_turn(
                "skeptic",
                "rec-14",
                f"cite-backed defect r{r}",
                extra="Evidence: https://example.test/rec-14 and fixture rec-14 measured.",
            )
        )
        t.append(claim_turn("pragmatist", "rec-14", f"one pragmatist claim r{r}"))
        t.append(claim_turn("critic", "rec-14", f"one critic claim r{r}"))
    out.append(council("rec-14", "rambler-vs-evidence-citer", SEATS4, t))

    t = []
    for r in range(4):
        t.append(filler_turn("architect", 20))
        t.append(
            {
                "seat": "skeptic",
                "text": (
                    f"Claim: chair token volume is not influence in rec-15 round {r}. "
                    "Therefore surviving-claim share is the dominance axis that matters. "
                    "Evidence: fixture rec-15 chair turns are filler acknowledgements; "
                    "measured claim count for chair is zero. Claim: skeptic holds the "
                    "recorded surviving claims."
                ),
                "claims": [
                    "chair volume is not influence",
                    "surviving-claim share is the dominance axis",
                    "skeptic holds surviving claims",
                ],
                "evidence_cites": ["rec-15:chair-filler", "rec-15:skeptic-claims"],
            }
        )
        t.append(claim_turn("pragmatist", "rec-15", f"modest pragmatist claim r{r}"))
        t.append(claim_turn("critic", "rec-15", f"modest critic claim r{r}"))
    out.append(
        council("rec-15", "chair-volume-skeptic-substance-manual-read", SEATS4, t)
    )

    t = []
    for r in range(3):
        t.append(filler_turn("architect", 15))
        t.append(filler_turn("skeptic", 15))
        t.append(
            claim_turn(
                "pragmatist",
                "rec-16",
                f"pragmatist breaks the substance tie r{r}",
                extra=(
                    "Claim: equal volume between architect and skeptic does not "
                    "imply equal substance."
                ),
            )
        )
    out.append(council("rec-16", "three-seat-volume-tie-substance-break", SEATS3, t))

    t = []
    for r in range(2):
        t.append(claim_turn("architect", "rec-17", f"architect near but under 2/n r{r}"))
        t.append(filler_turn("architect", 4))
        for seat in ("skeptic", "pragmatist", "critic", "historian"):
            t.append(claim_turn(seat, "rec-17", f"{seat} near-threshold r{r}"))
    out.append(council("rec-17", "five-seat-near-threshold-no-fire", SEATS5, t))

    t = []
    for r in range(3):
        t.append(
            {
                "seat": "architect",
                "text": (
                    f"Claim: the open question in round {r} is whether quota bounds "
                    "surviving claims. Therefore the question itself is a substantive "
                    "contribution. Evidence: fixture rec-18 question log."
                ),
                "claims": ["does quota bound surviving claims"],
                "evidence_cites": ["rec-18:question-log"],
            }
        )
        t.append(filler_turn("skeptic", 9))
        t.append(filler_turn("pragmatist", 9))
        t.append(filler_turn("critic", 9))
    out.append(council("rec-18", "questioning-seat-is-substantive", SEATS4, t))

    t = []
    for _ in range(4):
        for seat in SEATS4:
            t.append(filler_turn(seat, 8))
    out.append(council("rec-19", "all-filler-substance-undefined", SEATS4, t))

    t = []
    for r in range(3):
        t.append(filler_turn("architect", 25))
        t.append(
            {
                "seat": "skeptic",
                "text": (
                    f"Claim: quiet seats can own the outcome r{r}. Therefore silence "
                    "on volume is not silence on substance. Evidence: rec-20 skeptic units."
                ),
                "claims": ["quiet seats can own the outcome"],
                "evidence_cites": ["rec-20:skeptic"],
            }
        )
        t.append(filler_turn("pragmatist", 4))
        t.append(claim_turn("critic", "rec-20", f"critic modest r{r}"))
    out.append(council("rec-20", "quiet-substantive-vs-loud-empty", SEATS4, t))

    if len(out) != 20:
        raise RuntimeError(f"expected 20 recorded councils, got {len(out)}")
    ids = [c["council_id"] for c in out]
    if len(set(ids)) != 20:
        raise RuntimeError(f"duplicate recorded ids: {ids}")
    return out


def dump_recorded(path: Path | None = None) -> Path:
    path = path or RECORDED_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "unit_id": "IMP-0321",
        "n": 20,
        "note": (
            "Deterministic recorded corpus for volume-vs-substance disagreement. "
            "Not live model runs; labelled recorded fixtures with stable ids."
        ),
        "councils": recorded_councils(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_recorded(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or RECORDED_PATH
    if not path.is_file():
        dump_recorded(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    councils = data["councils"] if isinstance(data, dict) else data
    if len(councils) != 20:
        raise RuntimeError(f"{path} must hold 20 councils")
    return councils


if __name__ == "__main__":
    p = dump_recorded()
    print(f"wrote {p} councils=20")
