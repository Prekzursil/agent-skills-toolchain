"""Budget accounting: an immutable ledger that is monotonic and cannot double-count.

Every amount is an integer count of MICRO-units. Floats are refused at the boundary, not
merely discouraged: an integral float serialises as ``1.0`` from Python and ``1`` from JS, and
``-0.0``/``1e16`` diverge too — six of seven measured cases (README "UNVERIFIED follow-up").
Refusing floats deletes that whole divergence class from the wire.

``debit`` returns a NEW ledger. A counter mutated inside a helper is a measured loss class
(the value evaporates in a subshell / a copy), so the ledger is a value, not an accumulator.
"""

from __future__ import annotations

from dataclasses import dataclass


class BudgetExhausted(Exception):
    """Raised when a debit would exceed the ceiling. Carries the taxonomy reason."""

    reason = "budget-exhausted"

    def __init__(self, *, requested_micro: int, remaining_micro: int) -> None:
        super().__init__(
            f"budget-exhausted: requested {requested_micro} micro, "
            f"{remaining_micro} micro remaining"
        )
        self.requested_micro = requested_micro
        self.remaining_micro = remaining_micro


@dataclass(frozen=True, slots=True)
class Debit:
    """One charge, keyed by ``(unit_id, attempt)`` so a replay cannot double-count."""

    unit_id: str
    attempt: int
    micro: int


@dataclass(frozen=True, slots=True)
class Ledger:
    """A budget ceiling plus the ordered debits taken against it."""

    limit_micro: int
    debits: tuple[Debit, ...] = ()

    def __post_init__(self) -> None:
        if self.limit_micro < 0:
            raise ValueError("limit_micro must be >= 0")

    @property
    def spent_micro(self) -> int:
        """The sum of every debit — the totals ALWAYS reconcile by construction."""
        return sum(d.micro for d in self.debits)

    @property
    def remaining_micro(self) -> int:
        return self.limit_micro - self.spent_micro

    @property
    def exhausted(self) -> bool:
        return self.remaining_micro <= 0

    def debit(self, unit_id: str, *, attempt: int, micro: int) -> Ledger:
        """Return a new ledger with one more debit, or raise."""
        _require_int(micro, "micro")
        if micro <= 0:
            raise ValueError("micro must be positive (a zero debit is not an observation)")
        if attempt <= 0:
            raise ValueError("attempt must be >= 1")
        if not unit_id:
            raise ValueError("unit_id must be non-empty")
        if any(d.unit_id == unit_id and d.attempt == attempt for d in self.debits):
            raise ValueError(f"already debited: {unit_id!r} attempt {attempt}")
        if micro > self.remaining_micro:
            raise BudgetExhausted(requested_micro=micro, remaining_micro=self.remaining_micro)
        return Ledger(
            limit_micro=self.limit_micro,
            debits=(*self.debits, Debit(unit_id=unit_id, attempt=attempt, micro=micro)),
        )


def cost_per_success(ledger: Ledger, *, successes: int) -> int:
    """Cost per SUCCESSFUL task, floor-divided — the benchmark metric that matters.

    Raw token totals flatter a run that retried a lot; this divides the WHOLE spend
    (including failed attempts) by the number of units that actually succeeded.
    """
    if successes < 0:
        raise ValueError("successes must be >= 0")
    if successes == 0:
        return 0
    return ledger.spent_micro // successes


def _require_int(value: object, name: str) -> None:
    """Reject ``bool`` explicitly: ``isinstance(True, int)`` is True in Python."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int (micro-units), not {type(value).__name__}")
