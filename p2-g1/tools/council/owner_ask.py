"""Council-initiated owner question packet (IMP-0366)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OUTCOME_EMITTED = "OUTCOME_EMITTED"
OUTCOME_SUPPRESSED = "OUTCOME_SUPPRESSED"
OUTCOME_REFUSED_PENDING = "OUTCOME_REFUSED_PENDING"
OUTCOME_SKIPPED_NOT_OWNER = "OUTCOME_SKIPPED_NOT_OWNER"
COUNCIL_SUSPENDED = "COUNCIL_SUSPENDED"
COUNCIL_RUNNING = "RUNNING"

REQUIRED_PACKET_FIELDS = (
    "question",
    "recommendation",
    "tradeoff",
    "default_if_unanswered",
)

_FIELD_ALIASES = {
    "tradeoff": ("tradeoff", "strongest_tradeoff"),
    "default_if_unanswered": ("default_if_unanswered", "default"),
}


@dataclass
class PacketCheck:
    ok: bool
    errors: list[str] = field(default_factory=list)
    question_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "question_count": self.question_count,
        }


@dataclass
class Lookup:
    settled: bool
    used_claimant_assertion: bool = False
    performed_before_emit: bool = True
    answer: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "settled": self.settled,
            "used_claimant_assertion": self.used_claimant_assertion,
            "performed_before_emit": self.performed_before_emit,
            "answer": self.answer,
        }


@dataclass
class ConsiderResult:
    outcome: str
    packet: dict[str, Any] | None = None
    lookup: Lookup | None = None
    errors: list[str] = field(default_factory=list)
    council_state: str = COUNCIL_RUNNING
    suspended: bool = False
    suppressed: bool = False


def _questions_in(packet: dict[str, Any]) -> list[str]:
    qs: list[str] = []
    if isinstance(packet.get("questions"), list):
        qs.extend(str(q) for q in packet["questions"] if q)
    q = packet.get("question")
    if isinstance(q, list):
        qs.extend(str(x) for x in q if x)
    elif q:
        qs.append(str(q))
    extra = packet.get("second_question") or packet.get("follow_up")
    if extra:
        qs.append(str(extra))
    # unique preserving order
    seen: set[str] = set()
    out: list[str] = []
    for item in qs:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def check_packet(packet: dict[str, Any] | None) -> PacketCheck:
    packet = dict(packet or {})
    errors: list[str] = []
    questions = _questions_in(packet)
    n = len(questions)
    if n != 1:
        errors.append("one-question-at-a-time")
        errors.append(f"question-count={n}")
    for field in REQUIRED_PACKET_FIELDS:
        aliases = _FIELD_ALIASES.get(field, (field,))
        if not any(packet.get(alias) for alias in aliases):
            errors.append(f"missing {field}")
    ok = not errors
    return PacketCheck(ok=ok, errors=errors, question_count=n)


def load_decision_log(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        for key in ("entries", "decisions", "log", "items"):
            val = raw.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if raw.get("question") or raw.get("question_id"):
            return [raw]
    return []


def lookup_settled(
    log: list[dict[str, Any]] | Any,
    *,
    question_id: str | None = None,
    question: str | None = None,
) -> Lookup:
    rows = load_decision_log(log) if not isinstance(log, list) else log
    qid = str(question_id or "")
    qtext = str(question or "")
    for row in rows:
        rid = str(row.get("question_id") or row.get("id") or "")
        rtext = str(row.get("question") or "")
        settled = bool(row.get("settled") or row.get("answer") or row.get("status") == "settled")
        if not settled:
            continue
        if (qid and rid == qid) or (qtext and rtext == qtext):
            return Lookup(
                settled=True,
                used_claimant_assertion=False,
                performed_before_emit=True,
                answer=row.get("answer") if row.get("answer") is not None else row.get("ruling") or True,
            )
    return Lookup(settled=False, used_claimant_assertion=False, performed_before_emit=True)


class OwnerAskSession:
    def __init__(self, log_raw: Any = None) -> None:
        self.log = load_decision_log(log_raw)
        self.emitted: list[dict[str, Any]] = []
        self.council_state = COUNCIL_RUNNING
        self.pending = False

    def consider(self, decision: dict[str, Any]) -> ConsiderResult:
        decision = dict(decision or {})
        owner = decision.get("owner_controlled")
        if owner is False:
            return ConsiderResult(
                outcome=OUTCOME_SKIPPED_NOT_OWNER,
                packet=None,
                lookup=Lookup(settled=False, performed_before_emit=True),
                council_state=self.council_state,
                suspended=False,
            )
        qid = str(decision.get("question_id") or decision.get("id") or "")
        qtext = str(decision.get("question") or "")
        looked = lookup_settled(self.log, question_id=qid, question=qtext)
        if looked.settled:
            return ConsiderResult(
                outcome=OUTCOME_SUPPRESSED,
                packet=None,
                lookup=looked,
                council_state=self.council_state,
                suppressed=True,
            )
        if self.pending or self.emitted:
            return ConsiderResult(
                outcome=OUTCOME_REFUSED_PENDING,
                packet=None,
                lookup=looked,
                council_state=self.council_state,
                errors=["pending-owner-packet"],
            )
        packet = {
            "schema": "council.owner-ask.packet/v1",
            "question": qtext,
            "recommendation": decision.get("recommendation"),
            "tradeoff": decision.get("tradeoff") or decision.get("strongest_tradeoff"),
            "default_if_unanswered": decision.get("default_if_unanswered")
            or decision.get("default"),
        }
        checked = check_packet(packet)
        if not checked.ok:
            return ConsiderResult(
                outcome="OUTCOME_INVALID",
                packet=None,
                lookup=looked,
                errors=list(checked.errors),
                council_state=self.council_state,
            )
        self.emitted.append(packet)
        self.pending = True
        self.council_state = COUNCIL_SUSPENDED
        return ConsiderResult(
            outcome=OUTCOME_EMITTED,
            packet=packet,
            lookup=looked,
            council_state=COUNCIL_SUSPENDED,
            suspended=True,
        )


__all__ = [
    "COUNCIL_SUSPENDED",
    "OUTCOME_EMITTED",
    "OUTCOME_REFUSED_PENDING",
    "OUTCOME_SKIPPED_NOT_OWNER",
    "OUTCOME_SUPPRESSED",
    "OwnerAskSession",
    "REQUIRED_PACKET_FIELDS",
    "check_packet",
    "load_decision_log",
    "lookup_settled",
]
