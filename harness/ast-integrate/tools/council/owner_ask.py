"""Council-initiated owner question packet (IMP-0366, TST-0290).

One foundation-level question at a time, with a recommendation, the strongest
trade-off and a stated default if the owner never answers.  ``check_packet``
rejects packets that carry two questions (a list, or one compound sentence
that asks two things), packets missing a required field, and questions whose
id or text already appears in the owner's decision log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterator

PACKET_SCHEMA = "council.owner-ask.packet/v1"

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
    compound: bool = False
    settled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "question_count": self.question_count,
            "compound": self.compound,
            "settled": self.settled,
        }

    # Mapping-style access so callers may treat the check as a plain JSON row.
    def __getitem__(self, key: str) -> Any:
        data = self.as_dict()
        if key not in data:
            raise KeyError(key)
        return data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)

    def keys(self) -> list[str]:
        return list(self.as_dict().keys())

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __contains__(self, key: object) -> bool:
        return key in self.as_dict()


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


_INTERROGATIVES = (
    "should",
    "shall",
    "can",
    "could",
    "would",
    "will",
    "do",
    "does",
    "did",
    "is",
    "are",
    "was",
    "were",
    "may",
    "might",
    "must",
    "have",
    "has",
    "which",
    "what",
    "who",
    "when",
    "where",
    "why",
    "how",
)
# ", and should we also ..." / "; or can the ..." — a second interrogative
# clause joined onto the first one inside a single sentence.
_CLAUSE_JOIN_RE = re.compile(
    r"\b(?:and|or|but|plus)\b\s+(?:also\s+|then\s+|additionally\s+)?\b(?:"
    + "|".join(_INTERROGATIVES)
    + r")\b\s+\w+",
    re.IGNORECASE,
)


def count_questions_in_text(question: Any) -> int:
    """Count the interrogative clauses a single question string asks."""
    text = " ".join(str(question or "").split())
    if not text:
        return 0
    total = 0
    for segment in re.split(r"\?\s+(?=\S)", text):
        if segment.strip():
            total += 1 + len(_CLAUSE_JOIN_RE.findall(segment))
    return total


def is_compound_question(question: Any) -> bool:
    return count_questions_in_text(question) > 1


def check_packet(
    packet: dict[str, Any] | None,
    decision_log: Any = None,
) -> PacketCheck:
    """Validate an owner-ask packet.

    Fails when the packet asks other than exactly one question (a list of
    questions, a follow-up, or one compound sentence asking two things), when a
    required field is missing, or when ``decision_log`` already records the
    question (by id or by text) so the owner would be asked twice.
    """
    packet = dict(packet or {})
    errors: list[str] = []
    questions = _questions_in(packet)
    n = len(questions)
    compound = False
    if n == 1 and is_compound_question(questions[0]):
        compound = True
        n = count_questions_in_text(questions[0])
        errors.append("compound-question")
    if n != 1:
        errors.append("one-question-at-a-time")
        errors.append(f"question-count={n}")
    for field in REQUIRED_PACKET_FIELDS:
        aliases = _FIELD_ALIASES.get(field, (field,))
        if not any(packet.get(alias) for alias in aliases):
            errors.append(f"missing {field}")
    settled = False
    if decision_log is not None:
        qid = packet.get("question_id") or packet.get("id")
        looked = lookup_settled(
            load_decision_log(decision_log),
            question_id=str(qid) if qid else None,
            question=questions[0] if len(questions) == 1 else None,
        )
        if looked.settled:
            settled = True
            errors.append("already-settled")
            if qid:
                errors.append(f"settled question_id={qid}")
    ok = not errors
    return PacketCheck(ok=ok, errors=errors, question_count=n, compound=compound, settled=settled)


def build_packet(
    *,
    question_id: str,
    question: str,
    recommendation: str,
    strongest_tradeoff: str,
    default: str,
    proposition_id: str | None = None,
    decision_log: Any = None,
) -> dict[str, Any]:
    """Build one owner-intervention packet and attach its ``check_packet`` result.

    The packet is returned even when the check fails so the caller can see the
    errors; ``packet["check"]["ok"]`` says whether it may be emitted.
    """
    packet: dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "question_id": str(question_id),
        "question": str(question),
        "recommendation": str(recommendation),
        "strongest_tradeoff": str(strongest_tradeoff),
        "tradeoff": str(strongest_tradeoff),
        "default": str(default),
        "default_if_unanswered": str(default),
        "proposition_id": str(proposition_id) if proposition_id else None,
        "foundation_level": True,
    }
    check = check_packet(packet, decision_log=decision_log)
    packet["check"] = check.as_dict()
    return packet


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


_OPEN_STATUSES = {"open", "pending", "unanswered", "unsettled", "deferred"}


def _row_is_settled(row: dict[str, Any]) -> bool:
    """A decision-log row records a settled question unless it is explicitly open.

    Rows with ``settled: true``, a non-null ``answer`` or ``status: settled`` are
    settled.  Rows marked open (``status: open``, ``settled: false``, or an
    explicit ``answer: null`` alongside a non-settled status) are not.  A bare
    row that only names the question (no status/answer keys at all) is a
    recorded decision, so asking it again would ask the owner twice.
    """
    if row.get("settled") is False:
        return False
    status = str(row.get("status") or "").strip().lower()
    if status in _OPEN_STATUSES:
        return False
    if row.get("settled") or row.get("answer") is not None or status == "settled":
        return True
    return "status" not in row and "answer" not in row


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
        if not isinstance(row, dict):
            continue
        rid = str(row.get("question_id") or row.get("id") or "")
        rtext = str(row.get("question") or "")
        if not _row_is_settled(row):
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
    "COUNCIL_RUNNING",
    "COUNCIL_SUSPENDED",
    "ConsiderResult",
    "Lookup",
    "OUTCOME_EMITTED",
    "OUTCOME_REFUSED_PENDING",
    "OUTCOME_SKIPPED_NOT_OWNER",
    "OUTCOME_SUPPRESSED",
    "OwnerAskSession",
    "PACKET_SCHEMA",
    "PacketCheck",
    "REQUIRED_PACKET_FIELDS",
    "build_packet",
    "check_packet",
    "count_questions_in_text",
    "is_compound_question",
    "load_decision_log",
    "lookup_settled",
]
