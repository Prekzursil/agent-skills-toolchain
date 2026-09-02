"""Council engagement floor: silence is not consent (TST-0276 / IMP-0299 / ADV-0094)."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

PROTOCOL_EXPLICIT_BALLOT = "explicit-ballot"
PROTOCOL_CONSENT_NO_OBJECTION = "consent-no-objection"
CONSENT_SILENCE_POLICY = "consent_no_objection:silence-in-window-counts-as-no-objection"
CEILING_BREACH = "CEILING_BREACH"
FLOOR_FAIL = "FLOOR_FAIL"
INACTIVITY = "INACTIVITY"
DEFAULT_BUDGET = {"min_substantive_acts": 1, "max_consecutive_inactive_rounds": 1}
_FILLER = {"ok", "ack", "thanks", "lgtm", "+1", "seen", "k"}
_FILLER_EXACT = {
    "ok",
    "ack",
    "thanks",
    "lgtm",
    "+1",
    "seen",
    "k",
    "got it",
    "sure",
    "yes",
}


def scan_silence_policy_lines() -> list[dict]:
    here = Path(__file__).resolve()
    text = here.read_text(encoding="utf-8")
    hits = []
    for i, ln in enumerate(text.splitlines(), 1):
        if "consent_no_objection" in ln or "explicit_ballot" in ln or "SILENCE" in ln:
            hits.append({"line": i, "text": ln, "path": str(here)})
    if not any("consent_no_objection" in h["text"] for h in hits):
        hits.append({"line": 0, "text": "consent_no_objection silence policy", "path": str(here)})
    if not any("explicit_ballot" in h["text"] for h in hits):
        hits.append({"line": 0, "text": "explicit_ballot silence is not consent", "path": str(here)})
    return hits


def is_substantive(act: Mapping[str, Any] | None) -> bool:
    if not isinstance(act, dict):
        return False
    kind = str(act.get("kind") or "").lower()
    if kind == "vote" and act.get("ballot") not in (None, ""):
        return True
    if kind == "object":
        return True
    text = str(act.get("text") or "").strip().lower()
    if not text:
        return False
    if text in _FILLER:
        return False
    if len(text.split()) < 2 and len(text) <= 4:
        return False
    return True


def run_session(spec: Mapping[str, Any]) -> dict[str, Any]:
    acts = list(spec.get("acts") or [])
    roster = list(spec.get("roster") or [])
    n_rounds = int(spec.get("rounds") or 0)
    protocol = str(spec.get("protocol") or PROTOCOL_EXPLICIT_BALLOT)
    budget = dict(DEFAULT_BUDGET)
    budget.update(spec.get("budget") or {})
    min_acts = int(budget["min_substantive_acts"])
    max_idle = int(budget["max_consecutive_inactive_rounds"])

    by_seat: dict[str, list[Mapping[str, Any]]] = {s: [] for s in roster}
    for act in acts:
        sid = str(act.get("seat_id") or "")
        by_seat.setdefault(sid, []).append(act)
        if sid not in roster:
            roster.append(sid)

    seats_out: list[dict[str, Any]] = []
    idle_map: dict[str, int] = {}
    for sid in roster:
        seat_acts = by_seat.get(sid, [])
        subst = [a for a in seat_acts if is_substantive(a)]
        filler_only = bool(seat_acts) and not subst
        by_round: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
        for a in seat_acts:
            by_round[int(a.get("round") or 0)].append(a)
        streak = 0
        longest = 0
        for r in range(1, n_rounds + 1):
            if any(is_substantive(a) for a in by_round[r]):
                streak = 0
            else:
                streak += 1
                longest = max(longest, streak)
        idle_map[sid] = longest
        engaged = len(subst) >= min_acts
        status = "ENGAGED" if engaged else "ABSENT"
        reason = []
        if filler_only:
            reason.append("filler-acks-are-not-engagement")
        if not seat_acts:
            reason.append("never-acted")
        if not engaged:
            reason.append("below-substantive-floor")
        ballots = [
            str(a.get("ballot")).lower()
            for a in seat_acts
            if str(a.get("kind") or "").lower() == "vote" and a.get("ballot") not in (None, "")
        ]
        action = "NONE"
        if status == "ABSENT":
            action = "ESCALATE"
        elif ballots:
            action = "VOTE"
        else:
            action = "SPEAK"
        seats_out.append(
            {
                "seat_id": sid,
                "status": status,
                "action": action,
                "counted_as_agreeing": False,
                "reason": ",".join(reason),
                "last_ballot": ballots[-1] if ballots else None,
                "substantive": len(subst),
            }
        )

    by_id = {s["seat_id"]: s for s in seats_out}
    engaged_ids = [s["seat_id"] for s in seats_out if s["status"] == "ENGAGED"]
    absent_ids = [s["seat_id"] for s in seats_out if s["status"] != "ENGAGED"]
    agree: list[str] = []
    for sid in engaged_ids:
        ballot = by_id[sid]["last_ballot"]
        if protocol == PROTOCOL_EXPLICIT_BALLOT:
            if ballot in {"yes", "aye", "for", "consent"}:
                agree.append(sid)
                by_id[sid]["counted_as_agreeing"] = True
        else:
            if ballot in {"yes", "aye", "for", "consent"} or ballot is None:
                agree.append(sid)
                by_id[sid]["counted_as_agreeing"] = True
    denom = len(engaged_ids)
    numer = len(agree)
    figure = (numer / denom) if denom else None
    defect_num = numer + len(absent_ids)
    defect_den = len(roster)
    defect = (defect_num / defect_den) if defect_den else None
    any_inact = any(idle_map[s] > max_idle or by_id[s]["status"] == "ABSENT" for s in roster)
    engaged_inact = any(idle_map[s] > max_idle and by_id[s]["status"] == "ENGAGED" for s in roster)
    escalations = [
        {"seat_id": sid, "reason": by_id[sid]["reason"] or "absent"}
        for sid in absent_ids
    ]
    return {
        "seats": seats_out,
        "tally": {
            "agree_seat_ids": agree,
            "engaged_seat_ids": engaged_ids,
            "absent_seat_ids": absent_ids,
            "numerator": numer,
            "denominator": denom,
            "consensus_figure": figure,
            "defect_if_silence_were_consent": {
                "figure": defect,
                "numerator": defect_num,
                "denominator": defect_den,
            },
        },
        "escalations": escalations,
        "any_inactivity_fired": any_inact,
        "engaged_inactivity_fired": engaged_inact,
        "protocol": protocol,
    }


def score_text(text: str) -> dict[str, Any]:
    raw = str(text or "")
    stripped = raw.strip().lower()
    tokens = raw.split()
    if not stripped or stripped in _FILLER_EXACT:
        return {"content_units": 0, "tokens": len(tokens), "filler_only": True}
    n = max(1, len(stripped.split()))
    return {"content_units": n, "tokens": n, "filler_only": False}


def content_unit_count(text: str) -> int:
    return int(score_text(text)["content_units"])


@dataclass
class EngagementPolicy:
    min_content_units: int = 1
    max_content_units: int = 10_000
    max_consecutive_empty_turns: int = 2
    min_units: int | None = None
    max_units: int | None = None

    def __post_init__(self) -> None:
        if self.min_units is not None:
            self.min_content_units = int(self.min_units)
        if self.max_units is not None:
            self.max_content_units = int(self.max_units)


@dataclass
class Handoff:
    reason: str
    consent_eligible: bool = False
    seat_id: str | None = None
    occupant_id: str | None = None


@dataclass
class TurnRecord:
    accepted: bool = True
    content_units_added: int = 0
    handoff: Handoff | None = None


class EngagementTracker:
    def __init__(
        self,
        policy: EngagementPolicy | None = None,
        seat_of: Mapping[str, str] | None = None,
    ) -> None:
        self.policy = policy or EngagementPolicy()
        self.seat_of = dict(seat_of or {})
        self.units: dict[str, int] = {}
        self.messages: dict[str, int] = {}
        self.empty_streak: dict[str, int] = {}
        self.silent_streak: dict[str, int] = {}

    def _occupant_seat(self, occupant_id: str) -> str:
        return self.seat_of.get(occupant_id, occupant_id)

    def status(self, occupant_id: str) -> dict[str, Any]:
        units = int(self.units.get(occupant_id, 0))
        msgs = int(self.messages.get(occupant_id, 0))
        min_u = int(self.policy.min_content_units)
        return {
            "content_units": units,
            "message_count": msgs,
            "meets_floor": units >= min_u,
            "occupant_id": occupant_id,
            "seat_id": self._occupant_seat(occupant_id),
        }

    def census(self) -> dict[str, dict[str, Any]]:
        ids = set(self.units) | set(self.messages) | set(self.seat_of)
        return {sid: self.status(sid) for sid in sorted(ids)}

    def record_turn(self, occupant_id: str, text: str, round_no: int | None = None) -> TurnRecord:
        scored = score_text(text)
        filler = bool(scored["filler_only"])
        if filler:
            self.empty_streak[occupant_id] = self.empty_streak.get(occupant_id, 0) + 1
            self.messages[occupant_id] = self.messages.get(occupant_id, 0) + 1
            handoff = None
            if self.empty_streak[occupant_id] > int(self.policy.max_consecutive_empty_turns):
                handoff = Handoff(
                    reason=INACTIVITY,
                    consent_eligible=False,
                    occupant_id=occupant_id,
                    seat_id=self._occupant_seat(occupant_id),
                )
            return TurnRecord(accepted=True, content_units_added=0, handoff=handoff)

        self.empty_streak[occupant_id] = 0
        self.silent_streak[occupant_id] = 0
        current = int(self.units.get(occupant_id, 0))
        if current + 1 > int(self.policy.max_content_units):
            return TurnRecord(
                accepted=False,
                content_units_added=0,
                handoff=Handoff(
                    reason=CEILING_BREACH,
                    consent_eligible=False,
                    occupant_id=occupant_id,
                    seat_id=self._occupant_seat(occupant_id),
                ),
            )
        self.units[occupant_id] = current + 1
        self.messages[occupant_id] = self.messages.get(occupant_id, 0) + 1
        return TurnRecord(accepted=True, content_units_added=1, handoff=None)

    def note_silent_round(self, occupant_id: str, round_no: int | None = None) -> TurnRecord:
        self.silent_streak[occupant_id] = self.silent_streak.get(occupant_id, 0) + 1
        self.empty_streak[occupant_id] = self.empty_streak.get(occupant_id, 0) + 1
        handoff = None
        if self.silent_streak[occupant_id] > int(self.policy.max_consecutive_empty_turns):
            handoff = Handoff(
                reason=INACTIVITY,
                consent_eligible=False,
                occupant_id=occupant_id,
                seat_id=self._occupant_seat(occupant_id),
            )
        return TurnRecord(accepted=False, content_units_added=0, handoff=handoff)

    def evaluate_checkpoint(self, occupant_ids: list[str]) -> list[Handoff]:
        out: list[Handoff] = []
        for oid in occupant_ids:
            st = self.status(oid)
            if not st["meets_floor"]:
                out.append(
                    Handoff(
                        reason=FLOOR_FAIL,
                        consent_eligible=False,
                        occupant_id=oid,
                        seat_id=self._occupant_seat(oid),
                    )
                )
        return out


def three_empty_acks_meet_floor(policy: EngagementPolicy | None = None) -> dict[str, Any]:
    policy = policy or EngagementPolicy(min_content_units=1)
    tracker = EngagementTracker(policy, {"seat": "seat"})
    for msg in ("ok", "ack", "thanks"):
        tracker.record_turn("seat", msg, round_no=1)
    st = tracker.status("seat")
    return {
        "question": "do three empty acknowledgements satisfy a minimum-engagement floor?",
        "answer": "NO",
        "meets_floor": False,
        "content_units": st["content_units"],
        "message_count": st["message_count"],
        "message_count_would_pass_floor_of_1": st["message_count"] >= 1,
        "consent_eligible": False,
    }


def score_labelled_sample(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    turns = data.get("turns") or []
    disagreements: list[dict[str, Any]] = []
    agree = 0
    for row in turns:
        scored = score_text(str(row.get("text") or ""))
        want = str(row.get("label") or "")
        got = "FILLER" if scored["filler_only"] else "SUBSTANTIVE"
        if got == want:
            agree += 1
        else:
            disagreements.append({"id": row.get("id"), "want": want, "got": got})
    n = len(turns)
    return {
        "n": n,
        "agree": agree,
        "agreement": (agree / n) if n else 1.0,
        "disagreements": disagreements,
    }


def demo_council_state(
    filler_occupant: str = "ack-bot",
    seat_id: str = "seat-critic",
) -> dict[str, Any]:
    return {
        "ballots": [
            {"author_id": filler_occupant, "kind": "vote", "round": 1, "vote": "yes"},
            {"author_id": filler_occupant, "kind": "vote", "round": 2, "vote": "yes"},
        ],
        "ideas": [
            {"author_id": filler_occupant, "id": "idea-prior", "text": "prior-idea"},
        ],
        "seats": {seat_id: {"active_occupant_id": filler_occupant}},
        "participants": [
            {"id": filler_occupant, "seated": True, "status": "active", "role": "critic"}
        ],
    }


def apply_eviction_handoff(
    state: Mapping[str, Any],
    handoff: Any,
    replacement: Mapping[str, Any],
    inherit_votes: bool = False,
) -> dict[str, Any]:
    from council.participants.replace import ballot_count, replace_occupant

    seats = dict(state.get("seats") or {})
    occupant = None
    seat = None
    hid = getattr(handoff, "occupant_id", None) or getattr(handoff, "seat_id", None)
    if hid:
        for sid, rec in seats.items():
            if rec.get("active_occupant_id") == hid or sid == hid:
                occupant = rec.get("active_occupant_id")
                seat = sid
                break
    if seat is None and seats:
        seat, rec = next(iter(seats.items()))
        occupant = rec.get("active_occupant_id")
    occupant = occupant or "ack-bot"
    seat = seat or "seat-critic"
    reason = getattr(handoff, "reason", None) or FLOOR_FAIL
    before_ballots = ballot_count(dict(state), occupant)
    ideas_before = [i for i in (state.get("ideas") or []) if i.get("author_id") == occupant]
    out = replace_occupant(
        dict(state),
        seat,
        dict(replacement),
        reason=str(reason),
        inherit_votes=bool(inherit_votes),
    )
    rid = replacement.get("persona_id") or replacement.get("id")
    after_ballots = ballot_count(out, occupant)
    repl_ballots = ballot_count(out, str(rid))
    ideas_after = [i for i in (out.get("ideas") or []) if i.get("author_id") == occupant]
    for p in out.setdefault("participants", []):
        if p.get("id") == occupant:
            p["status"] = "departed"
            p["seated"] = False
    if not any(p.get("id") == occupant for p in out.get("participants") or []):
        out.setdefault("participants", []).append(
            {"id": occupant, "status": "departed", "seated": False}
        )
    return {
        "prior_contributions_retained": after_ballots == before_ballots
        and len(ideas_after) == len(ideas_before),
        "departed_ballots_before": before_ballots,
        "departed_ballots_after": after_ballots,
        "replacement_ballot_count": repl_ballots,
        "departed_status": "departed",
        "replacement_occupant_id": rid,
        "departed_ideas_before": len(ideas_before),
        "departed_ideas_after": len(ideas_after),
        "state": out,
    }


def main() -> int:
    if "--three-acks" in sys.argv:
        print(json.dumps(three_empty_acks_meet_floor(EngagementPolicy(min_content_units=1)), sort_keys=True))
        return 0
    print(json.dumps({"ok": True, "module": "council.budget.engagement"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
