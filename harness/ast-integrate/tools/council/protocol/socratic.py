"""Socratic cross-examination with enforced response obligations (IMP-0292).

A directed question creates an :class:`Obligation` that the addressee must
discharge within ``due_in_turns`` kernel turns.  Discharge is *not* a byte
count: the addressee's reply is run through :func:`classify_reply`, which
decides whether the reply takes a position on the asked content.  Empty
replies, acknowledgements ("ok", "noted"), echoes of the question, stalls,
deferrals, refusals, subject changes and repetitive filler all leave the
obligation OPEN however many bytes they carry.  An obligation that reaches
its deadline without an ANSWER expires (or, with ``auto_escalate=True``, is
escalated into a fresh one-turn follow-up obligation on the same addressee).

The classifier is question-type aware and lexical (stdlib only):

* the interrogative that opens the question fixes its type (polar, quantity,
  identity/selection, causal, manner, time, place, open);
* *typed cues* satisfy typed questions: a hex digest of the length the named
  hash produces, a numeral or number word for "how many", the selected noun
  for "which <noun>"; a leading polar particle ("yes"/"no") answers a polar
  question unless it is followed by an off-topic clause;
* *evasion markers* (acknowledgement-only replies, stall phrases, deferrals,
  refusals, subject-change phrases, echoes, counter-questions, low
  type/token-ratio filler) are rejected;
* otherwise a reply counts as an answer only when it is *grounded* in the
  question's content words and carries a stance marker or enough overlap to
  be a statement about the asked content.

``naive_any_bytes_discharge`` is the defeated control: it fires on every
non-empty reply and is reported alongside the real classification so probes
can show the two disagree on stalls.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

STATE_OPEN = "OPEN"
STATE_DISCHARGED = "DISCHARGED"
STATE_EXPIRED = "EXPIRED"
STATE_ESCALATED = "ESCALATED"
STATES = (STATE_OPEN, STATE_DISCHARGED, STATE_EXPIRED, STATE_ESCALATED)

LABEL_ANSWER = "ANSWER"
LABEL_EVASION = "EVASION"
LABEL_NON_ANSWER = "NON_ANSWER"
LABELS = (LABEL_ANSWER, LABEL_EVASION, LABEL_NON_ANSWER)

Q_POLAR = "polar"
Q_QUANTITY = "quantity"
Q_IDENTITY = "identity"
Q_CAUSAL = "causal"
Q_MANNER = "manner"
Q_TIME = "time"
Q_PLACE = "place"
Q_OPEN = "open"

_WORD = re.compile(r"[a-z0-9][a-z0-9'\-]*")
_HEX = re.compile(r"\b[0-9a-f]{32,128}\b")
_DIGITS = re.compile(r"^\d+(\.\d+)?$")

_POLAR_LEADS = frozenset(
    {
        "does", "do", "did", "is", "are", "was", "were", "can", "could", "will",
        "would", "should", "shall", "has", "have", "had", "may", "might", "must",
    }
)
_POLAR_PARTICLES = frozenset(
    {
        "yes", "no", "yeah", "yep", "nope", "nah", "never", "correct", "incorrect",
        "true", "false", "affirmative", "negative", "indeed", "absolutely",
        "definitely", "certainly",
    }
)
_ACK_PARTICLES = frozenset(
    {
        "ok", "okay", "k", "kk", "sure", "noted", "right", "fine", "alright",
        "understood", "roger", "acknowledged", "ack", "thanks", "thank", "hmm",
        "hm", "uh", "um", "cool", "great", "good", "nice", "interesting", "gotcha",
        "got", "it", "copy",
    }
)
_REFUSALS = frozenset({"pass", "skip", "decline", "abstain", "next"})
_FILLER_TOKENS = frozenset(
    {
        "lorem", "ipsum", "dolor", "amet", "consectetur", "adipiscing", "elit",
        "asdf", "qwerty", "blah", "foo", "bar", "baz", "xxx", "yyy", "zzz", "etc",
    }
)
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "of", "on", "in", "to", "for", "and", "or", "but", "is",
        "are", "was", "were", "be", "been", "being", "does", "do", "did", "this",
        "that", "these", "those", "with", "from", "than", "then", "after",
        "before", "about", "into", "any", "all", "not", "its", "it's", "has",
        "have", "had", "will", "would", "should", "shall", "can", "could", "may",
        "might", "must", "by", "at", "as", "so", "if", "we", "you", "they", "he",
        "she", "it", "i", "me", "my", "our", "your", "their", "us", "them", "i'll",
        "i'm", "we'll", "let's", "there", "here", "what", "which", "who", "whom",
        "whose", "why", "how", "when", "where", "many", "much", "some", "such",
        "very", "just", "also", "only", "even", "still", "yet", "too", "up",
        "out", "over", "under", "again", "own", "same", "more", "most", "other",
        "each", "few", "both", "per", "via", "no", "yes", "ok", "sure",
    }
)
_STANCE_MARKERS = frozenset(
    {
        "is", "are", "was", "were", "be", "does", "do", "did", "not", "never",
        "always", "must", "should", "can", "cannot", "can't", "will", "would",
        "remain", "remains", "require", "requires", "stay", "stays", "count",
        "counts", "mean", "means", "hold", "holds", "apply", "applies", "need",
        "needs", "only", "instead", "because", "therefore", "hence", "thus",
        "true", "false", "correct", "incorrect", "yes", "no",
    }
)
_CAUSAL_MARKERS = frozenset(
    {"because", "since", "due", "owing", "reason", "hence", "therefore", "thus", "so"}
)
_NUMBER_WORDS = frozenset(
    {
        "zero", "none", "one", "single", "two", "three", "four", "five", "six",
        "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen",
        "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
        "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
        "ninety", "hundred", "thousand", "million", "dozen",
    }
)
_HASH_LENGTHS = {
    "md5": 32,
    "sha1": 40,
    "sha-1": 40,
    "sha224": 56,
    "sha-224": 56,
    "sha256": 64,
    "sha-256": 64,
    "sha384": 96,
    "sha-384": 96,
    "sha512": 128,
    "sha-512": 128,
}
_STALL_PHRASES = (
    r"\b(?:interesting|good|great|fair|excellent|tough|hard|big) question\b",
    r"\blet me think\b",
    r"\bthat'?s (?:a )?(?:good|great|fair|interesting) (?:one|point)\b",
    r"\bno comment\b",
    r"\bfood for thought\b",
)
_DEFERRAL_PHRASES = (
    r"\bcircle back\b",
    r"\bget back to (?:you|this|that)\b",
    r"\blater\b",
    r"\brevisit\b",
    r"\banother time\b",
    r"\bafterwards\b",
    r"\beventually\b",
    r"\bsome other time\b",
    r"\bfollow up (?:on this )?(?:later|afterwards|tomorrow)\b",
    r"\btable (?:this|that|it)\b",
    r"\btomorrow\b",
    r"\bnext (?:week|time|meeting)\b",
)
_SUBJECT_CHANGE_PHRASES = (
    r"\binstead\b",
    r"\brather than (?:this|that)\b",
    r"\blet'?s (?:talk|discuss|chat|move on|focus on|get)\b",
    r"\bmoving on\b",
    r"\bchange (?:the |of )?(?:subject|topic)\b",
    r"\bnot worry about\b",
    r"\bforget about\b",
    r"\bnever mind\b",
    r"\banyway\b",
    r"\bin general\b",
)
_STALL_RE = re.compile("|".join(_STALL_PHRASES), re.I)
_DEFERRAL_RE = re.compile("|".join(_DEFERRAL_PHRASES), re.I)
_SUBJECT_CHANGE_RE = re.compile("|".join(_SUBJECT_CHANGE_PHRASES), re.I)


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #
def naive_any_bytes_discharge(text: str) -> bool:
    """The defeated control: any non-whitespace byte counts as a response."""
    return bool(str(text or "").strip())


def words(text: str) -> list[str]:
    """Lower-cased word tokens (letters, digits, apostrophes, hyphens)."""
    return _WORD.findall(str(text or "").lower())


def stem(token: str) -> str:
    """Light suffix stripping so ``replies``/``reply`` and ``counted``/``count`` meet."""
    t = token
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 5 and t.endswith("ing"):
        t = t[:-3]
    elif len(t) > 5 and t.endswith("ed"):
        t = t[:-2]
    elif len(t) > 4 and t.endswith("es"):
        t = t[:-2]
    elif len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    return t


def content_stems(tokens: Iterable[str]) -> set[str]:
    """Stems of the tokens that carry content (no stopwords, particles, filler)."""
    out: set[str] = set()
    for tok in tokens:
        if len(tok) < 3 or tok in _STOPWORDS or tok in _FILLER_TOKENS:
            continue
        if tok in _ACK_PARTICLES or tok in _POLAR_PARTICLES:
            continue
        out.add(stem(tok))
    return out


def normalise(text: str) -> str:
    """Whitespace/punctuation-insensitive lower-cased form for echo detection."""
    return " ".join(words(text))


def question_type(question: str) -> str:
    """Classify the interrogative that opens ``question``."""
    toks = words(question)
    if not toks:
        return Q_OPEN
    first = toks[0]
    second = toks[1] if len(toks) > 1 else ""
    if first == "how" and second in {"many", "much", "often", "long", "far", "old"}:
        return Q_QUANTITY
    if first in {"what", "which", "who", "whom", "whose"}:
        return Q_IDENTITY
    if first == "why":
        return Q_CAUSAL
    if first == "how":
        return Q_MANNER
    if first == "when":
        return Q_TIME
    if first == "where":
        return Q_PLACE
    if first in _POLAR_LEADS:
        return Q_POLAR
    if "?" in str(question) and toks[-1] in _POLAR_LEADS:
        return Q_POLAR
    return Q_OPEN


def expected_hex_length(question: str) -> int | None:
    """Digest length (hex chars) when the question names a hash algorithm."""
    low = str(question or "").lower()
    for name, length in _HASH_LENGTHS.items():
        if re.search(r"\b" + re.escape(name) + r"\b", low):
            return length
    if re.search(r"\b(?:hash|digest|checksum)\b", low):
        return 0  # any hex digest length accepted
    return None


def selected_noun(question: str) -> str | None:
    """The noun a ``which <noun>`` / ``what <noun>`` question selects over."""
    toks = words(question)
    if len(toks) < 2 or toks[0] not in {"which", "what", "whose"}:
        return None
    for tok in toks[1:4]:
        if tok not in _STOPWORDS and tok not in _POLAR_LEADS and len(tok) >= 3:
            return stem(tok)
    return None


def _type_token_ratio(tokens: list[str]) -> float:
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def _sentence_count(text: str) -> int:
    parts = [p for p in re.split(r"[.!?;]+", str(text or "")) if p.strip()]
    return max(1, len(parts))


# --------------------------------------------------------------------------- #
# reply classification
# --------------------------------------------------------------------------- #
@dataclass
class ReplyClass:
    """Outcome of :func:`classify_reply` for one (question, reply) pair."""

    label: str
    is_answer: bool
    reply_bytes: int
    reason: str
    question_type: str
    cue: str
    overlap: list[str] = field(default_factory=list)
    naive_bytes_would_discharge: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _typed_cue(question: str, qtype: str, reply: str, tokens: list[str]) -> str | None:
    """A value of the type the question asks for, if the reply carries one."""
    hex_len = expected_hex_length(question)
    if hex_len is not None:
        for m in _HEX.finditer(str(reply or "").lower()):
            if hex_len == 0 or len(m.group(0)) == hex_len:
                return f"hex-digest:{len(m.group(0))}"
    if qtype == Q_QUANTITY:
        for tok in tokens:
            if _DIGITS.match(tok) or tok in _NUMBER_WORDS:
                return f"number:{tok}"
    if qtype == Q_IDENTITY:
        noun = selected_noun(question)
        if noun and noun in content_stems(tokens):
            return f"names-selected:{noun}"
    return None


def classify_reply(question: str | None, reply: str | None = None, text: str | None = None) -> ReplyClass:
    """Decide whether ``reply`` answers ``question`` (takes a position on it).

    Returns a :class:`ReplyClass` whose ``label`` is ``ANSWER``, ``EVASION`` or
    ``NON_ANSWER`` (empty / wordless) and whose ``reason`` names the rule that
    fired.  ``naive_bytes_would_discharge`` records what the defeated
    byte-counting control would have said about the same reply.
    """
    body = str(reply if reply is not None else (text or ""))
    q = str(question or "")
    qtype = question_type(q)
    n_bytes = len(body.encode("utf-8"))
    naive = naive_any_bytes_discharge(body)

    def verdict(label: str, reason: str, cue: str = "", overlap: Iterable[str] = ()) -> ReplyClass:
        return ReplyClass(
            label=label,
            is_answer=label == LABEL_ANSWER,
            reply_bytes=n_bytes,
            reason=reason,
            question_type=qtype,
            cue=cue,
            overlap=sorted(overlap),
            naive_bytes_would_discharge=naive,
        )

    if not body.strip():
        return verdict(LABEL_NON_ANSWER, "empty")
    tokens = words(body)
    if not tokens:
        return verdict(LABEL_NON_ANSWER, "no-words")

    q_content = content_stems(words(q))
    r_content = content_stems(tokens)
    overlap = q_content & r_content

    # 1. a value of the asked type settles the question outright
    typed = _typed_cue(q, qtype, body, tokens)
    if typed:
        return verdict(LABEL_ANSWER, "typed-value", typed, overlap)

    # 2. echoing the question back is not a position on it
    if normalise(body) == normalise(q) and q.strip():
        return verdict(LABEL_EVASION, "echo")

    # 3. acknowledgement- or refusal-only replies
    substantive = [t for t in tokens if t not in _FILLER_TOKENS]
    if substantive and all(t in _ACK_PARTICLES for t in substantive):
        return verdict(LABEL_EVASION, "acknowledgement", substantive[0])
    if substantive and all(t in _REFUSALS or t in _ACK_PARTICLES for t in substantive):
        return verdict(LABEL_EVASION, "refusal", substantive[0])
    if not substantive:
        return verdict(LABEL_EVASION, "filler", tokens[0])

    # 4. polar questions answered with a leading particle
    lead = tokens[0]
    if lead in _POLAR_PARTICLES:
        remainder = content_stems(tokens[1:])
        if qtype == Q_POLAR or not remainder:
            if not remainder:
                return verdict(LABEL_ANSWER, "bare-polar", lead)
            if overlap:
                return verdict(LABEL_ANSWER, "polar-grounded", lead, overlap)
            if len(remainder) >= 3 or _SUBJECT_CHANGE_RE.search(body):
                return verdict(LABEL_EVASION, "polar-then-subject-change", lead)
            return verdict(LABEL_ANSWER, "polar-qualified", lead)

    # 5. stalls, deferrals, refusals, subject changes
    stall = _STALL_RE.search(body)
    if stall:
        return verdict(LABEL_EVASION, "stall", stall.group(0))
    if lead in _REFUSALS:
        return verdict(LABEL_EVASION, "refusal", lead)
    deferral = _DEFERRAL_RE.search(body)
    if deferral:
        return verdict(LABEL_EVASION, "deferral", deferral.group(0))
    change = _SUBJECT_CHANGE_RE.search(body)
    if change:
        return verdict(LABEL_EVASION, "subject-change", change.group(0))

    # 6. repetitive filler floods
    ratio = _type_token_ratio(tokens)
    if len(tokens) >= 8 and ratio <= 0.25:
        return verdict(LABEL_EVASION, "filler-repetition", f"ttr={ratio:.3f}")

    # 7. paraphrased echo: nothing beyond the question's own content words
    if r_content and r_content <= q_content and not any(t in _STANCE_MARKERS for t in tokens):
        return verdict(LABEL_EVASION, "echo", "subset")
    if body.strip().endswith("?") and _sentence_count(body) == 1:
        return verdict(LABEL_EVASION, "counter-question")

    # 8. causal questions want a because-clause about the asked content
    if qtype == Q_CAUSAL and any(t in _CAUSAL_MARKERS for t in tokens) and (r_content - q_content):
        return verdict(LABEL_ANSWER, "causal", next(t for t in tokens if t in _CAUSAL_MARKERS), overlap)

    # 9. grounded statement about the asked content
    stance = [t for t in tokens if t in _STANCE_MARKERS]
    if len(overlap) >= 2 or (overlap and stance):
        return verdict(LABEL_ANSWER, "grounded", stance[0] if stance else "overlap", overlap)
    if overlap:
        return verdict(LABEL_EVASION, "fragment", "", overlap)
    return verdict(LABEL_EVASION, "off-topic")


# --------------------------------------------------------------------------- #
# obligations and the protocol clock
# --------------------------------------------------------------------------- #
@dataclass
class Obligation:
    """A directed question the ``addressee`` owes an answer to."""

    id: str
    asker: str
    addressee: str
    question: str
    state: str = STATE_OPEN
    age_turns: int = 0
    due_in_turns: int = 3
    discharged_turn: int | None = None
    expired_turn: int | None = None
    escalated_turn: int | None = None
    last_reason: str = ""
    kind: str = "question"
    parent_id: str | None = None
    child_id: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_open(self) -> bool:
        return self.state == STATE_OPEN

    @property
    def overdue(self) -> bool:
        return self.state == STATE_OPEN and self.age_turns >= self.due_in_turns

    def as_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "age_turns": self.age_turns,
            "addressee": self.addressee,
            "asker": self.asker,
            "kind": self.kind,
            "parent_id": self.parent_id,
            "child_id": self.child_id,
            "due_in_turns": self.due_in_turns,
            "discharged_turn": self.discharged_turn,
            "expired_turn": self.expired_turn,
            "escalated_turn": self.escalated_turn,
            "last_reason": self.last_reason,
        }


class ObligationError(KeyError):
    """Raised for an unknown obligation id or an illegal state transition."""


class SocraticProtocol:
    """Tracks directed questions as obligations and ages them per kernel turn.

    Every :meth:`record_turn` advances the protocol clock by one turn.  Each
    OPEN obligation ages by one; if the speaker is its addressee the reply is
    classified and an ANSWER discharges it.  An obligation whose age reaches
    ``due_in_turns`` without discharge expires, or is escalated when the
    protocol was built with ``auto_escalate=True``.
    """

    def __init__(self, default_due_in_turns: int = 3, auto_escalate: bool = False) -> None:
        if int(default_due_in_turns) < 1:
            raise ValueError("default_due_in_turns must be >= 1")
        self.default_due_in_turns = int(default_due_in_turns)
        self.auto_escalate = bool(auto_escalate)
        self._obs: dict[str, Obligation] = {}
        self._seq = 0
        self._clock = 0
        self._turns: list[dict[str, Any]] = []

    # -- creation ---------------------------------------------------------- #
    def _new_id(self) -> str:
        self._seq += 1
        return f"ob-{self._seq:04d}"

    def ask(
        self,
        asker: str,
        addressee: str,
        question: str,
        due_in_turns: int | None = None,
    ) -> Obligation:
        """Direct ``question`` from ``asker`` at ``addressee``; returns the OPEN obligation."""
        if not str(question or "").strip():
            raise ValueError("a directed question must have content")
        if not asker or not addressee:
            raise ValueError("asker and addressee are required")
        if asker == addressee:
            raise ValueError("a participant cannot oblige itself")
        due = int(due_in_turns if due_in_turns is not None else self.default_due_in_turns)
        if due < 1:
            raise ValueError("due_in_turns must be >= 1")
        ob = Obligation(
            id=self._new_id(),
            asker=asker,
            addressee=addressee,
            question=str(question),
            due_in_turns=due,
        )
        ob.history.append({"turn": self._clock, "event": "asked"})
        self._obs[ob.id] = ob
        return ob

    # -- lookup ------------------------------------------------------------ #
    def get(self, oid: str) -> Obligation:
        try:
            return self._obs[oid]
        except KeyError as exc:
            raise ObligationError(f"unknown obligation {oid!r}") from exc

    def by_state(self, state: str) -> list[Obligation]:
        return [o for o in self._obs.values() if o.state == state]

    def open_for(self, addressee: str) -> list[Obligation]:
        return [o for o in self._obs.values() if o.is_open and o.addressee == addressee]

    @property
    def clock(self) -> int:
        return self._clock

    def turns(self) -> list[dict[str, Any]]:
        """Every recorded turn with its per-obligation evaluations."""
        return [dict(t) for t in self._turns]

    # -- the clock --------------------------------------------------------- #
    def record_turn(self, speaker: str, text: str) -> dict[str, Any]:
        """Advance one kernel turn; age, discharge, expire or escalate obligations.

        Returns the turn record: ``{"turn", "speaker", "reply_bytes",
        "naive_bytes_would_discharge", "evaluations": [...]}`` where each
        evaluation covers one obligation that was OPEN when the turn began.
        """
        self._clock += 1
        body = str(text or "")
        record: dict[str, Any] = {
            "turn": self._clock,
            "speaker": speaker,
            "reply_bytes": len(body.encode("utf-8")),
            "naive_bytes_would_discharge": naive_any_bytes_discharge(body),
            "evaluations": [],
        }
        for ob in [o for o in self._obs.values() if o.is_open]:
            before = ob.state
            ob.age_turns += 1
            evaluation: dict[str, Any] = {
                "obligation_id": ob.id,
                "addressee": ob.addressee,
                "speaker_is_addressee": speaker == ob.addressee,
                "age_turns": ob.age_turns,
                "due_in_turns": ob.due_in_turns,
                "state_before": before,
                "classification": None,
                "outcome": "aged",
            }
            if speaker == ob.addressee:
                cls = classify_reply(ob.question, body)
                evaluation["classification"] = cls.as_dict()
                if cls.is_answer:
                    ob.state = STATE_DISCHARGED
                    ob.discharged_turn = ob.age_turns
                    ob.last_reason = f"answered:{cls.reason}"
                    ob.history.append({"turn": self._clock, "event": "discharged", "reason": cls.reason})
                    evaluation["outcome"] = "discharged"
                else:
                    ob.last_reason = f"non-answer:{cls.reason}"
                    ob.history.append({"turn": self._clock, "event": "non-answer", "reason": cls.reason})
                    evaluation["outcome"] = "non-answer"
            if ob.is_open and ob.age_turns >= ob.due_in_turns:
                if self.auto_escalate:
                    follow = self.escalate(ob.id)
                    evaluation["outcome"] = "escalated"
                    evaluation["follow_up_id"] = follow.id
                else:
                    ob.state = STATE_EXPIRED
                    ob.expired_turn = ob.age_turns
                    ob.last_reason = "deadline"
                    ob.history.append({"turn": self._clock, "event": "expired"})
                    evaluation["outcome"] = "expired"
            evaluation["state_after"] = ob.state
            record["evaluations"].append(evaluation)
        self._turns.append(record)
        return record

    def expire(self, oid: str) -> Obligation:
        """Expire an OPEN obligation explicitly (deadline enforced by the chair)."""
        ob = self.get(oid)
        if not ob.is_open:
            raise ObligationError(f"{oid} is {ob.state}, only OPEN obligations expire")
        ob.state = STATE_EXPIRED
        ob.expired_turn = ob.age_turns
        ob.last_reason = "deadline"
        ob.history.append({"turn": self._clock, "event": "expired"})
        return ob

    def escalate(self, oid: str) -> Obligation:
        """Mark ``oid`` ESCALATED and open a one-turn follow-up on the same addressee."""
        ob = self.get(oid)
        if ob.state in (STATE_DISCHARGED, STATE_ESCALATED):
            raise ObligationError(f"{oid} is {ob.state} and cannot be escalated")
        ob.state = STATE_ESCALATED
        ob.escalated_turn = ob.age_turns
        ob.last_reason = "escalated"
        follow = Obligation(
            id=self._new_id(),
            asker=ob.asker,
            addressee=ob.addressee,
            question="FOLLOW: " + ob.question,
            due_in_turns=1,
            kind="escalation",
            parent_id=ob.id,
        )
        follow.history.append({"turn": self._clock, "event": "asked", "escalates": ob.id})
        ob.child_id = follow.id
        ob.history.append({"turn": self._clock, "event": "escalated", "follow_up": follow.id})
        self._obs[follow.id] = follow
        return follow

    def discharge(self, oid: str, reason: str = "chair") -> Obligation:
        """Discharge an OPEN obligation by explicit chair ruling."""
        ob = self.get(oid)
        if not ob.is_open:
            raise ObligationError(f"{oid} is {ob.state}, only OPEN obligations discharge")
        ob.state = STATE_DISCHARGED
        ob.discharged_turn = ob.age_turns
        ob.last_reason = f"answered:{reason}"
        ob.history.append({"turn": self._clock, "event": "discharged", "reason": reason})
        return ob

    # -- reporting --------------------------------------------------------- #
    def ledger(self) -> list[dict[str, Any]]:
        """One row per obligation in creation order (deterministic, no clocks)."""
        return [o.as_row() for o in self._obs.values()]

    def summary(self) -> dict[str, int]:
        counts = {state: 0 for state in STATES}
        for o in self._obs.values():
            counts[o.state] = counts.get(o.state, 0) + 1
        counts["total"] = len(self._obs)
        counts["turns"] = self._clock
        return counts


def ledger_digest(rows: list[dict[str, Any]]) -> str:
    """sha256 of the canonical JSON of ``rows``."""
    blob = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# labelled-corpus scoring
# --------------------------------------------------------------------------- #
def load_corpus(path: Any) -> list[dict[str, Any]]:
    """Load a labelled corpus (``{"items": [...]}`` or a bare list) and validate it."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    items = doc if isinstance(doc, list) else list(doc.get("items") or doc.get("rows") or [])
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"corpus item {i} is not an object")
        gold = str(it.get("gold") or it.get("label") or "").upper()
        if gold not in LABELS:
            raise ValueError(f"corpus item {it.get('id', i)} has unknown gold label {gold!r}")
        iid = str(it.get("id") or f"item-{i:03d}")
        if iid in seen:
            raise ValueError(f"duplicate corpus id {iid}")
        seen.add(iid)
        out.append(dict(it, id=iid, gold=gold))
    return out


def score_corpus(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Score :func:`classify_reply` against gold labels (ANSWER vs not-answer)."""
    rows: list[dict[str, Any]] = []
    tp = tn = fp = fn = 0
    for it in items:
        gold = str(it.get("gold") or it.get("label") or "").upper()
        reply = str(it.get("reply") if it.get("reply") is not None else it.get("text") or "")
        question = str(it.get("question") or "")
        cls = classify_reply(question, reply)
        gold_answer = gold == LABEL_ANSWER
        if gold_answer and cls.is_answer:
            bucket = "tp"
            tp += 1
        elif gold_answer:
            bucket = "fn"
            fn += 1
        elif not cls.is_answer:
            bucket = "tn"
            tn += 1
        else:
            bucket = "fp"
            fp += 1
        rows.append(
            {
                "id": it.get("id"),
                "gold": gold,
                "pred": cls.label,
                "bucket": bucket,
                "reason": cls.reason,
                "cue": cls.cue,
                "reply_bytes": cls.reply_bytes,
                "naive_bytes_would_discharge": cls.naive_bytes_would_discharge,
            }
        )
    n = tp + tn + fp + fn
    rate = (tp + tn) / n if n else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "n": n,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "discrimination_rate": rate,
        "rate": rate,
        "accuracy": rate,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "byte_counter_defeated_n": sum(
            1 for r in rows if r["gold"] != LABEL_ANSWER and r["naive_bytes_would_discharge"] and r["pred"] != LABEL_ANSWER
        ),
        "rows": rows,
        "pass": rate >= 0.9,
    }


__all__ = [
    "LABELS",
    "LABEL_ANSWER",
    "LABEL_EVASION",
    "LABEL_NON_ANSWER",
    "Obligation",
    "ObligationError",
    "ReplyClass",
    "STATES",
    "STATE_DISCHARGED",
    "STATE_ESCALATED",
    "STATE_EXPIRED",
    "STATE_OPEN",
    "SocraticProtocol",
    "classify_reply",
    "content_stems",
    "expected_hex_length",
    "ledger_digest",
    "load_corpus",
    "naive_any_bytes_discharge",
    "question_type",
    "score_corpus",
    "selected_noun",
    "stem",
    "words",
]
