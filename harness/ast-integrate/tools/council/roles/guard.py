"""Runtime role-enforcement guard for council turns.

Two units define this module's contract:

* IMP-0281 -- the guard itself. :class:`RoleGuard` inspects one *turn* (a mapping
  with ``id``, ``participant_id``, ``role``, ``content`` and an optional structured
  ``action``) and answers whether the participant performed an act its role's
  mandate does not grant. ``inspect_prose`` reads the words, ``inspect_structured``
  reads the ``action`` field, ``inspect`` combines them (structured wins), and
  ``enforce`` additionally records every rejection on an append-only ledger that
  ``rejections()`` returns. :func:`precision_recall` scores a labelled corpus.
* ADV-0103 -- reads :data:`DEFAULT_MANDATES` and requires the judge's mandate to be
  an object whose ``may_veto`` is True. The veto is *declared* here and deliberately
  *unwired* in ``tools.council.sdk.execute_spec``, which never constructs a guard;
  that gap is the subject of ADV-0103's structural audit.

Use versus mention. A critic who writes ``I propose option A`` performs a proposal
and breaches; a critic who writes ``The proposer said "I propose option A"`` merely
mentions one. The prose pass therefore (1) strips quotations and blockquotes,
(2) marks conditional / irrealis clauses as hypothetical, (3) marks negated forms
(``I am not voting``), and only then matches first-person performatives (``I vote``,
``I propose``, ``I veto`` ...) and formal labels (``Vote:``, ``Proposal:``).
Third-person reports (``The chair voted aye``) never match because every performative
pattern is anchored on a first-person subject or a line label.

Structured beats prose. When a turn carries an ``action`` field the council runtime
has already classified the act, so the wording is advisory: ``action="speak"`` with
vote-like prose is allowed, ``action="propose"`` from a critic is a breach even when
the prose is innocuous. Unknown actions and unregistered roles fail closed.

The module is deterministic and stdlib-only. Ledger records carry no wall-clock time
unless a ``clock`` callable is injected into :class:`RoleGuard`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

__all__ = [
    "ACTIONS",
    "ACTION_FLAGS",
    "BREACH",
    "DEFAULT_MANDATES",
    "GuardError",
    "InspectResult",
    "MENTION",
    "Mandate",
    "PERMITTED",
    "Performative",
    "ProseAnalysis",
    "RoleGuard",
    "analyse_prose",
    "normalise_action",
    "normalise_role",
    "precision_recall",
    "strip_quotations",
]

#: Classification vocabulary. BREACH: an act the mandate does not grant. PERMITTED:
#: an act the mandate grants. MENTION: nothing performed in this turn (either no act
#: at all, or acts present only as quotation, hypothesis, negation or report).
BREACH = "BREACH"
PERMITTED = "PERMITTED"
MENTION = "MENTION"

#: Performative acts a turn can attempt, each paired with the mandate flag it needs.
ACTION_FLAGS: Mapping[str, str] = MappingProxyType(
    {
        "speak": "may_speak",
        "propose": "may_propose",
        "critique": "may_critique",
        "vote": "may_vote",
        "veto": "may_veto",
        "override": "may_override",
        "rule": "may_bind",
        "chair": "may_chair",
        "synthesise": "may_synthesise",
    }
)
ACTIONS: tuple[str, ...] = tuple(ACTION_FLAGS)

_ACTION_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "abstain": "vote",
        "ballot": "vote",
        "bind": "rule",
        "criticise": "critique",
        "criticize": "critique",
        "moderate": "chair",
        "overrule": "override",
        "ruling": "rule",
        "synthesize": "synthesise",
    }
)
_ROLE_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "domain-expert": "domain_expert",
        "expert": "domain_expert",
        "non-voter": "nonvoter",
        "non_voter": "nonvoter",
        "synthesizer": "synthesiser",
    }
)


class GuardError(ValueError):
    """A turn or a mandate table handed to the guard is malformed."""


def normalise_action(action: Any) -> str | None:
    """Canonical action name, or None when the turn carries no structured action.

    Unknown names are returned unchanged (lower-cased) so the caller can refuse them
    with the original spelling in the reason.
    """
    if action is None:
        return None
    text = str(action).strip().lower().replace("-", "_")
    if not text:
        return None
    return _ACTION_ALIASES.get(text, text)


def normalise_role(role: Any) -> str:
    text = str(role or "").strip().lower().replace(" ", "_")
    return _ROLE_ALIASES.get(text, text)


# ------------------------------------------------------------------------ mandates


@dataclass(frozen=True)
class Mandate:
    """What one role may do. Every flag defaults to False except the floor right."""

    role: str
    may_speak: bool = True
    may_propose: bool = False
    may_critique: bool = False
    may_vote: bool = False
    may_veto: bool = False
    may_override: bool = False
    may_bind: bool = False
    may_chair: bool = False
    may_synthesise: bool = False
    description: str = ""

    def permits(self, action: str) -> bool:
        """True when this mandate grants ``action``; unknown actions are never granted."""
        flag = ACTION_FLAGS.get(normalise_action(action) or "")
        return bool(flag) and bool(getattr(self, flag))

    def rights(self) -> tuple[str, ...]:
        """Granted actions in :data:`ACTIONS` order."""
        return tuple(action for action in ACTIONS if self.permits(action))

    def grants(self) -> dict[str, Any]:
        """Grant map in the shape ``tools.council.roles.mandate.seat`` consumes.

        Only the rights both modules share are translated (``speaking``, ``vote``,
        ``veto``); tool and source access are not mandate-guard concerns.
        """
        grants: dict[str, set[str]] = {}
        if self.may_speak:
            grants["speaking"] = {"floor"}
        if self.may_vote:
            grants["vote"] = {"ballot"}
        if self.may_veto:
            grants["veto"] = {"veto"}
        return {"name": self.role, "grants": grants}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


#: Default role matrix. Roles the IMP-0281 corpus exercises come first; the council
#: seats that ``tools.council.sdk`` runs (every seat casts a ballot there) follow.
#: No role may override the tally: ``may_override`` is False everywhere, which is the
#: property ADV-0103 checks the SDK actually honours.
DEFAULT_MANDATES: Mapping[str, Mandate] = MappingProxyType(
    {
        "proposer": Mandate(
            "proposer",
            may_propose=True,
            description="tables proposals and motions; does not vote on them",
        ),
        "critic": Mandate(
            "critic",
            may_critique=True,
            description="critiques tabled proposals; never tables one and never votes",
        ),
        "voter": Mandate(
            "voter",
            may_vote=True,
            description="casts ballots on tabled proposals; does not table them",
        ),
        "nonvoter": Mandate(
            "nonvoter",
            description="holds the floor only; no ballot",
        ),
        "observer": Mandate(
            "observer",
            description="speaks for the record only; no ballot",
        ),
        "chair": Mandate(
            "chair",
            may_chair=True,
            may_bind=True,
            description="procedural control and binding procedural rulings; no veto, no ballot",
        ),
        "moderator": Mandate(
            "moderator",
            may_chair=True,
            may_bind=True,
            description="runs the rounds; procedural rulings bind; no veto, no ballot",
        ),
        "synthesiser": Mandate(
            "synthesiser",
            may_synthesise=True,
            description="merges positions into a synthesis; does not table proposals",
        ),
        "judge": Mandate(
            "judge",
            may_vote=True,
            may_veto=True,
            description=(
                "one voting seat with a declared veto; the veto is not wired into "
                "tools.council.sdk.execute_spec and the judge may not override the tally"
            ),
        ),
        "advocate": Mandate(
            "advocate",
            may_propose=True,
            may_vote=True,
            description="argues for the proposal and casts a ballot",
        ),
        "skeptic": Mandate(
            "skeptic",
            may_critique=True,
            may_vote=True,
            description="argues against the proposal and casts a ballot",
        ),
        "domain_expert": Mandate(
            "domain_expert",
            may_vote=True,
            description="answers on the merits and casts a ballot",
        ),
        "juror": Mandate(
            "juror",
            may_vote=True,
            description="casts a ballot; no proposals",
        ),
    }
)


# --------------------------------------------------------------- prose analysis

#: Quotation forms removed before performatives are matched (use-vs-mention).
_BLOCKQUOTE = re.compile(r"^[ \t]*>.*(?:\n|$)", re.MULTILINE)
_DOUBLE_QUOTED = re.compile(r"\"[^\"\n]{1,600}?\"|\u201c[^\u201d\n]{1,600}?\u201d")
# A single quote counts as a quotation mark only when it is not glued to a word
# character on the outside, so apostrophes (``Yesterday's``, ``don't``) survive.
_SINGLE_QUOTED = re.compile(r"(?<!\w)'[^'\n]{1,600}?'(?!\w)|\u2018[^\u2019\n]{1,600}?\u2019")
_BACKTICKED = re.compile(r"`[^`\n]{1,600}?`")

_CLAUSE_BREAK = re.compile(r"[,;:.!?\n]+")
_CONDITIONAL_LEAD = re.compile(
    r"^\s*(?:if|unless|suppose|supposing|imagine|assuming|provided|were|had|should|"
    r"whether|hypothetically)\b",
    re.IGNORECASE,
)
_IRREALIS = re.compile(
    r"\b(?:were\s+to|would|could|might|hypothetically|in\s+theory|in\s+principle)\b",
    re.IGNORECASE,
)
_NEGATED = re.compile(
    r"\bI\s+(?:do\s+not|don't|did\s+not|didn't|will\s+not|won't|shall\s+not|cannot|"
    r"can't|never|am\s+not|was\s+not)\b"
    r"|\b(?:this|that|it)\s+is\s+not\s+(?:a|an|my)\s+(?:vote|ballot|proposal|motion|veto)\b"
    r"|\bnot\s+my\s+(?:vote|ballot|proposal|motion|veto)\b"
    r"|\bnot\s+(?:voting|proposing|vetoing)\b",
    re.IGNORECASE,
)

_FIRST = r"\bI\s+(?:(?:hereby|formally|now|therefore|thus|also|officially|solemnly)\s+)?"

#: (action, pattern). Every pattern is either first-person ("I ...", "my vote is")
#: or a line label ("Vote:"), so third-person reports never match.
_PERFORMATIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (action, re.compile(pattern, re.IGNORECASE | re.MULTILINE))
    for action, pattern in (
        ("vote", _FIRST + r"(?:vote|abstain)\b"),
        ("vote", _FIRST + r"cast\s+(?:my\s+|a\s+)?(?:ballot|vote)\b"),
        ("vote", r"\bmy\s+(?:vote|ballot)\s+(?:is|goes)\b"),
        ("vote", r"^\s*(?:vote|ballot)\s*:"),
        ("propose", _FIRST + r"propose\b"),
        ("propose", r"\blet\s+me\s+propose\b"),
        ("propose", r"\bmy\s+proposal\s+is\b"),
        ("propose", _FIRST + r"move\s+(?:that|to|the|for)\b"),
        ("propose", _FIRST + r"(?:submit|table|put\s+forward)\b[^.;!?\n]*?\b(?:proposal|motion)\b"),
        ("propose", r"^\s*(?:proposal|motion)\s*:"),
        ("veto", _FIRST + r"veto\b"),
        ("veto", r"^\s*veto\s*:"),
        ("override", _FIRST + r"(?:overrule|override)\b"),
        ("rule", _FIRST + r"rule\s+that\b"),
        ("rule", r"^\s*ruling\s*:"),
        (
            "chair",
            _FIRST
            + r"(?:call|declare)\s+(?:this|the)\s+(?:session|meeting|round|council)\s+"
            r"(?:to\s+order|open|closed|adjourned)\b",
        ),
        ("chair", _FIRST + r"recogni[sz]e\s+the\b"),
        ("synthesise", _FIRST + r"synthesi[sz]e\b"),
        ("synthesise", r"^\s*synthesis\s*:"),
        ("critique", _FIRST + r"(?:lodge|raise|file)\s+(?:a|an|the)\s+(?:formal\s+)?(?:objection|critique)\b"),
        ("critique", r"^\s*(?:critique|objection)\s*:"),
    )
)

#: Loose first-person form used only to *name* an act inside a hypothetical or
#: negated clause (so the reason can say what was mentioned). Never counts as performed.
_LOOSE_FIRST_PERSON = re.compile(
    r"\bI\b[^,;.!?\n]{0,60}?\b(?P<verb>vot(?:e|ing)|propos(?:e|ing)|veto(?:ing)?|abstain(?:ing)?|"
    r"overrul(?:e|ing)|overrid(?:e|ing))\b",
    re.IGNORECASE,
)
_ACT_WORDS = re.compile(
    r"\b(?P<word>vot(?:e|es|ed|ing)|ballots?|propos(?:e|es|ed|al|als|ing)|motions?|"
    r"veto(?:es|ed|ing)?|abstain(?:s|ed|ing)?|overrul(?:e|es|ed|ing)|overrid(?:e|es|ing|den))\b",
    re.IGNORECASE,
)


def _act_of_word(word: str) -> str:
    lowered = word.lower()
    if lowered.startswith(("vot", "ballot", "abstain")):
        return "vote"
    if lowered.startswith(("propos", "motion")):
        return "propose"
    if lowered.startswith("veto"):
        return "veto"
    return "override"


def strip_quotations(text: str) -> tuple[str, list[str]]:
    """Remove blockquote lines and quoted spans from ``text``.

    Returns the residue (each removed span replaced by one space so word boundaries
    survive) and the removed spans grouped by kind: blockquotes, then double-,
    single- and backtick-quoted spans.
    """
    removed: list[str] = []

    def take(match: re.Match[str]) -> str:
        removed.append(match.group(0).strip())
        return " "

    residue = _BLOCKQUOTE.sub(take, text)
    residue = _DOUBLE_QUOTED.sub(take, residue)
    residue = _SINGLE_QUOTED.sub(take, residue)
    residue = _BACKTICKED.sub(take, residue)
    return residue, removed


@dataclass(frozen=True)
class Performative:
    """One act found in prose, with where it sat and how it should be read."""

    action: str
    text: str
    start: int
    end: int
    kind: str  # performed | quoted | hypothetical | negated
    clause: str


@dataclass(frozen=True)
class ProseAnalysis:
    """Everything the prose pass learned about one turn's content."""

    content: str
    analysed: str
    strip_quotes: bool
    stripped_spans: tuple[str, ...]
    performed: tuple[Performative, ...]
    mentioned: tuple[Performative, ...]
    referenced: tuple[str, ...]

    def actions(self) -> tuple[str, ...]:
        """Distinct performed actions in order of first appearance."""
        return tuple(dict.fromkeys(p.action for p in self.performed))

    def mention_kinds(self) -> tuple[str, ...]:
        return tuple(sorted({p.kind for p in self.mentioned}))


def _clauses(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    pos = 0
    for match in _CLAUSE_BREAK.finditer(text):
        if match.start() > pos:
            spans.append((pos, match.start(), text[pos : match.start()]))
        pos = match.end()
    if pos < len(text):
        spans.append((pos, len(text), text[pos:]))
    return spans


def _clause_at(clauses: Sequence[tuple[int, int, str]], offset: int) -> str:
    for start, end, text in clauses:
        if start <= offset < end:
            return text
    return ""


def _clause_kind(clause: str) -> str:
    """performed / hypothetical / negated reading of a clause's first-person acts."""
    if _CONDITIONAL_LEAD.match(clause) or _IRREALIS.search(clause):
        return "hypothetical"
    if _NEGATED.search(clause):
        return "negated"
    return "performed"


def _matches(text: str) -> list[tuple[str, re.Match[str]]]:
    found: list[tuple[str, re.Match[str]]] = []
    taken: list[tuple[int, int]] = []
    for action, pattern in _PERFORMATIVE_PATTERNS:
        for match in pattern.finditer(text):
            if any(match.start() < end and match.end() > start for start, end in taken):
                continue
            taken.append((match.start(), match.end()))
            found.append((action, match))
    found.sort(key=lambda item: item[1].start())
    return found


def analyse_prose(content: str, strip_quotes: bool = True) -> ProseAnalysis:
    """Classify every act in ``content`` as performed or merely mentioned.

    With ``strip_quotes`` (the default) quoted spans and blockquote lines are removed
    first and any performative inside them is reported as a ``quoted`` mention. With
    ``strip_quotes=False`` quoted text is read as the speaker's own words, which is
    the mutant IMP-0281 uses to show the quote filter is load-bearing.
    """
    text = content if isinstance(content, str) else ""
    stripped: list[str] = []
    analysed = text
    if strip_quotes:
        analysed, stripped = strip_quotations(text)
    clauses = _clauses(analysed)
    performed: list[Performative] = []
    mentioned: list[Performative] = []
    for span in stripped:
        for action, match in _matches(span):
            mentioned.append(Performative(action, match.group(0), -1, -1, "quoted", span))
    for action, match in _matches(analysed):
        clause = _clause_at(clauses, match.start())
        kind = _clause_kind(clause)
        item = Performative(action, match.group(0), match.start(), match.end(), kind, clause)
        (performed if kind == "performed" else mentioned).append(item)
    covered = [(p.start, p.end) for p in performed] + [
        (m.start, m.end) for m in mentioned if m.start >= 0
    ]
    for _start, _end, clause in clauses:
        kind = _clause_kind(clause)
        if kind == "performed":
            continue
        base = analysed.find(clause)
        for loose in _LOOSE_FIRST_PERSON.finditer(clause):
            start = base + loose.start()
            end = base + loose.end()
            if any(start < c_end and end > c_start for c_start, c_end in covered):
                continue
            covered.append((start, end))
            mentioned.append(
                Performative(_act_of_word(loose.group("verb")), loose.group(0), start, end, kind, clause)
            )
    performed_actions = {p.action for p in performed}
    referenced = tuple(
        sorted(
            {
                _act_of_word(m.group("word"))
                for m in _ACT_WORDS.finditer(analysed)
                if _act_of_word(m.group("word")) not in performed_actions
            }
        )
    )
    return ProseAnalysis(
        content=text,
        analysed=analysed,
        strip_quotes=bool(strip_quotes),
        stripped_spans=tuple(stripped),
        performed=tuple(performed),
        mentioned=tuple(mentioned),
        referenced=referenced,
    )


# ---------------------------------------------------------------------- guard


@dataclass
class InspectResult:
    """Verdict of one inspection pass over one turn."""

    rejected: bool
    classification: str
    source: str  # prose | structured
    attempted_action: str | None
    role: str = ""
    turn_id: str | None = None
    participant_id: str | None = None
    reason: str = ""
    evidence: str = ""
    missing_right: str | None = None
    performed: tuple[str, ...] = ()
    mentioned: tuple[str, ...] = ()
    prose_actions: tuple[str, ...] = ()
    rejection: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Turn:
    turn_id: str | None
    participant_id: str | None
    role: str
    role_raw: str
    content: str
    action: str | None
    action_raw: str | None


def _norm_turn(turn: Any) -> _Turn:
    if not isinstance(turn, Mapping):
        raise GuardError(f"a turn must be a mapping, got {type(turn).__name__}")
    turn_id = turn.get("id", turn.get("turn_id"))
    participant = turn.get("participant_id")
    content = turn.get("content")
    if content is None:
        content = ""
    elif not isinstance(content, str):
        raise GuardError(f"turn content must be a string, got {type(content).__name__}")
    action_raw = turn.get("action")
    action = normalise_action(action_raw)
    return _Turn(
        turn_id=None if turn_id is None else str(turn_id),
        participant_id=None if participant is None else str(participant),
        role=normalise_role(turn.get("role")),
        role_raw=str(turn.get("role") or ""),
        content=content,
        action=action,
        action_raw=None if action is None else str(action_raw),
    )


class RoleGuard:
    """Inspect council turns against role mandates and keep a rejection ledger.

    ``mandates`` defaults to :data:`DEFAULT_MANDATES`; pass your own mapping of role
    name to :class:`Mandate` to guard a differently constituted council. ``clock``
    is an optional zero-argument callable returning a string; when given, every
    ledger record carries ``recorded_at = clock()``.
    """

    def __init__(
        self,
        mandates: Mapping[str, Mandate] | None = None,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        table = dict(DEFAULT_MANDATES if mandates is None else mandates)
        for role, mandate in table.items():
            if type(mandate) is not Mandate:
                raise GuardError(f"mandate for role {role!r} must be a Mandate, got {type(mandate).__name__}")
        self._mandates: Mapping[str, Mandate] = MappingProxyType(
            {normalise_role(role): mandate for role, mandate in table.items()}
        )
        self._clock = clock
        self._ledger: list[dict[str, Any]] = []

    @property
    def mandates(self) -> Mapping[str, Mandate]:
        return self._mandates

    def mandate_for(self, role: str) -> Mandate | None:
        """The registered mandate for ``role`` (aliases resolved), or None."""
        return self._mandates.get(normalise_role(role))

    # -- passes -----------------------------------------------------------------

    def inspect_prose(self, turn: Mapping[str, Any], strip_quotes: bool = True) -> InspectResult:
        """Read the words only. The structured ``action`` field is ignored here."""
        t = _norm_turn(turn)
        analysis = analyse_prose(t.content, strip_quotes=strip_quotes)
        mandate = self.mandate_for(t.role)
        common = {
            "source": "prose",
            "role": t.role,
            "turn_id": t.turn_id,
            "participant_id": t.participant_id,
            "performed": analysis.actions(),
            "mentioned": tuple(dict.fromkeys(m.action for m in analysis.mentioned)),
        }
        if analysis.performed:
            breaches = [p for p in analysis.performed if mandate is None or not mandate.permits(p.action)]
            if breaches:
                hit = breaches[0]
                flag = ACTION_FLAGS[hit.action]
                if mandate is None:
                    reason = (
                        f"role {t.role_raw!r} has no registered mandate; performative "
                        f"{hit.action!r} ({hit.text!r}) refused"
                    )
                else:
                    reason = (
                        f"role {t.role!r} performed {hit.action!r} ({hit.text!r}) "
                        f"but its mandate does not grant {flag}"
                    )
                return InspectResult(
                    rejected=True,
                    classification=BREACH,
                    attempted_action=hit.action,
                    reason=reason,
                    evidence=hit.text,
                    missing_right=flag,
                    **common,
                )
            hit = analysis.performed[0]
            return InspectResult(
                rejected=False,
                classification=PERMITTED,
                attempted_action=hit.action,
                reason=f"role {t.role!r} performed {hit.action!r} ({hit.text!r}) within its mandate",
                evidence=hit.text,
                **common,
            )
        if analysis.mentioned:
            acts = ", ".join(dict.fromkeys(m.action for m in analysis.mentioned))
            kinds = ", ".join(analysis.mention_kinds())
            reason = f"use-vs-mention: {acts} appears only as {kinds} speech; nothing performed"
            evidence = analysis.mentioned[0].text
        elif analysis.referenced:
            reason = "no performative act; act words referenced: " + ", ".join(analysis.referenced)
            evidence = ""
        else:
            reason = "no performative act"
            evidence = ""
        return InspectResult(
            rejected=False,
            classification=MENTION,
            attempted_action=None,
            reason=reason,
            evidence=evidence,
            **common,
        )

    def inspect_structured(self, turn: Mapping[str, Any]) -> InspectResult:
        """Read the structured ``action`` field only. Fails closed on the unknown."""
        t = _norm_turn(turn)
        common = {
            "source": "structured",
            "role": t.role,
            "turn_id": t.turn_id,
            "participant_id": t.participant_id,
        }
        if t.action is None:
            return InspectResult(
                rejected=False,
                classification=MENTION,
                attempted_action=None,
                reason="turn carries no structured action",
                **common,
            )
        evidence = f"action={t.action_raw}"
        if t.action not in ACTION_FLAGS:
            return InspectResult(
                rejected=True,
                classification=BREACH,
                attempted_action=t.action,
                reason=f"unknown structured action {t.action_raw!r}; refused (fail closed)",
                evidence=evidence,
                **common,
            )
        flag = ACTION_FLAGS[t.action]
        mandate = self.mandate_for(t.role)
        if mandate is None:
            return InspectResult(
                rejected=True,
                classification=BREACH,
                attempted_action=t.action,
                reason=f"role {t.role_raw!r} has no registered mandate; action {t.action!r} refused",
                evidence=evidence,
                missing_right=flag,
                performed=(t.action,),
                **common,
            )
        if not mandate.permits(t.action):
            return InspectResult(
                rejected=True,
                classification=BREACH,
                attempted_action=t.action,
                reason=f"role {t.role!r} declared action {t.action!r} but its mandate does not grant {flag}",
                evidence=evidence,
                missing_right=flag,
                performed=(t.action,),
                **common,
            )
        return InspectResult(
            rejected=False,
            classification=PERMITTED,
            attempted_action=t.action,
            reason=f"role {t.role!r} declared action {t.action!r} within its mandate",
            evidence=evidence,
            performed=(t.action,),
            **common,
        )

    def inspect(self, turn: Mapping[str, Any], strip_quotes: bool = True) -> InspectResult:
        """Final verdict: the structured pass when an action is declared, else prose.

        On a structured verdict ``prose_actions`` records what the wording alone
        would have counted as performed, so audits can see when the two disagree.
        """
        t = _norm_turn(turn)
        if t.action is not None:
            result = self.inspect_structured(turn)
            result.prose_actions = analyse_prose(t.content, strip_quotes=strip_quotes).actions()
            return result
        return self.inspect_prose(turn, strip_quotes=strip_quotes)

    # -- enforcement ------------------------------------------------------------

    def enforce(self, turn: Mapping[str, Any], strip_quotes: bool = True) -> InspectResult:
        """Inspect, and when the turn is rejected append a record to the ledger.

        The record is also attached to the returned result as ``rejection``.
        """
        t = _norm_turn(turn)
        result = self.inspect(turn, strip_quotes=strip_quotes)
        if result.rejected:
            result.rejection = self._record(result, t)
        return result

    def _record(self, result: InspectResult, t: _Turn) -> dict[str, Any]:
        record: dict[str, Any] = {
            "seq": len(self._ledger) + 1,
            "turn_id": t.turn_id,
            "participant_id": t.participant_id,
            "role": t.role,
            "attempted_action": result.attempted_action,
            "source": result.source,
            "classification": result.classification,
            "missing_right": result.missing_right,
            "reason": result.reason,
            "evidence": result.evidence,
            "content_sha256": hashlib.sha256(t.content.encode("utf-8")).hexdigest(),
            "content_excerpt": t.content[:120],
        }
        if self._clock is not None:
            record["recorded_at"] = str(self._clock())
        self._ledger.append(record)
        return dict(record)

    def rejections(self) -> list[dict[str, Any]]:
        """Copies of every recorded rejection, oldest first."""
        return [dict(record) for record in self._ledger]

    def clear_rejections(self) -> int:
        """Drop the ledger; returns how many records were removed."""
        count = len(self._ledger)
        self._ledger = []
        return count


# -------------------------------------------------------------------- scoring


def precision_recall(y_true: Sequence[Any], y_pred: Sequence[Any]) -> dict[str, Any]:
    """Confusion counts plus precision and recall, reported separately (no F1).

    Both sequences are read as booleans (True = breach) and must be the same length.
    When a denominator is zero the score is 1.0: no predicted positives means no
    false alarm, no actual positives means nothing was missed.
    """
    truth = [bool(x) for x in y_true]
    pred = [bool(x) for x in y_pred]
    if len(truth) != len(pred):
        raise ValueError(f"y_true has {len(truth)} labels but y_pred has {len(pred)}")
    tp = sum(1 for t, p in zip(truth, pred) if t and p)
    fp = sum(1 for t, p in zip(truth, pred) if (not t) and p)
    fn = sum(1 for t, p in zip(truth, pred) if t and (not p))
    tn = sum(1 for t, p in zip(truth, pred) if (not t) and (not p))
    return {
        "n": len(truth),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if (tp + fp) else 1.0,
        "recall": tp / (tp + fn) if (tp + fn) else 1.0,
    }
