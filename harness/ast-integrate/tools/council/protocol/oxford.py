"""Oxford debate engine (P07, ``oxford-debate``).

A motion is argued by two sides - ``proposition`` and ``opposition`` - in the
classic order: every proposition speaker opens, then every opposition speaker;
the sides then exchange rebuttals to a bounded depth; finally each side closes.
Every turn is timed against ``DebateConfig.turn_budget_ms`` and a rebuttal
deeper than ``DebateConfig.max_rebuttal_depth`` is refused with
``rebuttal_depth_exceeded`` rather than executed.

Turns are executed through a *turn loop* that keeps the kernel's
execute-and-record invariant (``turns_executed == turns_recorded``).
:class:`LocalTurnLoop` is the self-contained loop the record labels
``kernel_bound == "local"``; :class:`KernelTurnLoop` drives the same schedule
through ``tools/council/kernel.py`` (IMP-0264) when it is present and labels
the record ``"kernel"``.  :func:`bind_loop` picks the kernel when importable.

The falsifiable question the module answers is the *side-assignment effect*:
does the side a participant is assigned change its stated conclusion more than
the evidence does?  Two deterministic replications measure it on the same
motion with the same speakers:

* :func:`side_swap_experiment` swaps every speaker's side and reports the share
  of speakers whose final conclusion flipped (``flip_rate``);
* :func:`evidence_swap_experiment` keeps the sides and reverses the polarity of
  every piece of evidence instead;
* :func:`compare_side_vs_evidence` runs both and says which one moved the
  conclusions more.

Speakers are deterministic fixtures with an explicit policy: an
:class:`EvidenceBoundSpeaker` concludes whatever the motion's evidence favours
(so it never flips under a side swap and always flips under an evidence
reversal on a decisive motion); a :class:`SideBoundSpeaker` concludes for its
assigned side whatever the evidence says (rhetoric); a :class:`WeightedSpeaker`
follows its side only while its loyalty outweighs the evidence balance.  The
two stock motions are the executable arithmetic motion ``2 + 2 = 4`` (every
piece of evidence is a check the module actually computes) and a balanced
matter of taste with evidence split evenly, so ``evidence_decisive`` is a
computed property of the evidence rather than a label.
"""
from __future__ import annotations

import ast
import operator
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

__all__ = [
    "PROTOCOL_ID",
    "PROPOSITION",
    "OPPOSITION",
    "SIDES",
    "UNDECIDED",
    "OPENING",
    "REBUTTAL",
    "CLOSING",
    "TURN_KINDS",
    "LOW_FLIP_CEILING",
    "HIGH_FLIP_FLOOR",
    "DECISIVE_BALANCE",
    "REFUSE_DEPTH_EXCEEDED",
    "REFUSE_DEPTH_INVALID",
    "REFUSE_UNKNOWN_SPEAKER",
    "OxfordError",
    "Evidence",
    "Motion",
    "evaluate_arithmetic",
    "decisive_arithmetic_motion",
    "balanced_taste_motion",
    "TurnContext",
    "Utterance",
    "EvidenceBoundSpeaker",
    "SideBoundSpeaker",
    "WeightedSpeaker",
    "DebateConfig",
    "PlannedTurn",
    "Turn",
    "TimingAudit",
    "timing_audit",
    "LoopResult",
    "LocalTurnLoop",
    "KernelTurnLoop",
    "bind_loop",
    "DebateRecord",
    "RebuttalOutcome",
    "OxfordProtocol",
    "flip_rate",
    "side_swap_experiment",
    "evidence_swap_experiment",
    "compare_side_vs_evidence",
]

PROTOCOL_ID = "P07"
PROPOSITION = "proposition"
OPPOSITION = "opposition"
SIDES: tuple[str, str] = (PROPOSITION, OPPOSITION)
UNDECIDED = "undecided"
CONCLUSIONS: tuple[str, ...] = (PROPOSITION, OPPOSITION, UNDECIDED)

OPENING = "opening"
REBUTTAL = "rebuttal"
CLOSING = "closing"
TURN_KINDS: tuple[str, str, str] = (OPENING, REBUTTAL, CLOSING)

#: A side-swap flip rate at or below this means side assignment did not move
#: the cohort's conclusions; at or above :data:`HIGH_FLIP_FLOOR` it did.
LOW_FLIP_CEILING = 0.25
HIGH_FLIP_FLOOR = 0.75
#: |evidence balance| at or above this makes a motion ``evidence_decisive``.
DECISIVE_BALANCE = 0.8
DEFAULT_ELAPSED_MS = 50

REFUSE_DEPTH_EXCEEDED = "rebuttal_depth_exceeded"
REFUSE_DEPTH_INVALID = "rebuttal_depth_invalid"
REFUSE_UNKNOWN_SPEAKER = "unknown_speaker"


class OxfordError(ValueError):
    """A motion, speaker, assignment or configuration violates the protocol."""


def _other_side(side: str) -> str:
    return OPPOSITION if side == PROPOSITION else PROPOSITION


# --------------------------------------------------------------------------- motions


@dataclass(frozen=True)
class Evidence:
    """One piece of evidence bearing on the motion.

    ``supports`` names the side the evidence favours, ``weight`` in (0, 1] its
    strength, ``checkable`` whether the module computed the claim itself.
    """

    id: str
    claim: str
    supports: str
    weight: float = 1.0
    checkable: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise OxfordError("evidence needs an id")
        if self.supports not in SIDES:
            raise OxfordError(f"evidence {self.id!r} supports {self.supports!r}; must be one of {SIDES}")
        if not 0.0 < float(self.weight) <= 1.0:
            raise OxfordError(f"evidence {self.id!r} weight must lie in (0, 1], got {self.weight}")

    @property
    def signed_weight(self) -> float:
        """Positive toward the proposition, negative toward the opposition."""
        return float(self.weight) if self.supports == PROPOSITION else -float(self.weight)

    def reversed(self) -> "Evidence":
        """The same evidence read as supporting the other side."""
        return Evidence(self.id, self.claim, _other_side(self.supports), self.weight, self.checkable)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "claim": self.claim,
            "supports": self.supports,
            "weight": float(self.weight),
            "checkable": self.checkable,
        }


@dataclass(frozen=True)
class Motion:
    """The proposition under debate plus the evidence bearing on it."""

    id: str
    text: str
    evidence: tuple[Evidence, ...]
    domain: str = "general"
    polarity: str = "as-stated"

    def __post_init__(self) -> None:
        if not self.id or not self.text:
            raise OxfordError("a motion needs an id and a text")
        ids = [e.id for e in self.evidence]
        if len(set(ids)) != len(ids):
            raise OxfordError(f"motion {self.id!r} has duplicate evidence ids {ids}")

    @property
    def balance(self) -> float:
        """Weighted evidence balance in [-1, 1]; positive favours the proposition."""
        total = sum(float(e.weight) for e in self.evidence)
        if total == 0.0:
            return 0.0
        return sum(e.signed_weight for e in self.evidence) / total

    @property
    def favoured_side(self) -> str:
        """Side the evidence favours, or ``UNDECIDED`` when it is balanced."""
        balance = self.balance
        if balance > 0.0:
            return PROPOSITION
        if balance < 0.0:
            return OPPOSITION
        return UNDECIDED

    @property
    def evidence_decisive(self) -> bool:
        """True when |balance| >= :data:`DECISIVE_BALANCE`."""
        return abs(self.balance) >= DECISIVE_BALANCE

    def with_reversed_evidence(self) -> "Motion":
        """Same motion, every piece of evidence read for the other side."""
        polarity = "reversed" if self.polarity == "as-stated" else "as-stated"
        return Motion(
            self.id,
            self.text,
            tuple(e.reversed() for e in self.evidence),
            self.domain,
            polarity,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "domain": self.domain,
            "polarity": self.polarity,
            "evidence": [e.as_dict() for e in self.evidence],
            "balance": self.balance,
            "favoured_side": self.favoured_side,
            "evidence_decisive": self.evidence_decisive,
        }


_BINARY_OPERATORS: dict[type, Callable[[int, int], int]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}


def evaluate_arithmetic(expression: str) -> int:
    """Evaluate an integer expression over ``+ - * // %`` and unary minus.

    Anything else (names, calls, floats, attribute access) is refused, so the
    evaluator can only ever compute arithmetic.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise OxfordError(f"not an arithmetic expression: {expression!r}") from exc

    def walk(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -walk(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
            left, right = walk(node.left), walk(node.right)
            if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and right == 0:
                raise OxfordError(f"division by zero in {expression!r}")
            return _BINARY_OPERATORS[type(node.op)](left, right)
        raise OxfordError(f"unsupported construct {type(node).__name__} in {expression!r}")

    return walk(tree)


def _checked(evidence_id: str, claim: str, holds: bool, weight: float = 1.0) -> Evidence:
    """Evidence whose side is the outcome of a check the module just ran."""
    return Evidence(evidence_id, claim, PROPOSITION if holds else OPPOSITION, weight, checkable=True)


def decisive_arithmetic_motion() -> Motion:
    """``2 + 2 = 4``: every piece of evidence is a computation, so the motion is decisive."""
    expression, asserted = "2 + 2", 4
    computed = evaluate_arithmetic(expression)
    union = list(range(2)) + list(range(2))
    return Motion(
        id="arith-2plus2",
        text=f"{expression} = {asserted}",
        domain="arithmetic",
        evidence=(
            _checked(
                "eval-integer-arithmetic",
                f"evaluating {expression!r} over the integers yields {computed}",
                computed == asserted,
            ),
            _checked(
                "cardinality-disjoint-union",
                f"a disjoint union of two 2-element sets has {len(union)} elements",
                len(union) == asserted,
            ),
            _checked(
                "binary-positional",
                f"in base 2, 10 + 10 = {bin(computed)[2:]} which reads back as {int(bin(computed), 2)}",
                int(bin(computed), 2) == asserted,
            ),
        ),
    )


def balanced_taste_motion() -> Motion:
    """``Pineapple belongs on pizza``: taste, with the evidence split exactly evenly."""
    return Motion(
        id="taste-pineapple-pizza",
        text="Pineapple belongs on pizza",
        domain="taste",
        evidence=(
            Evidence(
                "survey-for",
                "some surveys report a plurality enjoying sweet-and-savoury toppings",
                PROPOSITION,
                0.5,
            ),
            Evidence(
                "survey-against",
                "other surveys report a plurality rejecting fruit on pizza",
                OPPOSITION,
                0.5,
            ),
        ),
    )


# --------------------------------------------------------------------------- speakers


@dataclass(frozen=True)
class TurnContext:
    """What a speaker sees when asked to speak."""

    motion: Motion
    side: str
    kind: str
    depth: int
    turn_index: int
    transcript: tuple["Utterance", ...] = ()

    def last_from(self, side: str) -> "Utterance | None":
        for utterance in reversed(self.transcript):
            if utterance.side == side:
                return utterance
        return None


@dataclass(frozen=True)
class Utterance:
    """What a speaker said in one turn and how long it took."""

    speaker: str
    side: str
    kind: str
    depth: int
    conclusion: str
    text: str
    elapsed_ms: int

    def __post_init__(self) -> None:
        if self.conclusion not in CONCLUSIONS:
            raise OxfordError(f"{self.speaker}: conclusion {self.conclusion!r} not in {CONCLUSIONS}")
        if int(self.elapsed_ms) < 0:
            raise OxfordError(f"{self.speaker}: elapsed_ms must be >= 0")

    def as_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "side": self.side,
            "kind": self.kind,
            "depth": self.depth,
            "conclusion": self.conclusion,
            "text": self.text,
            "elapsed_ms": int(self.elapsed_ms),
        }


class _Speaker:
    """Deterministic speaker fixture; subclasses define ``conclude``."""

    policy = "abstract"

    def __init__(self, name: str, elapsed_ms: int = DEFAULT_ELAPSED_MS) -> None:
        if not isinstance(name, str) or not name.strip():
            raise OxfordError("speaker name must be a non-empty string")
        if int(elapsed_ms) < 0:
            raise OxfordError(f"{name}: elapsed_ms must be >= 0")
        self.name = name
        self.elapsed_ms = int(elapsed_ms)

    def conclude(self, ctx: TurnContext) -> str:
        raise NotImplementedError

    def phrase(self, ctx: TurnContext, conclusion: str) -> str:
        stance = {
            PROPOSITION: "the motion stands",
            OPPOSITION: "the motion falls",
            UNDECIDED: "the evidence does not settle the motion",
        }[conclusion]
        reply = ""
        if ctx.kind == REBUTTAL:
            peer = ctx.last_from(_other_side(ctx.side))
            if peer is not None:
                reply = f", answering {peer.speaker}'s {peer.kind}"
        return f"{self.name} ({ctx.side}, {ctx.kind}{reply}): {stance} - {ctx.motion.text!r}"

    def speak(self, ctx: TurnContext) -> Utterance:
        conclusion = self.conclude(ctx)
        return Utterance(
            speaker=self.name,
            side=ctx.side,
            kind=ctx.kind,
            depth=ctx.depth,
            conclusion=conclusion,
            text=self.phrase(ctx, conclusion),
            elapsed_ms=self.elapsed_ms,
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.name!r}, elapsed_ms={self.elapsed_ms})"


class EvidenceBoundSpeaker(_Speaker):
    """Concludes whatever the motion's evidence favours, regardless of side."""

    policy = "evidence-bound"

    def conclude(self, ctx: TurnContext) -> str:
        return ctx.motion.favoured_side

    def phrase(self, ctx: TurnContext, conclusion: str) -> str:
        cited = [e.id for e in ctx.motion.evidence if e.supports == conclusion]
        return super().phrase(ctx, conclusion) + f" [evidence: {', '.join(cited) or 'balanced'}]"


class SideBoundSpeaker(_Speaker):
    """Concludes for its assigned side whatever the evidence says (pure rhetoric)."""

    policy = "side-bound"

    def conclude(self, ctx: TurnContext) -> str:
        return ctx.side


class WeightedSpeaker(_Speaker):
    """Follows its side while ``loyalty`` outweighs the evidence balance, else the evidence."""

    policy = "weighted"

    def __init__(self, name: str, loyalty: float = 0.6, elapsed_ms: int = DEFAULT_ELAPSED_MS) -> None:
        super().__init__(name, elapsed_ms)
        if not 0.0 <= float(loyalty) <= 1.0:
            raise OxfordError(f"{name}: loyalty must lie in [0, 1], got {loyalty}")
        self.loyalty = float(loyalty)

    def conclude(self, ctx: TurnContext) -> str:
        if self.loyalty >= abs(ctx.motion.balance):
            return ctx.side
        return ctx.motion.favoured_side


# --------------------------------------------------------------------------- turns / loops


@dataclass(frozen=True)
class DebateConfig:
    """Per-turn time budget and the rebuttal depth bound."""

    turn_budget_ms: int = 1000
    max_rebuttal_depth: int = 2
    council_id: str = "oxford-debate"

    def __post_init__(self) -> None:
        if int(self.turn_budget_ms) <= 0:
            raise OxfordError(f"turn_budget_ms must be > 0, got {self.turn_budget_ms}")
        if int(self.max_rebuttal_depth) < 0:
            raise OxfordError(f"max_rebuttal_depth must be >= 0, got {self.max_rebuttal_depth}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn_budget_ms": int(self.turn_budget_ms),
            "max_rebuttal_depth": int(self.max_rebuttal_depth),
            "council_id": self.council_id,
        }


@dataclass(frozen=True)
class PlannedTurn:
    """One slot of the debate schedule before it is spoken."""

    index: int
    speaker: str
    side: str
    kind: str
    depth: int


@dataclass(frozen=True)
class Turn:
    """An executed and recorded turn."""

    index: int
    speaker: str
    side: str
    kind: str
    depth: int
    conclusion: str
    text: str
    elapsed_ms: int
    budget_ms: int
    timed_out: bool
    status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "speaker": self.speaker,
            "side": self.side,
            "kind": self.kind,
            "depth": self.depth,
            "conclusion": self.conclusion,
            "text": self.text,
            "elapsed_ms": self.elapsed_ms,
            "budget_ms": self.budget_ms,
            "timed_out": self.timed_out,
            "status": self.status,
        }


def _turn_from(planned: PlannedTurn, utterance: Utterance, budget_ms: int, status: str | None = None) -> Turn:
    if utterance.speaker != planned.speaker:
        raise OxfordError(f"turn {planned.index}: {utterance.speaker!r} spoke in {planned.speaker!r}'s slot")
    timed_out = int(utterance.elapsed_ms) > int(budget_ms)
    return Turn(
        index=planned.index,
        speaker=planned.speaker,
        side=planned.side,
        kind=planned.kind,
        depth=planned.depth,
        conclusion=utterance.conclusion,
        text=utterance.text,
        elapsed_ms=int(utterance.elapsed_ms),
        budget_ms=int(budget_ms),
        timed_out=timed_out,
        status=status or ("timeout" if timed_out else "ok"),
    )


@dataclass(frozen=True)
class TimingAudit:
    """Turn timing against the budget: which turns overran and by how much."""

    budget_ms: int
    turn_count: int
    overrun_count: int
    overrun_turns: tuple[int, ...]
    total_elapsed_ms: int
    max_elapsed_ms: int

    @property
    def in_budget(self) -> bool:
        return self.overrun_count == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "budget_ms": self.budget_ms,
            "turn_count": self.turn_count,
            "overrun_count": self.overrun_count,
            "overrun_turns": list(self.overrun_turns),
            "total_elapsed_ms": self.total_elapsed_ms,
            "max_elapsed_ms": self.max_elapsed_ms,
            "in_budget": self.in_budget,
        }


def timing_audit(turns: Iterable[Turn], budget_ms: int) -> TimingAudit:
    """Flag every turn whose ``elapsed_ms`` exceeds ``budget_ms``; silent when none does."""
    rows = list(turns)
    overruns = tuple(t.index for t in rows if t.elapsed_ms > int(budget_ms))
    return TimingAudit(
        budget_ms=int(budget_ms),
        turn_count=len(rows),
        overrun_count=len(overruns),
        overrun_turns=overruns,
        total_elapsed_ms=sum(t.elapsed_ms for t in rows),
        max_elapsed_ms=max((t.elapsed_ms for t in rows), default=0),
    )


@dataclass(frozen=True)
class LoopResult:
    """What a turn loop returns for one schedule: the turns and the invariant counters."""

    loop: str
    turns: tuple[Turn, ...]
    turns_executed: int
    turns_recorded: int

    @property
    def invariant_ok(self) -> bool:
        return self.turns_executed == self.turns_recorded == len(self.turns)


SpeakFn = Callable[[PlannedTurn], Utterance]


class LocalTurnLoop:
    """Self-contained execute-and-record loop: every executed turn is recorded once."""

    name = "local"

    def __init__(self) -> None:
        self.turns_executed = 0
        self.turns_recorded = 0
        self.log: list[Turn] = []

    def _record(self, turn: Turn) -> Turn:
        self.turns_recorded += 1
        self.log.append(turn)
        return turn

    def run_schedule(self, schedule: Iterable[PlannedTurn], speak: SpeakFn, budget_ms: int) -> LoopResult:
        executed_before, recorded_before = self.turns_executed, self.turns_recorded
        turns: list[Turn] = []
        for planned in schedule:
            self.turns_executed += 1
            utterance = speak(planned)
            turns.append(self._record(_turn_from(planned, utterance, budget_ms)))
        return LoopResult(
            self.name,
            tuple(turns),
            self.turns_executed - executed_before,
            self.turns_recorded - recorded_before,
        )

    @property
    def invariant_ok(self) -> bool:
        return self.turns_executed == self.turns_recorded == len(self.log)


class KernelTurnLoop:
    """Drive the schedule through ``tools/council/kernel.py`` (IMP-0264).

    Each planned turn becomes a kernel ``TurnSpec`` for its speaker; a stateful
    adapter per speaker pops that speaker's next slot, asks the speaker to speak
    and hands the kernel a ``TurnResponse`` carrying the conclusion as the turn's
    obligation field.  Counters come from the kernel itself.
    """

    name = "kernel"

    def __init__(self, council_id: str = "oxford-debate") -> None:
        try:
            from ..kernel import ExecutionPlan, Kernel, TurnResponse  # noqa: WPS433
        except ImportError as exc:  # pragma: no cover - depends on the tree
            raise OxfordError(f"council kernel not importable: {exc}") from exc
        self._plan_type = ExecutionPlan
        self._response_type = TurnResponse
        self.kernel = Kernel(council_id)

    @property
    def turns_executed(self) -> int:
        return int(self.kernel.turns_executed)

    @property
    def turns_recorded(self) -> int:
        return int(self.kernel.turns_recorded)

    def run_schedule(self, schedule: Iterable[PlannedTurn], speak: SpeakFn, budget_ms: int) -> LoopResult:
        planned_turns = list(schedule)
        if not planned_turns:
            return LoopResult(self.name, (), 0, 0)
        queues: dict[str, deque[PlannedTurn]] = {}
        for planned in planned_turns:
            queues.setdefault(planned.speaker, deque()).append(planned)
        spoken: list[tuple[PlannedTurn, Utterance]] = []
        response_type = self._response_type

        class _Adapter:
            def __init__(self, speaker: str) -> None:
                self.speaker = speaker

            def run(self, spec: Any) -> Any:
                planned = queues[self.speaker].popleft()
                utterance = speak(planned)
                spoken.append((planned, utterance))
                return response_type(
                    text=utterance.text,
                    fields={"conclusion": utterance.conclusion},
                    elapsed_ms=int(utterance.elapsed_ms),
                    timed_out=int(utterance.elapsed_ms) > int(budget_ms),
                )

        class _Topology:
            def order(self, plan: Any) -> list[str]:
                return [p.speaker for p in planned_turns]

        plan = self._plan_type(
            council_id=self.kernel.council_id,
            roster=tuple(dict.fromkeys(p.speaker for p in planned_turns)),
            n_rounds=1,
            timeout_ms=int(budget_ms),
            obligations=("conclusion",),
        )
        executed_before, recorded_before = self.turns_executed, self.turns_recorded
        result = self.kernel.run(plan, _Topology(), {name: _Adapter(name) for name in plan.roster})
        turns = tuple(
            _turn_from(planned, utterance, budget_ms, status=event.status)
            for (planned, utterance), event in zip(spoken, result.events)
        )
        return LoopResult(
            self.name,
            turns,
            self.turns_executed - executed_before,
            self.turns_recorded - recorded_before,
        )


def bind_loop(prefer: str = "kernel", council_id: str = "oxford-debate") -> LocalTurnLoop | KernelTurnLoop:
    """The kernel-backed loop when ``prefer == "kernel"`` and the kernel imports, else local."""
    if prefer == "kernel":
        try:
            return KernelTurnLoop(council_id)
        except OxfordError:
            return LocalTurnLoop()
    if prefer == "local":
        return LocalTurnLoop()
    raise OxfordError(f"unknown loop preference {prefer!r}; use 'kernel' or 'local'")


# --------------------------------------------------------------------------- records


@dataclass
class DebateRecord:
    """Everything one debate produced: turns, counters, timing and the loop that ran it."""

    motion: Motion
    config: DebateConfig
    assignments: dict[str, str]
    turns: list[Turn]
    turns_executed: int
    turns_recorded: int
    kernel_bound: str
    closed: bool
    timing: TimingAudit | None = None
    loop_invariant_ok: bool = True

    def __post_init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.timing = timing_audit(self.turns, self.config.turn_budget_ms)
        self.loop_invariant_ok = self.turns_executed == self.turns_recorded == len(self.turns)

    @property
    def rebuttal_depth_reached(self) -> int:
        return max((t.depth for t in self.turns if t.kind == REBUTTAL), default=0)

    def sides_spoken(self) -> set[str]:
        return {t.side for t in self.turns}

    def conclusions(self) -> dict[str, str]:
        """Each speaker's final stated conclusion (its last turn, i.e. the closing when present)."""
        final: dict[str, str] = {}
        for turn in self.turns:
            final[turn.speaker] = turn.conclusion
        return final

    def tally(self) -> dict[str, int]:
        counts = {PROPOSITION: 0, OPPOSITION: 0, UNDECIDED: 0}
        for conclusion in self.conclusions().values():
            counts[conclusion] += 1
        return counts

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": PROTOCOL_ID,
            "motion": self.motion.as_dict(),
            "config": self.config.as_dict(),
            "assignments": dict(self.assignments),
            "kernel_bound": self.kernel_bound,
            "closed": self.closed,
            "turns_executed": self.turns_executed,
            "turns_recorded": self.turns_recorded,
            "loop_invariant_ok": self.loop_invariant_ok,
            "rebuttal_depth_reached": self.rebuttal_depth_reached,
            "turns": [t.as_dict() for t in self.turns],
            "conclusions": self.conclusions(),
            "tally": self.tally(),
            "timing": None if self.timing is None else self.timing.as_dict(),
        }


@dataclass(frozen=True)
class RebuttalOutcome:
    """Result of asking for one more rebuttal: refused with a reason, or the turn."""

    speaker: str
    depth: int
    refused: bool
    refuse_reason: str | None = None
    turn: Turn | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "speaker": self.speaker,
            "depth": self.depth,
            "refused": self.refused,
            "refuse_reason": self.refuse_reason,
            "turn": None if self.turn is None else self.turn.as_dict(),
        }


# --------------------------------------------------------------------------- protocol


class OxfordProtocol:
    """Run a motion with proposition and opposition sides, timed turns and bounded rebuttals."""

    def __init__(
        self,
        config: DebateConfig | None = None,
        loop: LocalTurnLoop | KernelTurnLoop | None = None,
    ) -> None:
        self.config = config or DebateConfig()
        self.loop = loop or LocalTurnLoop()
        if not hasattr(self.loop, "run_schedule"):
            raise OxfordError(f"loop {self.loop!r} does not implement run_schedule")

    # ---- validation ------------------------------------------------------------

    @staticmethod
    def _validate_cast(speakers: Mapping[str, Any], assignments: Mapping[str, str]) -> dict[str, str]:
        if not assignments:
            raise OxfordError("assignments are empty")
        cast: dict[str, str] = {}
        for name, side in assignments.items():
            if name not in speakers:
                raise OxfordError(f"{name!r} is assigned a side but is not among the speakers")
            if not hasattr(speakers[name], "speak"):
                raise OxfordError(f"speaker {name!r} has no speak()")
            if side not in SIDES:
                raise OxfordError(f"{name!r} assigned unknown side {side!r}; sides are {SIDES}")
            cast[str(name)] = side
        missing = [side for side in SIDES if side not in cast.values()]
        if missing:
            raise OxfordError(f"no speaker assigned to {missing}; both sides must be seated")
        unassigned = sorted(set(speakers) - set(cast))
        if unassigned:
            raise OxfordError(f"speakers without a side: {unassigned}")
        return cast

    def schedule(self, assignments: Mapping[str, str]) -> list[PlannedTurn]:
        """Opening (prop then opp), rebuttal rounds 1..max_depth (prop then opp), closing."""
        by_side = {side: [n for n, s in assignments.items() if s == side] for side in SIDES}
        rounds: list[tuple[str, int]] = [(OPENING, 0)]
        rounds.extend((REBUTTAL, depth) for depth in range(1, int(self.config.max_rebuttal_depth) + 1))
        rounds.append((CLOSING, 0))
        planned: list[PlannedTurn] = []
        for kind, depth in rounds:
            for side in SIDES:
                for name in by_side[side]:
                    planned.append(PlannedTurn(len(planned), name, side, kind, depth))
        return planned

    # ---- execution --------------------------------------------------------------

    def _speaker_fn(
        self,
        motion: Motion,
        speakers: Mapping[str, Any],
        transcript: list[Utterance],
    ) -> SpeakFn:
        def speak(planned: PlannedTurn) -> Utterance:
            ctx = TurnContext(
                motion=motion,
                side=planned.side,
                kind=planned.kind,
                depth=planned.depth,
                turn_index=planned.index,
                transcript=tuple(transcript),
            )
            utterance = speakers[planned.speaker].speak(ctx)
            if not isinstance(utterance, Utterance):
                raise OxfordError(f"{planned.speaker!r}.speak() must return an Utterance")
            transcript.append(utterance)
            return utterance

        return speak

    def run(
        self,
        motion: Motion,
        speakers: Mapping[str, Any],
        assignments: Mapping[str, str],
    ) -> DebateRecord:
        """Execute the full schedule through the loop and return the record."""
        if not isinstance(motion, Motion):
            raise OxfordError("run() needs a Motion")
        cast = self._validate_cast(speakers, assignments)
        transcript: list[Utterance] = []
        result = self.loop.run_schedule(
            self.schedule(cast),
            self._speaker_fn(motion, speakers, transcript),
            self.config.turn_budget_ms,
        )
        return DebateRecord(
            motion=motion,
            config=self.config,
            assignments=cast,
            turns=list(result.turns),
            turns_executed=result.turns_executed,
            turns_recorded=result.turns_recorded,
            kernel_bound=result.loop,
            closed=any(t.kind == CLOSING for t in result.turns),
        )

    def submit_rebuttal(
        self,
        record: DebateRecord,
        speakers: Mapping[str, Any],
        speaker: str,
        depth: int,
    ) -> RebuttalOutcome:
        """One more rebuttal at ``depth``; refused beyond the bound, never executed when refused."""
        try:
            depth_int = int(depth)
        except (TypeError, ValueError):
            return RebuttalOutcome(speaker, -1, True, REFUSE_DEPTH_INVALID)
        if depth_int > int(self.config.max_rebuttal_depth):
            return RebuttalOutcome(speaker, depth_int, True, REFUSE_DEPTH_EXCEEDED)
        if depth_int < 1:
            return RebuttalOutcome(speaker, depth_int, True, REFUSE_DEPTH_INVALID)
        if speaker not in record.assignments or speaker not in speakers:
            return RebuttalOutcome(speaker, depth_int, True, REFUSE_UNKNOWN_SPEAKER)
        if record.closed:
            return RebuttalOutcome(speaker, depth_int, True, "debate_closed")
        transcript = [
            Utterance(t.speaker, t.side, t.kind, t.depth, t.conclusion, t.text, t.elapsed_ms)
            for t in record.turns
        ]
        planned = PlannedTurn(len(record.turns), speaker, record.assignments[speaker], REBUTTAL, depth_int)
        result = self.loop.run_schedule(
            [planned],
            self._speaker_fn(record.motion, speakers, transcript),
            self.config.turn_budget_ms,
        )
        turn = result.turns[0]
        record.turns.append(turn)
        record.turns_executed += result.turns_executed
        record.turns_recorded += result.turns_recorded
        record.refresh()
        return RebuttalOutcome(speaker, depth_int, False, None, turn)

    def close(self, record: DebateRecord, speakers: Mapping[str, Any]) -> DebateRecord:
        """Deliver the closing statements of an open record (prop then opp)."""
        if record.closed:
            raise OxfordError("debate already closed")
        start = len(record.turns)
        planned = [
            PlannedTurn(start + i, name, side, CLOSING, 0)
            for i, (name, side) in enumerate(
                (n, s) for wanted in SIDES for n, s in record.assignments.items() if s == wanted
            )
        ]
        transcript = [
            Utterance(t.speaker, t.side, t.kind, t.depth, t.conclusion, t.text, t.elapsed_ms)
            for t in record.turns
        ]
        result = self.loop.run_schedule(
            planned, self._speaker_fn(record.motion, speakers, transcript), self.config.turn_budget_ms
        )
        record.turns.extend(result.turns)
        record.turns_executed += result.turns_executed
        record.turns_recorded += result.turns_recorded
        record.closed = True
        record.refresh()
        return record


# --------------------------------------------------------------------------- experiments


def flip_rate(base: Mapping[str, str], other: Mapping[str, str]) -> tuple[int, float]:
    """(flips, rate): how many speakers changed conclusion between two runs."""
    names = sorted(base)
    if not names:
        raise OxfordError("no speakers to compare")
    if sorted(other) != names:
        raise OxfordError(f"speaker sets differ: {names} vs {sorted(other)}")
    flips = sum(1 for name in names if base[name] != other[name])
    return flips, flips / len(names)


def _per_speaker(base: Mapping[str, str], other: Mapping[str, str], other_label: str) -> dict[str, dict]:
    return {
        name: {"base": base[name], other_label: other[name], "flipped": base[name] != other[name]}
        for name in sorted(base)
    }


def _fresh_loop(protocol: OxfordProtocol) -> OxfordProtocol:
    """A protocol with the same config and an equivalent, fresh loop."""
    if isinstance(protocol.loop, KernelTurnLoop):
        return OxfordProtocol(protocol.config, KernelTurnLoop(protocol.config.council_id))
    return OxfordProtocol(protocol.config, type(protocol.loop)())


def side_swap_experiment(
    motion: Motion,
    speakers: Mapping[str, Any],
    assignments: Mapping[str, str],
    config: DebateConfig | None = None,
    loop: LocalTurnLoop | KernelTurnLoop | None = None,
) -> dict[str, Any]:
    """Run the motion, swap every speaker's side, run again; report the conclusion flip rate."""
    protocol = OxfordProtocol(config, loop)
    base = protocol.run(motion, speakers, assignments)
    swapped_sides = {name: _other_side(side) for name, side in base.assignments.items()}
    swapped = _fresh_loop(protocol).run(motion, speakers, swapped_sides)
    flips, rate = flip_rate(base.conclusions(), swapped.conclusions())
    return {
        "experiment": "side_swap",
        "motion_id": motion.id,
        "evidence_decisive": motion.evidence_decisive,
        "evidence_balance": motion.balance,
        "n": len(base.assignments),
        "flips": flips,
        "flip_rate": rate,
        "low_flip": rate <= LOW_FLIP_CEILING,
        "high_flip": rate >= HIGH_FLIP_FLOOR,
        "assignments": dict(base.assignments),
        "swapped_assignments": swapped_sides,
        "per_speaker": _per_speaker(base.conclusions(), swapped.conclusions(), "swapped"),
        "base": base.as_dict(),
        "swapped": swapped.as_dict(),
        "timing_base": base.timing.as_dict() if base.timing else None,
        "timing_swapped": swapped.timing.as_dict() if swapped.timing else None,
    }


def evidence_swap_experiment(
    motion: Motion,
    speakers: Mapping[str, Any],
    assignments: Mapping[str, str],
    config: DebateConfig | None = None,
    loop: LocalTurnLoop | KernelTurnLoop | None = None,
) -> dict[str, Any]:
    """Run the motion, reverse every piece of evidence, run again with the same sides."""
    protocol = OxfordProtocol(config, loop)
    base = protocol.run(motion, speakers, assignments)
    reversed_motion = motion.with_reversed_evidence()
    reversed_run = _fresh_loop(protocol).run(reversed_motion, speakers, assignments)
    flips, rate = flip_rate(base.conclusions(), reversed_run.conclusions())
    return {
        "experiment": "evidence_swap",
        "motion_id": motion.id,
        "evidence_decisive": motion.evidence_decisive,
        "evidence_balance": motion.balance,
        "reversed_balance": reversed_motion.balance,
        "n": len(base.assignments),
        "flips": flips,
        "flip_rate": rate,
        "assignments": dict(base.assignments),
        "per_speaker": _per_speaker(base.conclusions(), reversed_run.conclusions(), "reversed"),
        "base": base.as_dict(),
        "reversed": reversed_run.as_dict(),
    }


def compare_side_vs_evidence(
    motion: Motion,
    speakers: Mapping[str, Any],
    assignments: Mapping[str, str],
    config: DebateConfig | None = None,
    loop: LocalTurnLoop | KernelTurnLoop | None = None,
) -> dict[str, Any]:
    """Does side assignment move conclusions more than the evidence does?"""
    side = side_swap_experiment(motion, speakers, assignments, config, loop)
    evidence = evidence_swap_experiment(motion, speakers, assignments, config, loop)
    side_rate, evidence_rate = float(side["flip_rate"]), float(evidence["flip_rate"])
    side_exceeds = side_rate > evidence_rate
    return {
        "motion_id": motion.id,
        "evidence_decisive": motion.evidence_decisive,
        "side_assignment_flip_rate": side_rate,
        "evidence_flip_rate": evidence_rate,
        "side_minus_evidence": side_rate - evidence_rate,
        "side_exceeds_evidence": side_exceeds,
        "interpretation": (
            "side assignment changes conclusions more than evidence"
            if side_exceeds
            else "evidence changes conclusions as much as or more than side assignment"
        ),
        "side_swap": side,
        "evidence_swap": evidence,
    }
