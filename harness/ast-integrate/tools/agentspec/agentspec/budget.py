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

from agentspec import wire


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
        wire.require_wire_integer(self.limit_micro, "limit_micro")
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
        wire.require_wire_integer(micro, "micro")
        if micro <= 0:
            raise ValueError(
                "micro must be positive (a zero debit is not an observation)"
            )
        if attempt <= 0:
            raise ValueError("attempt must be >= 1")
        if not unit_id:
            raise ValueError("unit_id must be non-empty")
        if any(d.unit_id == unit_id and d.attempt == attempt for d in self.debits):
            raise ValueError(f"already debited: {unit_id!r} attempt {attempt}")
        if micro > self.remaining_micro:
            raise BudgetExhausted(
                requested_micro=micro, remaining_micro=self.remaining_micro
            )
        return Ledger(
            limit_micro=self.limit_micro,
            debits=(*self.debits, Debit(unit_id=unit_id, attempt=attempt, micro=micro)),
        )


def cost_per_success(ledger: Ledger, *, successes: int) -> int:
    """Cost per SUCCESSFUL task, floor-divided — the benchmark metric that matters.

    Raw token totals flatter a run that retried a lot; this divides the WHOLE spend
    (including failed attempts) by the number of units that actually succeeded.
    """
    wire.require_wire_integer(successes, "successes")
    if successes < 0:
        raise ValueError("successes must be >= 0")
    if successes == 0:
        return 0
    return ledger.spent_micro // successes


# --------------------------------------------------------------------------- IMP-0189
# Hierarchical roll-up ledger for composed (meta) workflows. Two row kinds:
#
#   leaf    -- one unit's spend, posted ONCE under its parent node;
#   rollup  -- a node's total, COMPUTED from the rows already posted for its children (the
#              amount is never supplied by the caller, so a roll-up cannot disagree with the
#              rows under it).
#
# The double-count hazard this makes checkable: summing EVERY row (leaves + roll-ups) counts a
# leaf once per ancestor. ``naive_sum_all_rows`` deliberately exposes that wrong number so a
# probe can prove the parent total equals ``leaf_total`` and NOT the naive sum.


class DoubleCountError(ValueError):
    """A node id was posted twice. Carries the taxonomy reason and the offending id."""

    reason = "budget-double-count"

    def __init__(self, node_id: str, *, kind: str = "leaf") -> None:
        super().__init__(f"budget-double-count: {kind} {node_id!r} is already posted")
        self.node_id = node_id
        self.kind = kind


class RollupMismatch(ValueError):
    """A parent's roll-up does not equal the sum of the children it was asked about."""

    reason = "budget-rollup-mismatch"

    def __init__(self, parent_id: str, *, parent_total: int, children_total: int) -> None:
        super().__init__(
            f"budget-rollup-mismatch: {parent_id!r} totals {parent_total} but its children "
            f"total {children_total}"
        )
        self.parent_id = parent_id
        self.parent_total = parent_total
        self.children_total = children_total


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    """One immutable ledger row. ``seq`` is 1-based posting order."""

    seq: int
    node_id: str
    kind: str
    amount: int
    parent_id: str | None
    children: tuple[str, ...] = ()


class BudgetLedger:
    """Append-only roll-up ledger: rows are never edited or removed, only posted."""

    __slots__ = ("_rows", "_by_id")

    def __init__(self) -> None:
        self._rows: list[LedgerEntry] = []
        self._by_id: dict[str, LedgerEntry] = {}

    @property
    def entries(self) -> tuple[LedgerEntry, ...]:
        return tuple(self._rows)

    def __len__(self) -> int:
        return len(self._rows)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._by_id

    def entry(self, node_id: str) -> LedgerEntry:
        try:
            return self._by_id[node_id]
        except KeyError:
            raise KeyError(f"no ledger row for {node_id!r}") from None

    def total_for(self, node_id: str) -> int:
        """The posted amount of a leaf, or the computed total of a roll-up."""
        return self.entry(node_id).amount

    def _append(self, entry_kind: str, node_id: str, amount: int, parent_id: str | None,
                children: tuple[str, ...]) -> LedgerEntry:
        if not node_id:
            raise ValueError("node_id must be non-empty")
        if node_id in self._by_id:
            raise DoubleCountError(node_id, kind=self._by_id[node_id].kind)
        row = LedgerEntry(
            seq=len(self._rows) + 1,
            node_id=node_id,
            kind=entry_kind,
            amount=amount,
            parent_id=parent_id,
            children=children,
        )
        self._rows.append(row)
        self._by_id[node_id] = row
        return row

    def post_leaf(self, node_id: str, amount: int, *, parent_id: str | None) -> LedgerEntry:
        """Post one unit's spend. A second posting of the same id is a :class:`DoubleCountError`."""
        wire.require_wire_integer(amount, "amount")
        if amount < 0:
            raise ValueError("amount must be >= 0")
        return self._append("leaf", node_id, amount, parent_id, ())

    def post_rollup(
        self, node_id: str, children: tuple[str, ...] | list[str], *, parent_id: str | None = None
    ) -> LedgerEntry:
        """Post a node's total as the sum of its ALREADY-POSTED children (never a caller value)."""
        child_ids = tuple(children)
        if len(set(child_ids)) != len(child_ids):
            duplicate = next(c for c in child_ids if child_ids.count(c) > 1)
            raise DoubleCountError(duplicate, kind="child")
        amount = sum(self.total_for(child) for child in child_ids)
        return self._append("rollup", node_id, amount, parent_id, child_ids)

    def leaf_total(self) -> int:
        """The real spend: every leaf counted exactly once."""
        return sum(row.amount for row in self._rows if row.kind == "leaf")

    def naive_sum_all_rows(self) -> int:
        """The WRONG total a flat ``sum`` over the ledger gives -- every leaf counted once per
        ancestor. Exposed so the double-count it hides can be asserted against, not repeated."""
        return sum(row.amount for row in self._rows)

    def assert_sum_equals_children(self, parent_id: str, child_ids: tuple[str, ...]) -> int:
        """Prove ``parent_id``'s roll-up equals the sum of ``child_ids``; return that total."""
        parent = self.entry(parent_id)
        if parent.kind != "rollup":
            raise RollupMismatch(
                parent_id, parent_total=parent.amount, children_total=parent.amount
            )
        children_total = sum(self.total_for(child) for child in child_ids)
        if set(child_ids) != set(parent.children) or children_total != parent.amount:
            raise RollupMismatch(
                parent_id, parent_total=parent.amount, children_total=children_total
            )
        return parent.amount
