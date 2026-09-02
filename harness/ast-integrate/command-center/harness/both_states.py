"""Both-states control harness (TST-0013; consumed by TST-0031 and later units).

A detector is only evidence when it is SILENT on a known-good state and FIRES
on a known-broken state. A check that is silent in both states measures
nothing; a check that fires in both states is a false-positive machine; a
check that fires on good and stays silent on broken has inverted polarity.
``control`` runs one check against both states and emits a typed
``ControlRecord`` whose verdict is ``VALID`` or ``REJECTED`` with a reason.

Consumption::

    sys.path.insert(0, "command-center/harness")
    from both_states import control
    rec = control(check, good_state, broken_state, check_id="test_x")
    assert rec.verdict == "VALID"

A check may signal a finding in either of two styles:

* **boolean/collection style** -- return a truthy value to FIRE, a falsy
  value (``False``, ``None``, ``[]``) to stay SILENT;
* **assert style** -- raise ``AssertionError`` (or any exception class named
  in ``fires_on``) to FIRE, return normally to stay SILENT.

Any other exception propagates: a crashing check is not a detection.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "VALID",
    "REJECTED",
    "SILENT",
    "FIRES",
    "SILENT_IN_BOTH",
    "FIRES_IN_BOTH",
    "POLARITY_INVERTED",
    "REJECTION_REASONS",
    "ControlRecord",
    "BothStatesRejected",
    "BothStatesFixture",
    "control",
    "both_states",
    "both_states_control",
    "both_states_decorator",
    "outcome_of",
    "classify",
    "BothStates",
    "run_both",
    "load_fixture_pair",
]

VALID = "VALID"
REJECTED = "REJECTED"
SILENT = "SILENT"
FIRES = "FIRES"
SILENT_IN_BOTH = "silent-in-both"
FIRES_IN_BOTH = "fires-in-both"
POLARITY_INVERTED = "polarity-inverted"
REJECTION_REASONS: tuple[str, ...] = (SILENT_IN_BOTH, FIRES_IN_BOTH, POLARITY_INVERTED)

Check = Callable[[Any], Any]


@dataclass(frozen=True)
class ControlRecord:
    """Typed result of running one check against a good and a broken state.

    Shape matches ``command-center/schema/detector-control.schema.json``
    ``$defs/control_record``: ``VALID`` implies SILENT-on-good and
    FIRES-on-broken; ``REJECTED`` always carries a ``rejection_reason``.
    """

    check_id: str
    verdict: str
    good_outcome: str
    broken_outcome: str
    silent_on_good_state: bool
    fired_on_bad_state: bool
    rejection_reason: str | None = None
    description: str = ""
    good_detail: str | None = None
    broken_detail: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in (VALID, REJECTED):
            raise ValueError(f"verdict must be VALID or REJECTED, got {self.verdict!r}")
        for name in ("good_outcome", "broken_outcome"):
            if getattr(self, name) not in (SILENT, FIRES):
                raise ValueError(f"{name} must be SILENT or FIRES, got {getattr(self, name)!r}")
        if self.silent_on_good_state != (self.good_outcome == SILENT):
            raise ValueError("silent_on_good_state disagrees with good_outcome")
        if self.fired_on_bad_state != (self.broken_outcome == FIRES):
            raise ValueError("fired_on_bad_state disagrees with broken_outcome")
        if self.verdict == VALID:
            if not (self.silent_on_good_state and self.fired_on_bad_state):
                raise ValueError("VALID requires SILENT on good and FIRES on broken")
            if self.rejection_reason is not None:
                raise ValueError("VALID record cannot carry a rejection_reason")
        elif self.rejection_reason not in REJECTION_REASONS:
            raise ValueError(f"REJECTED requires a rejection_reason in {REJECTION_REASONS}")
        if not self.check_id:
            raise ValueError("check_id must be non-empty")

    @property
    def accepted(self) -> bool:
        """True when the check earned ``VALID``."""
        return self.verdict == VALID

    @property
    def rejected(self) -> bool:
        """True when the check was ``REJECTED``."""
        return self.verdict == REJECTED

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready record (schema-required keys always present)."""
        out: dict[str, Any] = {
            "check_id": self.check_id,
            "verdict": self.verdict,
            "good_outcome": self.good_outcome,
            "broken_outcome": self.broken_outcome,
            "silent_on_good_state": self.silent_on_good_state,
            "fired_on_bad_state": self.fired_on_bad_state,
            "rejection_reason": self.rejection_reason,
        }
        if self.description:
            out["description"] = self.description
        if self.good_detail is not None:
            out["good_detail"] = self.good_detail
        if self.broken_detail is not None:
            out["broken_detail"] = self.broken_detail
        for key, value in sorted(self.extra.items()):
            out.setdefault(str(key), value)
        return out

    def raise_if_rejected(self) -> "ControlRecord":
        """Return self when VALID; raise ``BothStatesRejected`` otherwise."""
        if self.verdict != VALID:
            raise BothStatesRejected(self)
        return self


class BothStatesRejected(AssertionError):
    """Raised by the asserting forms when a check is not both-states VALID."""

    def __init__(self, record: ControlRecord) -> None:
        self.record = record
        super().__init__(
            f"{record.check_id}: {record.verdict} ({record.rejection_reason}) "
            f"good={record.good_outcome} broken={record.broken_outcome}"
        )


def _describe(value: Any, limit: int = 200) -> str:
    text = repr(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def outcome_of(
    check: Check,
    state: Any,
    *,
    fires_on: tuple[type[BaseException], ...] = (AssertionError,),
) -> tuple[str, str]:
    """Run ``check`` on ``state``; return ``(SILENT|FIRES, detail)``.

    Truthy return or an exception listed in ``fires_on`` means FIRES. Other
    exceptions propagate unchanged.
    """
    try:
        result = check(state)
    except fires_on as exc:
        return FIRES, f"raised {type(exc).__name__}: {_describe(str(exc))}"
    if result:
        return FIRES, f"returned {_describe(result)}"
    return SILENT, f"returned {_describe(result)}"


def classify(good_outcome: str, broken_outcome: str) -> tuple[str, str | None]:
    """Map the two outcomes to ``(verdict, rejection_reason)``."""
    if good_outcome not in (SILENT, FIRES) or broken_outcome not in (SILENT, FIRES):
        raise ValueError(f"outcomes must be SILENT/FIRES, got {good_outcome!r}/{broken_outcome!r}")
    if good_outcome == SILENT and broken_outcome == FIRES:
        return VALID, None
    if good_outcome == SILENT and broken_outcome == SILENT:
        return REJECTED, SILENT_IN_BOTH
    if good_outcome == FIRES and broken_outcome == FIRES:
        return REJECTED, FIRES_IN_BOTH
    return REJECTED, POLARITY_INVERTED


def _check_id_for(check: Any, check_id: str | None) -> str:
    if check_id:
        return str(check_id)
    name = getattr(check, "__qualname__", None) or getattr(check, "__name__", None)
    if isinstance(name, str) and name and name != "<lambda>":
        return name
    return f"check-{type(check).__name__}-{id(check):x}"


def control(
    check: Check,
    good_state: Any,
    broken_state: Any,
    *,
    check_id: str | None = None,
    description: str = "",
    fires_on: tuple[type[BaseException], ...] = (AssertionError,),
    extra: dict[str, Any] | None = None,
) -> ControlRecord:
    """Run ``check`` on both states and emit a ``ControlRecord`` (never raises for a rejection).

    ``VALID`` only when the check is SILENT on ``good_state`` and FIRES on
    ``broken_state``; otherwise ``REJECTED`` with ``silent-in-both``,
    ``fires-in-both`` or ``polarity-inverted``.
    """
    if not callable(check):
        raise TypeError(f"check must be callable, got {type(check).__name__}")
    good_outcome, good_detail = outcome_of(check, good_state, fires_on=fires_on)
    broken_outcome, broken_detail = outcome_of(check, broken_state, fires_on=fires_on)
    verdict, reason = classify(good_outcome, broken_outcome)
    return ControlRecord(
        check_id=_check_id_for(check, check_id),
        verdict=verdict,
        good_outcome=good_outcome,
        broken_outcome=broken_outcome,
        silent_on_good_state=good_outcome == SILENT,
        fired_on_bad_state=broken_outcome == FIRES,
        rejection_reason=reason,
        description=str(description or ""),
        good_detail=good_detail,
        broken_detail=broken_detail,
        extra=dict(extra or {}),
    )


def both_states_control(
    check: Check,
    good_state: Any,
    broken_state: Any,
    **kwargs: Any,
) -> ControlRecord:
    """Asserting form: return the VALID record or raise ``BothStatesRejected``."""
    return control(check, good_state, broken_state, **kwargs).raise_if_rejected()


@dataclass(frozen=True)
class BothStatesFixture:
    """A good/broken state pair that controls any number of checks."""

    good_state: Any
    broken_state: Any
    fires_on: tuple[type[BaseException], ...] = (AssertionError,)

    def control(self, check: Check, **kwargs: Any) -> ControlRecord:
        """Non-raising control of ``check`` against this pair."""
        kwargs.setdefault("fires_on", self.fires_on)
        return control(check, self.good_state, self.broken_state, **kwargs)

    def assert_valid(self, check: Check, **kwargs: Any) -> ControlRecord:
        """Raise ``BothStatesRejected`` unless ``check`` is VALID on this pair."""
        return self.control(check, **kwargs).raise_if_rejected()

    __call__ = assert_valid

    def decorator(self, **kwargs: Any) -> Callable[[Check], Callable[[], ControlRecord]]:
        """Decorator form bound to this pair (see ``both_states_decorator``)."""
        return both_states_decorator(self.good_state, self.broken_state, fires_on=self.fires_on, **kwargs)


def both_states(
    good_state: Any,
    broken_state: Any,
    *,
    fires_on: tuple[type[BaseException], ...] = (AssertionError,),
) -> BothStatesFixture:
    """Fixture form: bind a good/broken pair, then ``.control(check)`` / ``.assert_valid(check)``."""
    return BothStatesFixture(good_state=good_state, broken_state=broken_state, fires_on=fires_on)


def both_states_decorator(
    good_state: Any,
    broken_state: Any,
    *,
    check_id: str | None = None,
    description: str = "",
    fires_on: tuple[type[BaseException], ...] = (AssertionError,),
) -> Callable[[Check], Callable[[], ControlRecord]]:
    """Decorator form: the decorated check becomes a zero-arg runner returning its ``ControlRecord``.

    The original check stays reachable as ``runner.check``; ``runner.assert_valid()``
    raises ``BothStatesRejected`` on a rejection.
    """

    def wrap(check: Check) -> Callable[[], ControlRecord]:
        if not callable(check):
            raise TypeError("both_states_decorator must decorate a callable check")
        resolved_id = _check_id_for(check, check_id)

        @functools.wraps(check)
        def runner() -> ControlRecord:
            return control(
                check,
                good_state,
                broken_state,
                check_id=resolved_id,
                description=description,
                fires_on=fires_on,
            )

        def assert_valid() -> ControlRecord:
            return runner().raise_if_rejected()

        runner.check = check  # type: ignore[attr-defined]
        runner.check_id = resolved_id  # type: ignore[attr-defined]
        runner.assert_valid = assert_valid  # type: ignore[attr-defined]
        runner.is_both_states_control = True  # type: ignore[attr-defined]
        return runner

    return wrap


# --- earlier surface (TST-0031 fixture-pair helpers), kept for existing callers ---


@dataclass
class BothStates:
    """Result of evaluating a good and a broken fixture in one process."""

    good: Any
    broken: Any
    identical: bool

    def as_record(self, check_id: str, *, good_fires: bool, broken_fires: bool) -> ControlRecord:
        """Lift raw good/broken results into a typed ``ControlRecord``."""
        good_outcome = FIRES if good_fires else SILENT
        broken_outcome = FIRES if broken_fires else SILENT
        verdict, reason = classify(good_outcome, broken_outcome)
        return ControlRecord(
            check_id=check_id,
            verdict=verdict,
            good_outcome=good_outcome,
            broken_outcome=broken_outcome,
            silent_on_good_state=good_outcome == SILENT,
            fired_on_bad_state=broken_outcome == FIRES,
            rejection_reason=reason,
            good_detail=_describe(self.good),
            broken_detail=_describe(self.broken),
        )


def run_both(good_fn: Callable[[], Any], broken_fn: Callable[[], Any]) -> BothStates:
    """Evaluate two zero-arg producers and record whether they agree."""
    good = good_fn()
    broken = broken_fn()
    return BothStates(good=good, broken=broken, identical=good == broken)


def load_fixture_pair(root: Path) -> dict[str, Path]:
    """Conventional ``<root>/good`` and ``<root>/broken`` fixture locations."""
    root = Path(root)
    return {
        "good": root / "good",
        "broken": root / "broken",
    }
