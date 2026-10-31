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


class ParticipantRegistry:
    def __init__(self) -> None:
        self._seats: list[Participant] = []

    def register(self, **kwargs) -> Participant:
        person = Participant(**kwargs)
        self._seats.append(person)
        return person

    def roster(self) -> list[Participant]:
        return list(self._seats)

    def independence_audit(self) -> dict:
        report = self.collision_report()
        pairs = []
        seats = self._seats
        for i, a in enumerate(seats):
            for b in seats[i + 1 :]:
                same = a.fingerprint == b.fingerprint
                pairs.append(
                    {
                        "a": a.participant_id,
                        "b": b.participant_id,
                        "independent": not same,
                        "flagged": same,
                    }
                )
        flagged = [p for p in pairs if p["flagged"]]
        return {
            "ok": True,
            "pair_count": len(flagged) if flagged else len(pairs),
            "all_flagged_pairs_non_independent": all(not p["independent"] for p in flagged) if flagged else True,
            "flagged_pairs": flagged,
            "pairs": pairs,
            **report,
        }

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
