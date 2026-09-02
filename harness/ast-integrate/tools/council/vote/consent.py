"""Consent / veto sessions. silence_policy is required; no constructor default."""
from __future__ import annotations

from typing import Any, Mapping

LATE_RECORD_AND_IGNORE = "LATE_RECORD_AND_IGNORE"
MODE_CONSENT = "MODE_CONSENT"
MODE_VETO = "MODE_VETO"
RESP_CONSENT = "RESP_CONSENT"
RESP_OBJECT = "RESP_OBJECT"
RESP_VETO = "RESP_VETO"
SILENCE_IS_CONSENT = "SILENCE_IS_CONSENT"
OUT_BLOCKED = "BLOCKED"
OUT_CONSENTED = "CONSENTED"
OUT_VETOED = "VETOED"
STATE_CONSENT_BY_SILENCE = "CONSENT_BY_SILENCE"
STATE_EXPLICIT = "EXPLICIT"


class ArtifactValidationError(Exception):
    pass


def _seat_id(seat: Mapping[str, Any]) -> str:
    return str(seat.get("id") or seat.get("participant_id") or "")


class ConsentSession:
    def __init__(
        self,
        proposal_id: str,
        mode: str,
        silence_policy: str,
        late_objection_policy: str,
        objection_window: Mapping[str, Any],
        participants: list[Mapping[str, Any]],
        proposal: str = "",
    ) -> None:
        if not silence_policy:
            raise ArtifactValidationError("silence_policy required")
        self.proposal_id = proposal_id
        self.mode = mode
        self.silence_policy = silence_policy
        self.late_objection_policy = late_objection_policy
        self.objection_window = dict(objection_window)
        self.participants = [dict(p) for p in participants]
        self.proposal = proposal
        self._events: list[dict[str, Any]] = []
        self._closed = False
        self._close_at: float | None = None
        self._artifact: dict[str, Any] | None = None
        self._late: list[dict[str, Any]] = []

    def respond(
        self,
        participant_id: str,
        kind: str,
        at: float,
        reason: str | None = None,
    ) -> dict[str, Any]:
        rec = {
            "participant_id": participant_id,
            "kind": kind,
            "at": float(at),
            "reason": reason or "",
            "admitted": True,
        }
        closes = float(self.objection_window.get("closes_at") or 0)
        if self._closed or float(at) > closes:
            rec["admitted"] = False
            rec["late"] = True
            if self.late_objection_policy == LATE_RECORD_AND_IGNORE:
                self._late.append(rec)
            return rec
        self._events.append(rec)
        return rec

    def _build(self, close_at: float) -> dict[str, Any]:
        opens = float(self.objection_window.get("opens_at") or 0)
        closes = float(self.objection_window.get("closes_at") or 0)
        if close_at < closes:
            silent = [
                _seat_id(s)
                for s in self.participants
                if _seat_id(s)
                not in {e["participant_id"] for e in self._events if e.get("admitted")}
            ]
            if silent:
                raise ArtifactValidationError("early close with silent seats")
        admitted = [e for e in self._events if e.get("admitted")]
        vetoes = [e for e in admitted if e["kind"] == RESP_VETO]
        objections = [e for e in admitted if e["kind"] == RESP_OBJECT]
        if self.mode == MODE_VETO and vetoes:
            outcome = OUT_VETOED
        elif objections:
            outcome = OUT_BLOCKED
        else:
            outcome = OUT_CONSENTED
        per: dict[str, Any] = {}
        seen = {e["participant_id"] for e in admitted}
        for seat in self.participants:
            sid = _seat_id(seat)
            hits = [e for e in admitted if e["participant_id"] == sid]
            if hits:
                per[sid] = {"status": STATE_EXPLICIT, "kind": hits[-1]["kind"]}
            elif self.silence_policy == SILENCE_IS_CONSENT:
                per[sid] = {"status": STATE_CONSENT_BY_SILENCE}
            else:
                per[sid] = {"status": "SILENT"}
        art = {
            "proposal_id": self.proposal_id,
            "mode": self.mode,
            "outcome": outcome,
            "silence_policy": self.silence_policy,
            "late_objection_policy": self.late_objection_policy,
            "objection_window": dict(self.objection_window),
            "per_participant_state": per,
            "late_objections": list(self._late),
            "events": list(admitted),
            "close_at": close_at,
            "opens_at": opens,
            "closes_at": closes,
            "seen": sorted(seen),
        }
        return art

    def close(self, close_at: float) -> dict[str, Any]:
        art = self._build(float(close_at))
        self._closed = True
        self._close_at = float(close_at)
        self._artifact = art
        return art

    def to_artifact(self) -> dict[str, Any]:
        if self._artifact is None:
            raise ArtifactValidationError("not closed")
        art = dict(self._artifact)
        art["late_objections"] = list(self._late)
        return art


def decision_from_events(
    *,
    proposal_id: str,
    mode: str,
    silence_policy: str,
    late_objection_policy: str,
    objection_window: Mapping[str, Any],
    participants: list[Mapping[str, Any]],
    events: list[Mapping[str, Any]],
    close_at: float,
    proposal: str = "",
) -> dict[str, Any]:
    sess = ConsentSession(
        proposal_id=proposal_id,
        mode=mode,
        silence_policy=silence_policy,
        late_objection_policy=late_objection_policy,
        objection_window=objection_window,
        participants=list(participants),
        proposal=proposal,
    )
    for event in events:
        sess.respond(
            str(event["participant_id"]),
            str(event["kind"]),
            float(event["at"]),
            event.get("reason"),
        )
    return sess.close(float(close_at))


def strip_silence_policy(artifact: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(artifact)
    out.pop("silence_policy", None)
    return out


def validate_artifact(artifact: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    if "silence_policy" not in artifact or not artifact.get("silence_policy"):
        errs.append("unrecorded silence_policy")
    if artifact.get("outcome") not in {OUT_BLOCKED, OUT_CONSENTED, OUT_VETOED}:
        errs.append("outcome missing")
    return errs
