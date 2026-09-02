"""Six-Hats lens-rotation engine (P30 ``six-hats-rotation``, IMP-0334).

Every participant is rotated through the six thinking lenses so that each
perspective is applied by more than one participant.  :func:`compile_schedule`
builds the rotation (``parallel``: all seats wear the same hat each round;
``staggered``: seat *i* at round *r* wears hat ``(r + i) mod 6``) and refuses a
single seat - one participant cannot wear two hats at once, so no lens would
be applied by multiple participants.  :func:`audit_schedule` proves
completeness from the bindings themselves: every lens covered, every
participant wore every lens, every lens worn by at least two participants.  A
truncated schedule is reported incomplete with the lenses it misses.

The falsifiable question is whether rotation actually changes a participant's
output or whether the same participant produces lens-invariant text - role
collapse under a different name.  :class:`HatsEngine` runs a speaker through
the schedule and measures two things per run: lens *vocabulary* presence per
turn (are the assigned lens's markers in the text?) and per-participant
*divergence* - the mean pairwise Jaccard distance between one participant's
turns across the six lenses, compared with the same-round across-participant
baseline.  A participant whose across-lens distance is at or below
``ROLE_COLLAPSE_MAX_DISTANCE`` is flagged ``REASON_ROLE_COLLAPSE`` even when
every marker is present - :class:`InvariantSpeaker` with ``spam_vocabulary``
is exactly that fixture, and a vocabulary-only checker would accept it.
:class:`LensFaithfulSpeaker` is the compliant control.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "MODULE_REL",
    "PROTOCOL_ID",
    "SLUG",
    "MODE_PARALLEL",
    "MODE_STAGGERED",
    "MODES",
    "REASON_SINGLE_SEAT",
    "REASON_ROLE_COLLAPSE",
    "REASON_VOCAB_MISSING",
    "REASON_SCHEDULE_INCOMPLETE",
    "REASON_UNKNOWN_MODE",
    "REASON_DUPLICATE_SEAT",
    "ROLE_COLLAPSE_MAX_DISTANCE",
    "DEFAULT_QUESTION",
    "DEFAULT_PARTICIPANTS",
    "Hat",
    "SIX_HATS",
    "HatsError",
    "Binding",
    "Schedule",
    "Audit",
    "TurnContext",
    "TurnRecord",
    "VocabularyReport",
    "Divergence",
    "RunResult",
    "LensFaithfulSpeaker",
    "InvariantSpeaker",
    "HatsEngine",
    "compile_schedule",
    "audit_schedule",
    "tokens",
    "jaccard_distance",
    "check_vocabulary",
    "measure_divergence",
    "plugin_record",
]

MODULE_REL = "tools/council/protocol/hats.py"
PROTOCOL_ID = "P30"
SLUG = "six-hats-rotation"
MODE_PARALLEL = "parallel"
MODE_STAGGERED = "staggered"
MODES = (MODE_PARALLEL, MODE_STAGGERED)
REASON_SINGLE_SEAT = "single-seat-cannot-wear-two-hats"
REASON_ROLE_COLLAPSE = "role-collapse"
REASON_VOCAB_MISSING = "lens-vocabulary-missing"
REASON_SCHEDULE_INCOMPLETE = "schedule-incomplete"
REASON_UNKNOWN_MODE = "unknown-rotation-mode"
REASON_DUPLICATE_SEAT = "duplicate-participant"
# Mean pairwise Jaccard distance across a participant's six lens turns at or
# below this is lens-invariant output (role collapse), whatever the vocabulary.
ROLE_COLLAPSE_MAX_DISTANCE = 0.12
DEFAULT_QUESTION = "Should we ship the fallback cache this week?"
DEFAULT_PARTICIPANTS: tuple[str, ...] = ("alice", "bruno", "chloe")


class HatsError(ValueError):
    """Typed refusal; ``str(exc)`` is the reason code."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Hat:
    lens_id: str
    color: str
    question: str
    markers: tuple[str, ...] = ()
    phase_id: str = ""
    mode: str = "PROCESS"
    acts: tuple[str, ...] = ()
    sentence: str = ""


SIX_HATS: tuple[Hat, ...] = (
    Hat(
        "white", "white", "What are the facts?",
        markers=("facts", "data", "evidence"),
        phase_id="white-facts",
        sentence="Facts first: the data we actually hold, the evidence measured, and what remains unknown.",
    ),
    Hat(
        "red", "red", "What is the emotional read?",
        markers=("feel", "gut", "intuition"),
        phase_id="red-intuition",
        sentence="Gut read: how the room feels, the intuition and unease before any argument is made.",
    ),
    Hat(
        "black", "black", "What are the risks?",
        markers=("risk", "fails", "danger"),
        phase_id="black-risk",
        mode="CRITIQUE",
        acts=("black_hat",),
        sentence="Risk scan: where this fails, the danger of being wrong, the cost when the cache lies.",
    ),
    Hat(
        "yellow", "yellow", "What is the upside?",
        markers=("benefit", "upside", "value"),
        phase_id="yellow-upside",
        sentence="Upside case: the benefit delivered, the value gained, why shipping now could pay off.",
    ),
    Hat(
        "green", "green", "What alternatives exist?",
        markers=("alternative", "instead", "what if"),
        phase_id="green-alternatives",
        mode="GENERATE",
        acts=("green_hat_emit",),
        sentence="Alternatives: what if we shipped a smaller slice instead, a fresh option, a different route.",
    ),
    Hat(
        "blue", "blue", "How do we process the round?",
        markers=("process", "agenda", "next step"),
        phase_id="blue-process",
        sentence="Process check: the agenda so far, the next step, who summarises, how we close the round.",
    ),
)
_HAT_BY_ID = {hat.lens_id: hat for hat in SIX_HATS}
_WORD_RE = re.compile(r"[a-z0-9]+")


def _pid(seat: Any) -> str:
    if isinstance(seat, Mapping):
        return str(seat.get("id") or seat.get("participant_id") or seat.get("name") or "").strip()
    return str(getattr(seat, "id", seat)).strip()


# ----------------------------------------------------------------------- schedule
@dataclass(frozen=True)
class Binding:
    round_index: int
    participant_id: str
    lens_id: str
    question: str

    @property
    def hat(self) -> Hat:
        return _HAT_BY_ID[self.lens_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "participant_id": self.participant_id,
            "lens_id": self.lens_id,
            "question": self.question,
        }


@dataclass(frozen=True)
class Schedule:
    """Rotation schedule: one :class:`Binding` per (round, participant)."""

    participants: tuple[str, ...]
    mode: str
    question: str
    bindings: tuple[Binding, ...]

    @property
    def n_rounds(self) -> int:
        return len({b.round_index for b in self.bindings})

    @property
    def complete(self) -> bool:
        return audit_schedule(self).complete

    def rounds(self) -> list[list[Binding]]:
        by_round: dict[int, list[Binding]] = {}
        for b in self.bindings:
            by_round.setdefault(b.round_index, []).append(b)
        return [by_round[r] for r in sorted(by_round)]

    def restrict_rounds(self, n_rounds: int) -> "Schedule":
        """The first ``n_rounds`` rounds only (a truncated schedule)."""
        keep = tuple(b for b in self.bindings if b.round_index < int(n_rounds))
        return Schedule(self.participants, self.mode, self.question, keep)

    def lens_for(self, participant_id: str, round_index: int) -> str | None:
        for b in self.bindings:
            if b.participant_id == participant_id and b.round_index == round_index:
                return b.lens_id
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "participants": list(self.participants),
            "mode": self.mode,
            "question": self.question,
            "n_rounds": self.n_rounds,
            "rounds": [b.to_dict() for b in self.bindings],
            "complete": self.complete,
        }

    # dict-shaped access kept for the earlier ``compile_schedule`` callers
    def __getitem__(self, key: str) -> Any:
        if key == "rounds":
            return [b.to_dict() for b in self.bindings]
        if key == "complete":
            return self.complete
        if key in ("question", "mode", "participants"):
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def compile_schedule(
    participants: Sequence[Any] | None = None,
    question: str = DEFAULT_QUESTION,
    mode: str = MODE_PARALLEL,
) -> Schedule:
    """Rotate every participant through all six hats.

    Raises :class:`HatsError` ``REASON_SINGLE_SEAT`` for fewer than two seats
    (one seat cannot wear two hats, so no lens is applied by multiple
    participants), ``REASON_DUPLICATE_SEAT`` for a repeated id and
    ``REASON_UNKNOWN_MODE`` for a mode outside :data:`MODES`.
    """
    roster = tuple(_pid(seat) for seat in (participants or DEFAULT_PARTICIPANTS))
    if any(not pid for pid in roster):
        raise HatsError(REASON_DUPLICATE_SEAT, "blank participant id")
    if len(roster) < 2:
        raise HatsError(REASON_SINGLE_SEAT, f"roster={list(roster)}")
    if len(set(roster)) != len(roster):
        raise HatsError(REASON_DUPLICATE_SEAT, f"roster={list(roster)}")
    if mode not in MODES:
        raise HatsError(REASON_UNKNOWN_MODE, f"mode={mode!r}")
    n = len(SIX_HATS)
    bindings: list[Binding] = []
    for r in range(n):
        for i, pid in enumerate(roster):
            hat = SIX_HATS[r] if mode == MODE_PARALLEL else SIX_HATS[(r + i) % n]
            bindings.append(Binding(r, pid, hat.lens_id, str(question)))
    return Schedule(roster, mode, str(question), tuple(bindings))


@dataclass(frozen=True)
class Audit:
    """Completeness proof computed from a schedule's bindings."""

    complete: bool
    every_lens_covered: bool
    every_participant_wore_every_lens: bool
    each_lens_applied_by_multiple_participants: bool
    lenses_covered: tuple[str, ...]
    missing_lenses: tuple[str, ...]
    single_wearer_lenses: tuple[str, ...]
    incomplete_participants: tuple[str, ...]
    n_bindings: int
    n_lenses: int
    n_participants: int
    n_rounds: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "complete": self.complete,
            "every_lens_covered": self.every_lens_covered,
            "every_participant_wore_every_lens": self.every_participant_wore_every_lens,
            "each_lens_applied_by_multiple_participants": (
                self.each_lens_applied_by_multiple_participants
            ),
            "lenses_covered": list(self.lenses_covered),
            "missing_lenses": list(self.missing_lenses),
            "single_wearer_lenses": list(self.single_wearer_lenses),
            "incomplete_participants": list(self.incomplete_participants),
            "n_bindings": self.n_bindings,
            "n_lenses": self.n_lenses,
            "n_participants": self.n_participants,
            "n_rounds": self.n_rounds,
            "reasons": list(self.reasons),
        }

    # dict-shaped access kept for the earlier ``audit_schedule`` callers
    def __getitem__(self, key: str) -> Any:
        if key == "ok":
            return self.complete
        if key == "missing":
            return list(self.missing_lenses)
        return self.to_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


def _bindings_of(schedule: Any) -> tuple[tuple[Binding, ...], tuple[str, ...]]:
    if isinstance(schedule, Schedule):
        return schedule.bindings, schedule.participants
    rows = (schedule.get("rounds") or []) if isinstance(schedule, Mapping) else []
    bindings = tuple(
        Binding(
            int(row.get("round_index", i)),
            str(row.get("participant_id", "")),
            str(row.get("lens_id", "")),
            str(row.get("question", "")),
        )
        for i, row in enumerate(rows)
    )
    seen: list[str] = []
    for b in bindings:
        if b.participant_id not in seen:
            seen.append(b.participant_id)
    return bindings, tuple(seen)


def audit_schedule(schedule: Any) -> Audit:
    """Audit a schedule: complete only when every lens is covered, every
    participant wore every lens and every lens had at least two wearers."""
    bindings, participants = _bindings_of(schedule)
    all_lenses = [hat.lens_id for hat in SIX_HATS]
    wearers: dict[str, set[str]] = {lens: set() for lens in all_lenses}
    worn: dict[str, set[str]] = {pid: set() for pid in participants}
    for b in bindings:
        wearers.setdefault(b.lens_id, set()).add(b.participant_id)
        worn.setdefault(b.participant_id, set()).add(b.lens_id)
    covered = sorted(lens for lens in all_lenses if wearers[lens])
    missing = tuple(lens for lens in all_lenses if not wearers[lens])
    single = tuple(lens for lens in all_lenses if len(wearers[lens]) == 1)
    incomplete = tuple(pid for pid in participants if worn[pid] != set(all_lenses))
    every_lens = not missing
    every_participant = not incomplete and bool(participants)
    multiple = not single and every_lens
    reasons: list[str] = []
    if not every_lens:
        reasons.append(f"{REASON_SCHEDULE_INCOMPLETE}:missing-lenses:{','.join(missing)}")
    if incomplete:
        reasons.append(f"{REASON_SCHEDULE_INCOMPLETE}:participants:{','.join(incomplete)}")
    if single:
        reasons.append(f"{REASON_SINGLE_SEAT}:{','.join(single)}")
    return Audit(
        complete=every_lens and every_participant and multiple,
        every_lens_covered=every_lens,
        every_participant_wore_every_lens=every_participant,
        each_lens_applied_by_multiple_participants=not single and every_lens,
        lenses_covered=tuple(covered),
        missing_lenses=missing,
        single_wearer_lenses=single,
        incomplete_participants=incomplete,
        n_bindings=len(bindings),
        n_lenses=len(all_lenses),
        n_participants=len(participants),
        n_rounds=len({b.round_index for b in bindings}),
        reasons=tuple(reasons),
    )


# ------------------------------------------------------------------------ speakers
@dataclass(frozen=True)
class TurnContext:
    participant_id: str
    hat: Hat
    round_index: int
    question: str
    mode: str


class LensFaithfulSpeaker:
    """Compliant control: the turn is the assigned lens's own sentence."""

    def speak(self, ctx: TurnContext) -> str:
        return f"{ctx.participant_id} on {ctx.question!r}: {ctx.hat.sentence}"


class InvariantSpeaker:
    """Role-collapse fixture: the same text whatever hat is assigned.

    With ``spam_vocabulary`` every lens marker is pasted into every turn, so a
    vocabulary-only checker passes it while the divergence gate must not.
    """

    def __init__(self, spam_vocabulary: bool = False) -> None:
        self.spam_vocabulary = bool(spam_vocabulary)

    def speak(self, ctx: TurnContext) -> str:
        text = f"{ctx.participant_id}: my position is unchanged whatever hat is on; ship it as planned."
        if self.spam_vocabulary:
            text += " " + " ".join(marker for hat in SIX_HATS for marker in hat.markers) + "."
        return text


# ---------------------------------------------------------------------- measures
def tokens(text: str) -> frozenset[str]:
    return frozenset(_WORD_RE.findall(str(text).lower()))


def jaccard_distance(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    return 1.0 - len(sa & sb) / len(sa | sb)


@dataclass(frozen=True)
class TurnRecord:
    binding: Binding
    text: str
    turn_index: int

    @property
    def participant_id(self) -> str:
        return self.binding.participant_id

    @property
    def lens_id(self) -> str:
        return self.binding.lens_id

    def to_dict(self) -> dict[str, Any]:
        return {"turn_index": self.turn_index, **self.binding.to_dict(), "text": self.text}


@dataclass(frozen=True)
class VocabularyReport:
    per_turn: tuple[dict[str, Any], ...]
    all_present: bool
    miss_keys: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_present": self.all_present,
            "n_turns": len(self.per_turn),
            "miss_keys": list(self.miss_keys),
            "per_turn": list(self.per_turn),
        }


def check_vocabulary(records: Sequence[TurnRecord]) -> VocabularyReport:
    """Per turn: which of the assigned lens's markers appear in the text."""
    per_turn: list[dict[str, Any]] = []
    misses: list[str] = []
    for rec in records:
        low = " ".join(str(rec.text).lower().split())
        hits = [m for m in rec.binding.hat.markers if m in low]
        key = f"{rec.participant_id}:{rec.binding.round_index}:{rec.lens_id}"
        vocab_ok = bool(hits)
        per_turn.append(
            {
                "key": key,
                "participant_id": rec.participant_id,
                "round_index": rec.binding.round_index,
                "lens_id": rec.lens_id,
                "hits": hits,
                "vocab_ok": vocab_ok,
            }
        )
        if not vocab_ok:
            misses.append(key)
    return VocabularyReport(
        per_turn=tuple(per_turn), all_present=not misses and bool(records), miss_keys=tuple(misses)
    )


@dataclass(frozen=True)
class Divergence:
    """Across-lens divergence per participant vs. the same-round peer baseline."""

    per_participant_across_lens: dict[str, float]
    mean_across_lens: float
    across_participant_baseline: float
    n_across_pairs: int
    n_peer_pairs: int
    role_collapse_participants: tuple[str, ...]
    threshold: float = ROLE_COLLAPSE_MAX_DISTANCE

    @property
    def flagged(self) -> bool:
        return bool(self.role_collapse_participants)

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_participant_across_lens": dict(self.per_participant_across_lens),
            "mean_across_lens": self.mean_across_lens,
            "across_participant_baseline": self.across_participant_baseline,
            "n_across_pairs": self.n_across_pairs,
            "n_peer_pairs": self.n_peer_pairs,
            "role_collapse_participants": list(self.role_collapse_participants),
            "threshold": self.threshold,
        }


def measure_divergence(records: Sequence[TurnRecord]) -> Divergence:
    """Mean pairwise Jaccard distance of each participant's turns across lenses
    (one turn per lens) and the across-participant baseline within a round.

    A participant at or below ``ROLE_COLLAPSE_MAX_DISTANCE`` is lens-invariant."""
    by_participant: dict[str, dict[str, frozenset[str]]] = {}
    by_round: dict[int, list[frozenset[str]]] = {}
    for rec in records:
        toks = tokens(rec.text)
        by_participant.setdefault(rec.participant_id, {}).setdefault(rec.lens_id, toks)
        by_round.setdefault(rec.binding.round_index, []).append(toks)
    per: dict[str, float] = {}
    n_across = 0
    collapsed: list[str] = []
    for pid, lens_texts in by_participant.items():
        pairs = list(combinations(sorted(lens_texts), 2))
        dists = [jaccard_distance(lens_texts[a], lens_texts[b]) for a, b in pairs]
        n_across += len(pairs)
        dist = sum(dists) / len(dists) if dists else 0.0
        per[pid] = dist
        if dist <= ROLE_COLLAPSE_MAX_DISTANCE:
            collapsed.append(pid)
    peer: list[float] = []
    for round_texts in by_round.values():
        for a, b in combinations(range(len(round_texts)), 2):
            peer.append(jaccard_distance(round_texts[a], round_texts[b]))
    return Divergence(
        per_participant_across_lens=per,
        mean_across_lens=sum(per.values()) / len(per) if per else 0.0,
        across_participant_baseline=sum(peer) / len(peer) if peer else 0.0,
        n_across_pairs=n_across,
        n_peer_pairs=len(peer),
        role_collapse_participants=tuple(collapsed),
        threshold=ROLE_COLLAPSE_MAX_DISTANCE,
    )


# -------------------------------------------------------------------------- engine
@dataclass(frozen=True)
class RunResult:
    schedule: Schedule
    audit: Audit
    records: tuple[TurnRecord, ...]
    vocabulary: VocabularyReport
    divergence: Divergence
    reasons: tuple[str, ...]
    compliant: bool
    role_collapse_flagged: bool
    turns_recorded: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.schedule.mode,
            "question": self.schedule.question,
            "participants": list(self.schedule.participants),
            "n_records": len(self.records),
            "audit": self.audit.to_dict(),
            "vocabulary": {"all_present": self.vocabulary.all_present, "miss_keys": list(self.vocabulary.miss_keys)},
            "divergence": self.divergence.to_dict(),
            "reasons": list(self.reasons),
            "compliant": self.compliant,
            "role_collapse_flagged": self.role_collapse_flagged,
            "turns_recorded": self.turns_recorded,
        }


class HatsEngine:
    """Run a speaker through a six-hat rotation and judge compliance.

    Compliance needs a complete schedule, lens vocabulary on every turn and no
    role collapse; the reasons tuple names every gate that fired.  An attached
    kernel (``attach_kernel``) receives every turn as ``execute_turn``.
    """

    def __init__(self, mode: str = MODE_PARALLEL, kernel: Any | None = None) -> None:
        if mode not in MODES:
            raise HatsError(REASON_UNKNOWN_MODE, f"mode={mode!r}")
        self.mode = mode
        self.kernel = kernel

    def attach_kernel(self, kernel: Any) -> "HatsEngine":
        self.kernel = kernel
        return self

    def run(self, participants: Sequence[Any], question: str, speaker: Any) -> RunResult:
        schedule = compile_schedule(participants, question=question, mode=self.mode)
        audit = audit_schedule(schedule)
        records: list[TurnRecord] = []
        turns_recorded = 0
        for turn_index, binding in enumerate(schedule.bindings, 1):
            ctx = TurnContext(
                participant_id=binding.participant_id,
                hat=binding.hat,
                round_index=binding.round_index,
                question=schedule.question,
                mode=schedule.mode,
            )
            text = str(speaker.speak(ctx))
            if self.kernel is not None:
                self.kernel.execute_turn(
                    binding.participant_id,
                    text,
                    {"lens_id": binding.lens_id, "round_index": binding.round_index, "protocol_id": PROTOCOL_ID},
                )
                turns_recorded = int(getattr(self.kernel, "turns_recorded", turns_recorded + 1))
            records.append(TurnRecord(binding=binding, text=text, turn_index=turn_index))
        vocabulary = check_vocabulary(records)
        divergence = measure_divergence(records)
        reasons: list[str] = []
        if not audit.complete:
            reasons.append(REASON_SCHEDULE_INCOMPLETE)
        if not vocabulary.all_present:
            reasons.append(REASON_VOCAB_MISSING)
        if divergence.flagged:
            reasons.append(REASON_ROLE_COLLAPSE)
        return RunResult(
            schedule=schedule,
            audit=audit,
            records=tuple(records),
            vocabulary=vocabulary,
            divergence=divergence,
            reasons=tuple(reasons),
            compliant=not reasons,
            role_collapse_flagged=divergence.flagged,
            turns_recorded=turns_recorded,
        )


# -------------------------------------------------------------------------- plugin
def _writes_participant_output() -> bool:
    """AST scan of this module for a write-mode ``open(`` - a kernel-bypass smell."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"):
            continue
        for arg in node.args[1:]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if any(flag in arg.value for flag in ("w", "a", "x", "+")):
                    return True
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                if any(flag in str(kw.value.value) for flag in ("w", "a", "x", "+")):
                    return True
    return False


def plugin_record() -> dict[str, Any]:
    """Protocol-as-data record for the P30 plugin catalog."""
    writes = _writes_participant_output()
    return {
        "module": MODULE_REL,
        "protocol_id": PROTOCOL_ID,
        "slug": SLUG,
        "family": "GENERATIVE",
        "hats": [hat.lens_id for hat in SIX_HATS],
        "lenses": [hat.lens_id for hat in SIX_HATS],
        "phases": [
            {"phase_id": hat.phase_id, "lens_id": hat.lens_id, "mode": hat.mode, "acts": list(hat.acts)}
            for hat in SIX_HATS
        ],
        "generate_acts": [act for hat in SIX_HATS if hat.mode == "GENERATE" for act in hat.acts],
        "critique_acts": [act for hat in SIX_HATS if hat.mode == "CRITIQUE" for act in hat.acts],
        "counting_acts": [act for hat in SIX_HATS if hat.mode == "GENERATE" for act in hat.acts],
        "phase_gate": "GENERATE_CLOSED",
        "kernel_required_to_advance": True,
        "rotation": {
            MODE_PARALLEL: "all seats wear the same hat each round",
            MODE_STAGGERED: "seat i at round r wears hat (r+i) mod 6",
        },
        "role_collapse": {
            "metric": "per-participant mean pairwise Jaccard distance across lenses",
            "reason": REASON_ROLE_COLLAPSE,
            "threshold": ROLE_COLLAPSE_MAX_DISTANCE,
        },
        "writes_participant_output": writes,
        "plugin_writes_participant_output": writes,
    }
