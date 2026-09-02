"""Owner-intervention channel with recorded interventions (IMP-0342).

A live council keeps a single append-only event log.  Participants contribute
turns while the council is ``running``; the owner may ``pause`` it, inject
guidance or a constraint *only while paused*, and ``resume``.  Every owner
action is appended as its own event carrying ``origin=owner`` and an
``origin_marker`` of the form ``owner-origin:<owner_id>``, so interventions
are distinguishable from participant contributions in the final artifact and
can never silently rewrite an earlier position: the log has no rewrite path
(``rewrite`` / ``truncate`` raise ``AppendOnlyError``) and a prefix hash taken
before an intervention still verifies afterwards (``check_prefix``).

``debug_overwrite_payload`` is the deliberate tamper hook used by the negative
control; it is the *only* way to change a recorded event and it exists so the
prefix check can be shown to FIRE.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable, Sequence

UNIT_ID = "IMP-0342"
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json:IMP-0342 question_or_target "
    "owner-intervention channel"
)

KIND_START = "council.start"
KIND_TURN = "participant.turn"
KIND_PAUSE = "owner.pause"
KIND_GUIDANCE = "owner.inject.guidance"
KIND_CONSTRAINT = "owner.inject.constraint"
KIND_RESUME = "owner.resume"
INTERVENTION_KINDS: tuple[str, ...] = (KIND_PAUSE, KIND_GUIDANCE, KIND_CONSTRAINT, KIND_RESUME)

ORIGIN_SYSTEM = "system"
ORIGIN_PARTICIPANT = "participant"
ORIGIN_OWNER = "owner"
OWNER_MARKER_PREFIX = "owner-origin:"

STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"


class OwnerChannelError(Exception):
    """A lifecycle or authorisation rule of the owner channel was violated."""


class AppendOnlyError(Exception):
    """The event log has no rewrite path."""


class PrefixTamperError(Exception):
    """A previously hashed prefix of the event log no longer verifies."""

    def __init__(self, detail: dict[str, Any]) -> None:
        self.detail = dict(detail)
        super().__init__(
            f"prefix of {detail.get('n')} events does not verify: "
            f"expected {detail.get('expected')} observed {detail.get('observed')}"
        )


def owner_marker(owner_id: str) -> str:
    return f"{OWNER_MARKER_PREFIX}{owner_id}"


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def canonical_event(event: dict[str, Any]) -> str:
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def event_digest(event: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_event(event).encode("utf-8")).hexdigest()


def prefix_hash(events: Sequence[dict[str, Any]], n: int | None = None) -> str:
    """Chained SHA-256 over the first ``n`` events (all of them by default).

    The chain means a change to event *k* moves every hash that covers *k*
    and no hash that stops before it.
    """
    if n is None:
        n = len(events)
    if n < 0 or n > len(events):
        raise ValueError(f"prefix length {n} outside log of {len(events)} events")
    h = hashlib.sha256(b"council-event-log-v1")
    for event in list(events)[:n]:
        h.update(event_digest(event).encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()


def check_prefix(events: Sequence[dict[str, Any]], expected: str, n: int) -> str:
    """Return ``"intact"`` or raise :class:`PrefixTamperError`.

    A log shorter than ``n`` is a truncation and also fires.
    """
    if len(events) < n:
        raise PrefixTamperError(
            {
                "n": n,
                "expected": expected,
                "observed": None,
                "fired": True,
                "reason": f"log holds {len(events)} events, prefix needs {n}",
            }
        )
    observed = prefix_hash(events, n)
    if observed != expected:
        raise PrefixTamperError(
            {"n": n, "expected": expected, "observed": observed, "fired": True}
        )
    return "intact"


# ---------------------------------------------------------------------------
# Append-only event log
# ---------------------------------------------------------------------------


class EventLog:
    """Append-only sequence of event dicts; ``seq`` starts at 1."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def __len__(self) -> int:
        return len(self._events)

    def append(
        self,
        kind: str,
        origin: str,
        actor: str,
        payload: dict[str, Any] | None = None,
        *,
        origin_marker: str | None = None,
    ) -> dict[str, Any]:
        if origin == ORIGIN_OWNER and not origin_marker:
            raise OwnerChannelError("owner events must carry an origin marker")
        if origin != ORIGIN_OWNER and origin_marker:
            raise OwnerChannelError("only owner events may carry an origin marker")
        event: dict[str, Any] = {
            "seq": len(self._events) + 1,
            "kind": kind,
            "origin": origin,
            "actor": actor,
            "origin_marker": origin_marker,
            "payload": dict(payload or {}),
        }
        event["digest"] = event_digest({k: v for k, v in event.items() if k != "digest"})
        self._events.append(event)
        return json.loads(canonical_event(event))

    def events(self) -> list[dict[str, Any]]:
        """Deep copies: callers cannot reach the stored records."""
        return [json.loads(canonical_event(e)) for e in self._events]

    def get(self, seq: int) -> dict[str, Any]:
        for event in self._events:
            if event["seq"] == seq:
                return json.loads(canonical_event(event))
        raise KeyError(seq)

    def rewrite(self, seq: int, *_: Any, **__: Any) -> None:
        raise AppendOnlyError(f"event {seq} cannot be rewritten; the log is append-only")

    def truncate(self, *_: Any, **__: Any) -> None:
        raise AppendOnlyError("the event log cannot be truncated")

    def debug_overwrite_payload(self, seq: int, payload: dict[str, Any]) -> None:
        """Tamper hook for the negative control only.

        Bypasses the append-only API on purpose so that ``check_prefix`` can
        be shown to FIRE on a mutated prior event.  Production code must not
        call this.
        """
        for event in self._events:
            if event["seq"] == seq:
                event["payload"] = dict(payload)
                return
        raise KeyError(seq)


# ---------------------------------------------------------------------------
# Live council with the owner channel
# ---------------------------------------------------------------------------


class LiveCouncil:
    def __init__(self, council_id: str, owner_id: str = "owner") -> None:
        if not council_id:
            raise OwnerChannelError("council_id is required")
        if not owner_id:
            raise OwnerChannelError("owner_id is required")
        self.council_id = council_id
        self.owner_id = owner_id
        self.log = EventLog()
        self.participants: list[str] = []
        self.seed: str = ""
        self._status = STATUS_IDLE

    # -- state ------------------------------------------------------------

    @property
    def status(self) -> str:
        return self._status

    def _require_owner(self, owner_id: str, action: str) -> None:
        if owner_id != self.owner_id:
            raise OwnerChannelError(
                f"{action}: {owner_id!r} is not the owner of {self.council_id} ({self.owner_id!r})"
            )

    def _require_status(self, wanted: str, action: str) -> None:
        if self._status != wanted:
            raise OwnerChannelError(
                f"{action} requires status {wanted!r}, council is {self._status!r}"
            )

    def _owner_event(self, kind: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.log.append(
            kind,
            ORIGIN_OWNER,
            self.owner_id,
            payload,
            origin_marker=owner_marker(self.owner_id),
        )

    # -- lifecycle --------------------------------------------------------

    def start(self, participants: Iterable[str], seed: str = "") -> dict[str, Any]:
        self._require_status(STATUS_IDLE, "start")
        roster = list(dict.fromkeys(participants))
        if not roster:
            raise OwnerChannelError("a council needs at least one participant")
        self.participants = roster
        self.seed = seed
        event = self.log.append(
            KIND_START,
            ORIGIN_SYSTEM,
            self.council_id,
            {"participants": roster, "seed": seed, "owner_id": self.owner_id},
        )
        self._status = STATUS_RUNNING
        return event

    def record_turn(self, participant: str, text: str) -> dict[str, Any]:
        self._require_status(STATUS_RUNNING, "record_turn")
        if participant not in self.participants:
            raise OwnerChannelError(f"{participant!r} is not seated on {self.council_id}")
        if participant == self.owner_id:
            raise OwnerChannelError("the owner speaks through the owner channel, not as a participant")
        return self.log.append(KIND_TURN, ORIGIN_PARTICIPANT, participant, {"text": text})

    def pause(self, owner_id: str, reason: str = "") -> dict[str, Any]:
        self._require_owner(owner_id, "pause")
        self._require_status(STATUS_RUNNING, "pause")
        event = self._owner_event(KIND_PAUSE, {"reason": reason})
        self._status = STATUS_PAUSED
        return event

    def inject_guidance(self, owner_id: str, text: str) -> dict[str, Any]:
        self._require_owner(owner_id, "inject_guidance")
        self._require_status(STATUS_PAUSED, "inject_guidance")
        return self._owner_event(KIND_GUIDANCE, {"text": text})

    def inject_constraint(self, owner_id: str, text: str) -> dict[str, Any]:
        self._require_owner(owner_id, "inject_constraint")
        self._require_status(STATUS_PAUSED, "inject_constraint")
        return self._owner_event(KIND_CONSTRAINT, {"text": text})

    def resume(self, owner_id: str) -> dict[str, Any]:
        self._require_owner(owner_id, "resume")
        self._require_status(STATUS_PAUSED, "resume")
        event = self._owner_event(KIND_RESUME, {})
        self._status = STATUS_RUNNING
        return event

    # -- views ------------------------------------------------------------

    def snapshot_prefix(self) -> dict[str, Any]:
        events = self.log.events()
        return {"n": len(events), "prefix_hash": prefix_hash(events)}

    def artifact(self) -> dict[str, Any]:
        events = self.log.events()
        return {
            "council_id": self.council_id,
            "owner_id": self.owner_id,
            "status": self._status,
            "participants": list(self.participants),
            "event_count": len(events),
            "events": events,
            "interventions": [e for e in events if e["origin"] == ORIGIN_OWNER],
            "contributions": [e for e in events if e["origin"] == ORIGIN_PARTICIPANT],
            "log_hash": prefix_hash(events),
        }


# ---------------------------------------------------------------------------
# Scans and demonstrations
# ---------------------------------------------------------------------------


def scan_owner_markers(artifact: dict[str, Any]) -> dict[str, Any]:
    """Are owner interventions distinguishable from participant turns?"""
    interventions = list(artifact.get("interventions", []))
    contributions = list(artifact.get("contributions", []))
    missing = [
        e["seq"]
        for e in interventions
        if not str(e.get("origin_marker") or "").startswith(OWNER_MARKER_PREFIX)
        or e.get("kind") not in INTERVENTION_KINDS
    ]
    confusion = [
        e["seq"]
        for e in contributions
        if e.get("origin_marker")
        or e.get("origin") != ORIGIN_PARTICIPANT
        or e.get("kind") in INTERVENTION_KINDS
    ]
    intervention_seqs = {e["seq"] for e in interventions}
    contribution_seqs = {e["seq"] for e in contributions}
    overlap = sorted(intervention_seqs & contribution_seqs)
    return {
        "intervention_count": len(interventions),
        "contribution_count": len(contributions),
        "intervention_kinds": [e.get("kind") for e in interventions],
        "intervention_markers": [e.get("origin_marker") for e in interventions],
        "missing_owner_marker_seqs": missing,
        "origin_confusion_seqs": confusion + overlap,
        "every_intervention_has_owner_marker": not missing,
        "distinguishable": not missing and not confusion and not overlap,
    }


def run_lifecycle_demo() -> dict[str, Any]:
    """Two turns, pause, guidance, constraint, resume, one more turn."""
    council = LiveCouncil("council-imp-0342-demo", owner_id="owner-1")
    council.start(["alice", "bob"], seed="imp-0342")
    t1 = council.record_turn("alice", "Position A: ship the gate as-is.")
    t2 = council.record_turn("bob", "Position B: hold for the prefix invariant.")
    prefix_before = council.snapshot_prefix()
    council.pause("owner-1", "owner review")
    council.inject_guidance("owner-1", "Weigh the invariant over speed.")
    council.inject_constraint("owner-1", "Do not rewrite position A or B.")
    council.resume("owner-1")
    council.record_turn("alice", "Position A': accept the constraint.")
    events = council.log.events()
    prefix_after = prefix_hash(events, int(prefix_before["n"]))
    live = {e["seq"]: e for e in events}
    prior_texts_unchanged = (
        live[t1["seq"]]["payload"]["text"] == t1["payload"]["text"]
        and live[t2["seq"]]["payload"]["text"] == t2["payload"]["text"]
    )
    art = council.artifact()
    return {
        "artifact": art,
        "scan": scan_owner_markers(art),
        "status_after": council.status,
        "event_count": len(events),
        "prefix_before": prefix_before,
        "prefix_after": prefix_after,
        "prefix_of_prior_unchanged": prefix_after == prefix_before["prefix_hash"],
        "prior_texts_unchanged": prior_texts_unchanged,
    }


def run_negative_control() -> dict[str, Any]:
    """Mutate a prior event: the prefix check must FIRE; rewrite must refuse."""
    council = LiveCouncil("council-imp-0342-nc", owner_id="owner-1")
    council.start(["alice"], seed="nc")
    turn = council.record_turn("alice", "original position")
    snap = council.snapshot_prefix()
    intact_on_clean_log = (
        check_prefix(council.log.events(), snap["prefix_hash"], int(snap["n"])) == "intact"
    )
    rewrite_api_refused = False
    try:
        council.log.rewrite(int(turn["seq"]), {"text": "rewritten"})
    except AppendOnlyError:
        rewrite_api_refused = True
    truncate_refused = False
    try:
        council.log.truncate()
    except AppendOnlyError:
        truncate_refused = True
    council.log.debug_overwrite_payload(int(turn["seq"]), {"text": "mutated position"})
    fired = False
    detail: dict[str, Any] = {}
    try:
        check_prefix(council.log.events(), snap["prefix_hash"], int(snap["n"]))
    except PrefixTamperError as exc:
        fired = True
        detail = exc.detail
    return {
        "intact_on_clean_log": intact_on_clean_log,
        "rewrite_api_refused": rewrite_api_refused and truncate_refused,
        "mutated_seq": int(turn["seq"]),
        "prefix_check_fired": fired,
        "detail": detail,
    }


__all__ = [
    "AppendOnlyError",
    "EventLog",
    "INTERVENTION_KINDS",
    "KIND_CONSTRAINT",
    "KIND_GUIDANCE",
    "KIND_PAUSE",
    "KIND_RESUME",
    "KIND_START",
    "KIND_TURN",
    "LiveCouncil",
    "ORIGIN_OWNER",
    "ORIGIN_PARTICIPANT",
    "ORIGIN_SYSTEM",
    "OWNER_MARKER_PREFIX",
    "OwnerChannelError",
    "PrefixTamperError",
    "SPEC_ANCHOR",
    "STATUS_IDLE",
    "STATUS_PAUSED",
    "STATUS_RUNNING",
    "UNIT_ID",
    "canonical_event",
    "check_prefix",
    "event_digest",
    "owner_marker",
    "prefix_hash",
    "run_lifecycle_demo",
    "run_negative_control",
    "scan_owner_markers",
]
