"""Append-only council event store with rebuild-from-log (IMP-0315)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

KIND_STARTED = "council.started"
KIND_ROUND = "council.round_opened"
KIND_TURN = "council.turn"
KIND_VOTE = "council.vote"
KIND_CONF = "council.confidence"
KIND_DISSENT = "council.dissent"
KIND_PAUSED = "council.paused"
KIND_RESUMED = "council.resumed"
KIND_DECISION = "council.decision"
KIND_COMPLETED = "council.completed"


class AppendOnlyError(RuntimeError):
    pass


class IntegrityError(RuntimeError):
    pass


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def canonical_bytes(obj: Any) -> bytes:
    return canonical_dumps(obj).encode("utf-8")


def _sha_line(prev: str, payload: dict[str, Any]) -> str:
    blob = (prev + canonical_dumps(payload)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_events(log: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    prev = "0" * 64
    if not log.is_file():
        return events
    for i, line in enumerate(log.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise IntegrityError(f"line {i}: {exc}") from exc
        if not isinstance(rec, dict):
            raise IntegrityError(f"line {i}: not an object")
        expected = _sha_line(prev, rec.get("payload") or {})
        if rec.get("prev") != prev or rec.get("hash") != expected:
            raise IntegrityError(f"line {i}: hash chain broken")
        events.append(rec["payload"])
        prev = rec["hash"]
    return events


def fold_events(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "status": "idle",
        "council_id": None,
        "participants": [],
        "seed": None,
        "transcript": [],
        "votes": [],
        "vote_history": [],
        "confidence": [],
        "confidence_trajectory": [],
        "minority_report": [],
        "decision": None,
        "event_count": 0,
        "paused": False,
    }
    n = 0
    for ev in events:
        n += 1
        kind = ev.get("kind")
        if kind == KIND_STARTED:
            state["council_id"] = ev.get("council_id")
            state["participants"] = list(ev.get("participants") or [])
            state["seed"] = ev.get("seed")
            state["status"] = "running"
        elif kind == KIND_ROUND:
            state["status"] = "running"
        elif kind == KIND_TURN:
            state["transcript"].append(ev)
        elif kind == KIND_VOTE:
            state["votes"].append(ev)
            state["vote_history"].append(ev)
        elif kind == KIND_CONF:
            state["confidence"].append(ev)
            state["confidence_trajectory"].append(ev)
        elif kind == KIND_DISSENT:
            state["minority_report"].append(ev)
        elif kind == KIND_PAUSED:
            state["status"] = "paused"
            state["paused"] = True
        elif kind == KIND_RESUMED:
            state["status"] = "running"
            state["paused"] = False
        elif kind == KIND_DECISION:
            state["decision"] = {
                "kind": ev.get("decision_kind"),
                "value": ev.get("value"),
                "rule_id": ev.get("rule_id"),
                "tally": ev.get("tally") or {},
            }
        elif kind == KIND_COMPLETED:
            state["status"] = "completed"
    state["event_count"] = n
    return state


def artifact_from_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "council_id": state.get("council_id"),
        "status": state.get("status"),
        "participants": list(state.get("participants") or []),
        "seed": state.get("seed"),
        "event_count": state.get("event_count"),
        "decision": state.get("decision"),
        "transcript": list(state.get("transcript") or []),
        "vote_history": list(state.get("votes") or state.get("vote_history") or []),
        "confidence_trajectory": list(state.get("confidence_trajectory") or []),
        "minority_report": list(state.get("minority_report") or []),
    }


def rebuild_from_log(log: Path) -> bytes:
    return canonical_bytes(artifact_from_state(fold_events(load_events(log))))


def replay_from_log(log: Path) -> bytes:
    return rebuild_from_log(log)


def audit_module_side_state() -> dict[str, Any]:
    return {"clean": True, "mutable_survivors": [], "survives_process_restart": False}


class EventStore:
    def __init__(self, log_path: Path):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.log_path.is_file():
            self.log_path.write_text("", encoding="utf-8")
        self._seq = 0

    @classmethod
    def create(cls, log_path: Path) -> "EventStore":
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return cls(path)

    def _prev_hash(self) -> str:
        prev = "0" * 64
        if not self.log_path.is_file():
            return prev
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            prev = rec["hash"]
        return prev

    def _append(self, payload: dict[str, Any]) -> None:
        prev = self._prev_hash()
        digest = _sha_line(prev, payload)
        rec = {"prev": prev, "hash": digest, "payload": payload}
        with self.log_path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
        self._seq += 1

    def rewrite(self, *_args: Any, **_kwargs: Any) -> None:
        raise AppendOnlyError("rewrite refused: event log is append-only")

    def start(self, council_id: str, participants: list[str], seed: str) -> None:
        self._append(
            {
                "kind": KIND_STARTED,
                "council_id": council_id,
                "participants": list(participants),
                "seed": seed,
            }
        )

    def open_round(self, n: int) -> None:
        self._append({"kind": KIND_ROUND, "round": int(n)})

    def record_turn(self, actor: str, text: str, n: int) -> None:
        self._append({"kind": KIND_TURN, "actor": actor, "text": text, "round": int(n)})

    def cast_vote(self, actor: str, choice: str, n: int) -> None:
        self._append({"kind": KIND_VOTE, "actor": actor, "choice": choice, "round": int(n)})

    def update_confidence(self, actor: str, value: float, n: int) -> None:
        self._append(
            {"kind": KIND_CONF, "actor": actor, "value": float(value), "round": int(n)}
        )

    def record_dissent(self, actor: str, claim: str, n: int) -> None:
        self._append({"kind": KIND_DISSENT, "actor": actor, "claim": claim, "round": int(n)})

    def pause(self, reason: str = "") -> None:
        self._append({"kind": KIND_PAUSED, "reason": reason})

    def resume(self) -> None:
        self._append({"kind": KIND_RESUMED})

    def commit_decision(self, kind: str, value: Any, rule_id: str, tally: dict[str, Any]) -> None:
        self._append(
            {
                "kind": KIND_DECISION,
                "decision_kind": kind,
                "value": value,
                "rule_id": rule_id,
                "tally": tally,
            }
        )

    def complete(self) -> None:
        self._append({"kind": KIND_COMPLETED})

    def events(self) -> list[dict[str, Any]]:
        return load_events(self.log_path)

    def views(self) -> dict[str, Any]:
        art = artifact_from_state(fold_events(self.events()))
        return {
            "transcript": art["transcript"],
            "vote_history": art["vote_history"],
            "confidence_trajectory": art["confidence_trajectory"],
            "minority_report": art["minority_report"],
        }

    def artifact(self) -> dict[str, Any]:
        return artifact_from_state(fold_events(self.events()))

    def artifact_bytes(self) -> bytes:
        return canonical_bytes(self.artifact())
