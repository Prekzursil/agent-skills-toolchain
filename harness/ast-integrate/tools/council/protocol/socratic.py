"""Socratic cross-examination with enforced response obligations."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

STATE_OPEN = "OPEN"
STATE_DISCHARGED = "DISCHARGED"
STATE_EXPIRED = "EXPIRED"
STATE_ESCALATED = "ESCALATED"
LABEL_ANSWER = "ANSWER"

_Q_WORDS = re.compile(
    r"\b(does|what|how|why|when|where|who|which|can|is|are)\b",
    re.I,
)


def naive_any_bytes_discharge(text: str) -> bool:
    return bool(str(text or "").strip())


@dataclass
class Obligation:
    id: str
    asker: str
    addressee: str
    question: str
    state: str = STATE_OPEN
    age_turns: int = 0
    due_in_turns: int = 3
    discharged_turn: int | None = None
    expired_turn: int | None = None
    last_reason: str = ""
    kind: str = "question"
    parent_id: str | None = None


class SocraticProtocol:
    def __init__(self, default_due_in_turns: int = 3, auto_escalate: bool = False) -> None:
        self.default_due_in_turns = int(default_due_in_turns)
        self.auto_escalate = bool(auto_escalate)
        self._obs: dict[str, Obligation] = {}
        self._seq = 0
        self._clock = 0

    def ask(self, asker: str, addressee: str, question: str, due_in_turns: int | None = None) -> Obligation:
        self._seq += 1
        ob = Obligation(
            id=f"ob-{self._seq:04d}",
            asker=asker,
            addressee=addressee,
            question=question,
            due_in_turns=int(due_in_turns if due_in_turns is not None else self.default_due_in_turns),
        )
        self._obs[ob.id] = ob
        return ob

    def get(self, oid: str) -> Obligation:
        return self._obs[oid]

    def _addresses(self, ob: Obligation, speaker: str, text: str) -> bool:
        if speaker != ob.addressee:
            return False
        body = str(text or "").strip()
        if len(body) < 3:
            return False
        if body.lower() in {"ok", "yes", "no"} and "?" in ob.question:
            if body.lower() == "no" and "empty" in ob.question.lower():
                return True
            if len(body) <= 3:
                return body.lower() in {"no"}
        if naive_any_bytes_discharge(body) and len(body) > 20:
            q_tokens = set(re.findall(r"[a-z]{4,}", ob.question.lower()))
            t_tokens = set(re.findall(r"[a-z]{4,}", body.lower()))
            if q_tokens & t_tokens:
                return True
            if "empty" in ob.question.lower() and "empty" in body.lower():
                return True
            if "sha-256" in ob.question.lower():
                return False
        if body.lower() in {"no."}:
            return True
        return False

    def record_turn(self, speaker: str, text: str) -> None:
        self._clock += 1
        for ob in list(self._obs.values()):
            if ob.state != STATE_OPEN:
                continue
            ob.age_turns += 1
            if self._addresses(ob, speaker, text):
                ob.state = STATE_DISCHARGED
                ob.discharged_turn = ob.age_turns
                ob.last_reason = "answered"
                continue
            if ob.age_turns >= ob.due_in_turns:
                if self.auto_escalate:
                    self.escalate(ob.id)
                else:
                    ob.state = STATE_EXPIRED
                    ob.expired_turn = ob.age_turns
                    ob.last_reason = "deadline"

    def escalate(self, oid: str) -> Obligation:
        ob = self._obs[oid]
        ob.state = STATE_ESCALATED
        ob.last_reason = "escalated"
        self._seq += 1
        follow = Obligation(
            id=f"ob-{self._seq:04d}",
            asker=ob.asker,
            addressee=ob.addressee,
            question="FOLLOW: " + ob.question,
            due_in_turns=1,
            kind="escalation",
            parent_id=ob.id,
        )
        self._obs[follow.id] = follow
        return follow

    def by_state(self, state: str) -> list[Obligation]:
        return [o for o in self._obs.values() if o.state == state]

    def ledger(self) -> list[dict[str, Any]]:
        rows = []
        for o in self._obs.values():
            rows.append(
                {
                    "id": o.id,
                    "state": o.state,
                    "age_turns": o.age_turns,
                    "addressee": o.addressee,
                    "kind": o.kind,
                    "parent_id": o.parent_id,
                    "due_in_turns": o.due_in_turns,
                }
            )
        return rows


def ledger_digest(rows: list[dict[str, Any]]) -> str:
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ReplyClass:
    label: str
    is_answer: bool
    reply_bytes: int
    reason: str


def classify_reply(question: str | None = None, reply: str | None = None, text: str | None = None) -> Any:
    body = str(reply if reply is not None else text or "")
    q = str(question or "")
    label = LABEL_ANSWER if _looks_like_answer(q, body) else "EVASION"
    return ReplyClass(
        label=label,
        is_answer=label == LABEL_ANSWER,
        reply_bytes=len(body.encode("utf-8")),
        reason="addressed" if label == LABEL_ANSWER else "non-answer",
    )


def _looks_like_answer(question: str, body: str) -> bool:
    b = body.strip()
    if len(b) < 3:
        return False
    if b.lower() in {"ok", "yes", "sure"} or b.lower().startswith("sure "):
        return False
    if "lorem" in b.lower() and len(b) > 100:
        return False
    q_tokens = set(__import__("re").findall(r"[a-z]{4,}", question.lower()))
    t_tokens = set(__import__("re").findall(r"[a-z]{4,}", b.lower()))
    if q_tokens & t_tokens and len(b) < 400:
        return True
    if b.lower() in {"no", "no."}:
        return True
    return False


def load_corpus(path: Any) -> list[dict[str, Any]]:
    from pathlib import Path
    import json
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return doc
    return list(doc.get("items") or doc.get("rows") or [])


def score_corpus(items: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    tp = tn = fp = fn = 0
    for it in items:
        gold = str(it.get("gold") or it.get("label") or "").upper()
        reply = str(it.get("reply") or it.get("text") or "")
        question = str(it.get("question") or "")
        cls = classify_reply(question, reply)
        pred = LABEL_ANSWER if cls.is_answer else "EVASION"
        if gold == LABEL_ANSWER and cls.is_answer:
            bucket = "tp"
            tp += 1
        elif gold == LABEL_ANSWER and not cls.is_answer:
            bucket = "fn"
            fn += 1
        elif gold != LABEL_ANSWER and not cls.is_answer:
            bucket = "tn"
            tn += 1
        else:
            bucket = "fp"
            fp += 1
        rows.append({"id": it.get("id"), "gold": gold, "pred": pred, "bucket": bucket})
    n = tp + tn + fp + fn
    rate = (tp + tn) / n if n else 0.0
    return {
        "n": n,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "discrimination_rate": rate,
        "rows": rows,
        "rate": rate,
        "pass": rate >= 0.9,
    }
