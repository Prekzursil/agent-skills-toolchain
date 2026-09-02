#!/usr/bin/env python3
"""Owner mid-council intervention: CONTINUE vs RESTART, pause, resume, replay.

Run identity is the tuple (question, chair_id, protocol_id, roster, vote_weights,
information_partition). A change that mutates that tuple, or that rewrites an
already-committed event, invalidates the run. Resource extensions and
append-only evidence do not.

Quiet continuation of an identity change is refused: the runtime must emit a
RestartRecord rather than append to the same run_id.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

CONTINUE = "CONTINUE"
RESTART = "RESTART"

IDENTITY_KEYS = (
    "question",
    "chair_id",
    "protocol_id",
    "roster",
    "vote_weights",
    "information_partition",
)

CONTINUE_CLASSES = {
    "evidence_add": "append-only new evidence; prior positions stay",
    "budget_extend": "raise a future ceiling (max_rounds, tokens, wall-clock)",
    "guidance_inject": "owner-origin labeled guidance for future rounds",
    "constraint_add_future": "constraint that applies from next round only",
    "pause": "stop without mutation",
    "resume": "continue from serialized prefix",
}

RESTART_CLASSES = {
    "question_change": "the asked question is the run's identity",
    "chair_replace": "the chair is a named identity seat",
    "protocol_change": "protocol/preset change is a different deliberation",
    "roster_replace_voting_seat": "a voting seat replacement would inherit or drop votes",
    "evidence_rewrite": "mutating a prior evidence event rewrites history",
    "vote_weight_change": "retroactive weight change rewrites past tallies",
    "information_partition_change": "changing what a seated speaker could see",
}

AUDIT_EVENT_TYPE = "owner_intervention"
RESTART_RECORD_TYPE = "restart_record"


class QuietContinuationRefused(ValueError):
    """Raised when an invalidating change is asked to continue on the same run_id."""


class PrefixMismatch(ValueError):
    """Raised when a pause snapshot's prefix bytes do not match prefix_sha256."""


class UnknownInterventionClass(ValueError):
    """Raised when an intervention class is not in the CONTINUE/RESTART tables."""


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_obj(obj: Any) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def hash_prefix(events: list[dict]) -> str:
    return sha256_obj(events)


def classify(op: dict, *, run: "CouncilRun | None" = None) -> dict:
    """Return disposition CONTINUE or RESTART for an owner operation.

    Secondary reclassification (not a guessed owner default):
      * evidence_add that names mutates_event_id is evidence_rewrite
      * budget_extend that lowers a ceiling below already-consumed rounds is RESTART
    """
    if not isinstance(op, dict):
        raise UnknownInterventionClass("intervention is not an object")
    cls = str(op.get("class") or "")
    if cls == "evidence_add" and op.get("mutates_event_id"):
        cls = "evidence_rewrite"
    if cls in RESTART_CLASSES:
        return {
            "class": cls,
            "disposition": RESTART,
            "invalidates_run": True,
            "reason": RESTART_CLASSES[cls],
        }
    if cls in CONTINUE_CLASSES:
        if cls == "budget_extend" and run is not None:
            field = str(op.get("field") or "max_rounds")
            new = op.get("new")
            if field == "max_rounds" and isinstance(new, int) and new < run.round_index:
                return {
                    "class": cls,
                    "disposition": RESTART,
                    "invalidates_run": True,
                    "reason": (
                        "budget ceiling lowered below already-consumed rounds; "
                        "past rounds would be silently un-happened"
                    ),
                }
        return {
            "class": cls,
            "disposition": CONTINUE,
            "invalidates_run": False,
            "reason": CONTINUE_CLASSES[cls],
        }
    raise UnknownInterventionClass(cls or "<missing class>")


class CouncilRun:
    def __init__(self, identity: dict, seeds: dict, run_id: str, *, max_rounds: int = 8):
        self.identity = {k: copy.deepcopy(identity[k]) for k in IDENTITY_KEYS}
        self.seeds = dict(seeds)
        self.run_id = run_id
        self.max_rounds = max_rounds
        self.events: list[dict] = []
        self.status = "LIVE"
        self.round_index = 0
        self.votes: list[dict] = []
        self.minority_reports: list[str] = []
        self.restart_record: dict | None = None

    @classmethod
    def new(
        cls,
        *,
        run_id: str,
        question: str,
        chair_id: str,
        protocol_id: str,
        roster: list[str],
        vote_weights: dict[str, int],
        information_partition: dict[str, list[str]] | None = None,
        seeds: dict[str, str] | None = None,
        max_rounds: int = 8,
    ) -> "CouncilRun":
        partition = information_partition or {seat: ["shared"] for seat in roster}
        return cls(
            {
                "question": question,
                "chair_id": chair_id,
                "protocol_id": protocol_id,
                "roster": list(roster),
                "vote_weights": dict(vote_weights),
                "information_partition": partition,
            },
            seeds or {"sampling": "s0", "tool_order": "s0", "wall_clock": "s0", "recruit": "s0"},
            run_id,
            max_rounds=max_rounds,
        )

    def apply_event(self, ev: dict) -> None:
        self.events.append(copy.deepcopy(ev))
        self._recompute_views()

    def _recompute_views(self) -> None:
        """Derived views are rebuilt from the event log. They are never the SSOT."""
        self.votes = []
        self.minority_reports = []
        self.round_index = 0
        self.restart_record = None
        status = "LIVE"
        max_rounds = None
        for ev in self.events:
            t = ev.get("type")
            if t == "round_open":
                self.round_index = int(ev["round"])
            elif t == "vote":
                self.votes.append(
                    {
                        "seat": ev["seat"],
                        "value": ev["value"],
                        "round": ev["round"],
                    }
                )
            elif t == "minority_report":
                self.minority_reports.append(str(ev["text"]))
            elif t == "budget":
                max_rounds = int(ev["max_rounds"])
            elif t == RESTART_RECORD_TYPE:
                self.restart_record = copy.deepcopy(ev)
                status = "RESTART_REQUIRED"
            elif t == "run_close":
                status = str(ev.get("status") or status)
        if max_rounds is not None:
            self.max_rounds = max_rounds
        if status != "LIVE":
            self.status = status

    def derived_state(self) -> dict:
        return {
            "run_id": self.run_id,
            "identity": copy.deepcopy(self.identity),
            "round_index": self.round_index,
            "votes": copy.deepcopy(self.votes),
            "minority_reports": list(self.minority_reports),
            "max_rounds": self.max_rounds,
            "status": self.status,
            "event_count": len(self.events),
        }

    def prefix_sha256(self) -> str:
        return hash_prefix(self.events)

    def pause(self) -> dict:
        """Serialize the prefix. Views are stored as expected, not as SSOT."""
        return {
            "run_id": self.run_id,
            "identity": copy.deepcopy(self.identity),
            "seeds": dict(self.seeds),
            "max_rounds": self.max_rounds,
            "prefix": copy.deepcopy(self.events),
            "prefix_sha256": self.prefix_sha256(),
            "cursor": len(self.events),
            "expected_derived": self.derived_state(),
        }

    @classmethod
    def from_snapshot(cls, snap: dict) -> "CouncilRun":
        ident = snap["identity"]
        run = cls.new(
            run_id=snap["run_id"],
            question=ident["question"],
            chair_id=ident["chair_id"],
            protocol_id=ident["protocol_id"],
            roster=list(ident["roster"]),
            vote_weights=dict(ident["vote_weights"]),
            information_partition=copy.deepcopy(ident["information_partition"]),
            seeds=dict(snap["seeds"]),
            max_rounds=int(snap.get("max_rounds") or 8),
        )
        claimed = str(snap.get("prefix_sha256") or "")
        actual = hash_prefix(snap["prefix"])
        if claimed != actual:
            raise PrefixMismatch(
                f"pause-record prefix_sha256 mismatch claimed={claimed} actual={actual}"
            )
        for ev in snap["prefix"]:
            run.apply_event(ev)
        if run.prefix_sha256() != claimed:
            raise PrefixMismatch("replay of prefix did not reconstruct the snapshot hash")
        return run


def apply_intervention(run: CouncilRun, op: dict, *, force_continue: bool = False) -> dict:
    """Apply an owner intervention.

    CONTINUE: append an owner_intervention event; prefix hash of prior events is unchanged.
    RESTART: close the run with a restart_record; do not append a continuing event.
    force_continue on a RESTART class raises QuietContinuationRefused.
    """
    decision = classify(op, run=run)
    cursor = len(run.events)
    prefix_hash = run.prefix_sha256()
    origin = "owner"
    if decision["disposition"] == RESTART:
        if force_continue or str(op.get("mode") or "") == "continue":
            raise QuietContinuationRefused(
                f"quiet continuation refused for class={decision['class']} "
                f"run_id={run.run_id} cursor={cursor}"
            )
        rec = {
            "type": RESTART_RECORD_TYPE,
            "old_run_id": run.run_id,
            "class": decision["class"],
            "reason": decision["reason"],
            "cursor": cursor,
            "prefix_sha256": prefix_hash,
            "origin": origin,
            "invalidates_run": True,
        }
        run.apply_event(rec)
        run.status = "RESTART_REQUIRED"
        run.restart_record = rec
        return {
            "applied": RESTART,
            "run_id": run.run_id,
            "restart_record": rec,
            "prefix_sha256_before": prefix_hash,
            "same_run_continued": False,
        }
    payload = copy.deepcopy(op)
    payload.pop("mode", None)
    ev = {
        "type": AUDIT_EVENT_TYPE,
        "class": decision["class"],
        "origin": origin,
        "cursor_before": cursor,
        "prefix_sha256_before": prefix_hash,
        "invalidates_run": False,
        "payload": payload,
    }
    run.apply_event(ev)
    if decision["class"] == "budget_extend" and op.get("field") == "max_rounds":
        run.apply_event({"type": "budget", "max_rounds": int(op["new"]), "origin": origin})
    prefix_after_prior = hash_prefix(run.events[:cursor])
    if prefix_after_prior != prefix_hash:
        raise PrefixMismatch("CONTINUE intervention mutated the committed prefix")
    return {
        "applied": CONTINUE,
        "run_id": run.run_id,
        "restart_record": None,
        "prefix_sha256_before": prefix_hash,
        "same_run_continued": True,
        "cursor_after": len(run.events),
    }


def replay_to_intervention(snap: dict) -> dict:
    """Rebuild derived state from the pause prefix. Must match expected_derived."""
    run = CouncilRun.from_snapshot(snap)
    got = run.derived_state()
    expected = snap.get("expected_derived")
    if expected is not None and got != expected:
        raise PrefixMismatch(
            "replay derived state diverged from pause expected_derived "
            f"got={got} expected={expected}"
        )
    return got
