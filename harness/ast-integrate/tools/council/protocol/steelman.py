"""Steelman gate: covering restatement required before a rebuttal is admitted."""
from __future__ import annotations

from typing import Any

ACCEPT = "ACCEPT"
NONE = "NONE"
REFUSE = "REFUSE"
ESCALATION_KIND = "mediator-required"
REFUSAL_LIMIT = 3


class SteelmanGate:
    def __init__(self, gate_enabled: bool = True) -> None:
        self.gate_enabled = gate_enabled
        self.refusal_limit = REFUSAL_LIMIT
        self._positions: dict[str, dict[str, Any]] = {}
        self._attempts: dict[str, dict[str, Any]] = {}
        self._attempt_seq = 0
        self._accepted: dict[tuple[str, str], str] = {}
        self._refuse_counts: dict[tuple[str, str], int] = {}
        self._progress: dict[tuple[str, str], str] = {}
        self._mediators: dict[tuple[str, str], str] = {}
        self._log: list[dict[str, Any]] = []
        self._escalations: list[dict[str, Any]] = []

    def register_position(
        self,
        position_id: str,
        author_id: str,
        claims: list[dict[str, Any]],
        text: str,
    ) -> None:
        self._positions[position_id] = {
            "author_id": author_id,
            "claims": list(claims),
            "text": text,
        }

    def _covering(self, position_id: str, restatement: list[dict[str, Any]]) -> bool:
        claims = self._positions[position_id]["claims"]
        needed = {c["id"] for c in claims}
        got = {r.get("id") for r in restatement if str(r.get("paraphrase") or "").strip()}
        return needed <= got

    def submit_steelman(
        self,
        position_id: str,
        opponent_id: str,
        text: str,
        restatement: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._attempt_seq += 1
        aid = f"a{self._attempt_seq}"
        covering = self._covering(position_id, restatement)
        rec = {
            "attempt_id": aid,
            "ok": covering,
            "structural_ok": covering,
            "position_id": position_id,
            "opponent_id": opponent_id,
            "text": text,
            "restatement": restatement,
            "status": None,
        }
        self._attempts[aid] = rec
        return rec

    def author_verdict(
        self,
        attempt_id: str,
        actor_id: str,
        accepted: bool,
        rationale: str = "",
    ) -> dict[str, Any]:
        att = self._attempts[attempt_id]
        pos = att["position_id"]
        opp = att["opponent_id"]
        author = self._positions[pos]["author_id"]
        mediator = self._mediators.get((pos, opp))
        key = (pos, opp)
        progress = self._progress.get(key)

        if not att["structural_ok"]:
            return {"ok": False, "status": "INCOMPLETE"}

        if progress == "escalated":
            if actor_id == author:
                return {"ok": False, "status": "AUTHOR_LOCKED"}
            if not mediator or actor_id != mediator:
                return {"ok": False, "status": "NOT_MEDIATOR"}
        elif actor_id != author:
            return {"ok": False, "status": "NOT_AUTHOR"}

        if not accepted:
            att["status"] = "REFUSED"
            self._refuse_counts[key] = self._refuse_counts.get(key, 0) + 1
            result: dict[str, Any] = {
                "ok": True,
                "status": "REFUSED",
                "escalated": False,
                "deadlock": False,
                "rationale": rationale,
            }
            if self._refuse_counts[key] >= REFUSAL_LIMIT:
                esc = {"escalation_kind": ESCALATION_KIND, "deadlock": False}
                result["escalated"] = True
                result["escalation"] = esc
                self._progress[key] = "escalated"
                self._escalations.append(esc)
            return result

        att["status"] = "ACCEPTED"
        self._accepted[key] = att["text"]
        self._progress[key] = "accepted"
        return {"ok": True, "status": "ACCEPTED"}

    def submit_rebuttal(
        self, position_id: str, opponent_id: str, text: str
    ) -> dict[str, Any]:
        if not self.gate_enabled:
            rec = {
                "admitted": True,
                "preceded_by_accepted_steelman": False,
                "text": text,
            }
            return {"admitted": True, "ok": True, "record": rec}

        key = (position_id, opponent_id)
        accepted_text = self._accepted.get(key)
        if accepted_text:
            rec = {
                "admitted": True,
                "author_verdict": ACCEPT,
                "preceded_by_accepted_steelman": True,
                "steelman_text": accepted_text,
                "text": text,
            }
            return {"admitted": True, "ok": True, "record": rec}

        last_steel = None
        last_verdict = NONE
        for att in reversed(list(self._attempts.values())):
            if (
                att["position_id"] == position_id
                and att["opponent_id"] == opponent_id
                and att.get("structural_ok")
            ):
                last_steel = att["text"]
                last_verdict = REFUSE if att.get("status") == "REFUSED" else NONE
                break
        if last_steel is None:
            return {
                "admitted": False,
                "ok": False,
                "steelman_text": None,
                "author_verdict": NONE,
            }
        self._log.append(
            {
                "event": "REBUTTAL_REJECTED",
                "author_verdict": last_verdict,
                "steelman_text": last_steel,
            }
        )
        return {
            "admitted": False,
            "ok": False,
            "steelman_text": last_steel,
            "author_verdict": last_verdict,
        }

    def appoint_mediator(
        self, position_id: str, opponent_id: str, mediator_id: str
    ) -> dict[str, Any]:
        pos = self._positions[position_id]
        if mediator_id in {pos["author_id"], opponent_id}:
            return {"ok": False}
        self._mediators[(position_id, opponent_id)] = mediator_id
        return {"ok": True}

    def deadlocked(self, position_id: str, opponent_id: str) -> bool:
        return False

    def progress_state(self, position_id: str, opponent_id: str) -> str:
        return self._progress.get((position_id, opponent_id), "open")

    def escalation_events(self) -> list[dict[str, Any]]:
        return list(self._escalations)

    def rejection_log(self) -> list[dict[str, Any]]:
        return list(self._log)


__all__ = [
    "ACCEPT",
    "ESCALATION_KIND",
    "NONE",
    "REFUSAL_LIMIT",
    "REFUSE",
    "SteelmanGate",
]
