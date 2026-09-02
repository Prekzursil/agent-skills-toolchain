"""Voice-fingerprint participant registry. IMP-0265."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable


def _norm_text(value: str) -> str:
    return " ".join(str(value).split())


def _norm_tools(tools: Iterable[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for t in tools:
        if t not in seen:
            seen.append(t)
    return tuple(sorted(seen))


def voice_fingerprint(vendor: str, model: str, prompt: str, tool_grants: Iterable[str]) -> str:
    payload = "|".join(
        [
            _norm_text(vendor),
            _norm_text(model),
            _norm_text(prompt),
            ",".join(_norm_tools(tool_grants)),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


FINGERPRINT_VERSION = "voice-fp-v1"
# Fields that define a *voice*; changing any of them changes the fingerprint.
FINGERPRINT_FIELDS = ("vendor", "model", "prompt", "tool_grants")
# Identity/claim fields deliberately excluded: they name a seat, not a voice.
IDENTITY_FIELDS_EXCLUDED_FROM_VOICE = (
    "participant_id",
    "display_name",
    "declared_expertise",
    "calibration_history_pointer",
)
FIRST_ROUND_QUESTION = "independence-audit: state your position in one sentence"


def first_round_output(seat: "Participant", question: str = FIRST_ROUND_QUESTION) -> str:
    """Deterministic stand-in for a seat's first-round output on ``question``.

    Output is a function of the voice only (fingerprint + question), never of
    identity fields, so two seats with the same voice answer identically.
    """
    payload = f"{seat.fingerprint}|{_norm_text(question)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass
class Participant:
    participant_id: str
    display_name: str
    vendor: str
    model: str
    prompt: str
    declared_expertise: tuple[str, ...] | list[str]
    calibration_history_pointer: str | None
    tool_grants: tuple[str, ...] | list[str]
    fingerprint: str = ""

    def __post_init__(self) -> None:
        self.declared_expertise = tuple(self.declared_expertise)
        self.tool_grants = tuple(self.tool_grants)
        self.fingerprint = voice_fingerprint(
            self.vendor, self.model, self.prompt, self.tool_grants
        )

    def as_dict(self) -> dict:
        """JSON-ready view of the seat (identity fields plus the derived fingerprint)."""
        return {
            "participant_id": self.participant_id,
            "display_name": self.display_name,
            "vendor": self.vendor,
            "model": self.model,
            "prompt": self.prompt,
            "declared_expertise": list(self.declared_expertise),
            "calibration_history_pointer": self.calibration_history_pointer,
            "tool_grants": list(self.tool_grants),
            "fingerprint": self.fingerprint,
            "fingerprint_version": FINGERPRINT_VERSION,
        }


def _audit_pair(a: "Participant", b: "Participant", question: str, flagged: bool) -> dict:
    same = a.fingerprint == b.fingerprint
    identical = first_round_output(a, question) == first_round_output(b, question)
    return {
        "a": a.participant_id,
        "b": b.participant_id,
        "same_fingerprint": same,
        "first_round_identical": identical,
        "independent": not (same or identical),
        "independence_rejected": same or identical,
        "flagged": flagged,
    }


def independence_audit(
    roster: Iterable["Participant"],
    flagged_pairs: Iterable[tuple[str, str]] | None = None,
    question: str = FIRST_ROUND_QUESTION,
) -> dict:
    """Pairwise independence audit.

    Two seats whose voice fingerprints collide produce identical first-round
    output on the same question (same vendor, model, prompt and tools), so the
    pair's independence assumption is rejected and it must not be counted as
    two independent voices. With ``flagged_pairs`` given, exactly those pairs
    (by participant id) are audited; otherwise every pair is audited and the
    fingerprint collisions are the flagged ones. ``pairs`` lists the flagged
    pairs when any exist, else every pair; ``all_pairs`` is always the full set.
    """
    seats = list(roster)
    by_id = {s.participant_id: s for s in seats}
    if flagged_pairs is not None:
        wanted = [(str(x), str(y)) for x, y in flagged_pairs]
        unknown = [pid for pair in wanted for pid in pair if pid not in by_id]
        if unknown:
            raise KeyError(f"flagged pair names unseated participant(s): {sorted(set(unknown))}")
        pairs = [_audit_pair(by_id[x], by_id[y], question, True) for x, y in wanted]
        flagged = list(pairs)
    else:
        pairs = []
        for i, a in enumerate(seats):
            for b in seats[i + 1 :]:
                pairs.append(_audit_pair(a, b, question, a.fingerprint == b.fingerprint))
        flagged = [p for p in pairs if p["flagged"]]
    headline = flagged if flagged else pairs
    return {
        "ok": True,
        "question": question,
        "pair_count": len(headline),
        "all_flagged_pairs_non_independent": all(not p["independent"] for p in flagged) if flagged else True,
        "flagged_pairs": flagged,
        "pairs": headline,
        "all_pairs": pairs,
    }


class ParticipantRegistry:
    def __init__(self) -> None:
        self._seats: list[Participant] = []

    def register(self, **kwargs) -> Participant:
        person = Participant(**kwargs)
        self._seats.append(person)
        return person

    def roster(self) -> list[Participant]:
        return list(self._seats)

    def independence_audit(self, question: str = FIRST_ROUND_QUESTION) -> dict:
        """Pairwise independence audit of the seated roster (see module function)."""
        return {**independence_audit(self._seats, question=question), **self.collision_report()}

    def collision_report(self) -> dict:
        by_fp: dict[str, list[Participant]] = {}
        for p in self._seats:
            by_fp.setdefault(p.fingerprint, []).append(p)
        collisions = []
        for fp, group in by_fp.items():
            if len(group) > 1:
                collisions.append(
                    {
                        "fingerprint": fp,
                        "seat_ids": [p.participant_id for p in group],
                    }
                )
        return {
            "fired": bool(collisions),
            "seat_count": len(self._seats),
            "effective_voice_count": len(by_fp),
            "collision_count": len(collisions),
            "collisions": collisions,
        }
