"""Lossy-import ledger: translation losses are loud, never silent.

Contract (IMP-0168):
  Every import writes what did NOT survive translation (construct, source
  span, reason, whether it is semantically load-bearing). An empty ledger
  is legal only when accounting proves 100% of source constructs were
  preserved. Unaccounted constructs are a failure (uncontrolled-silence).

Coverage is computed: (preserved + lost) / source, never asserted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Literal

Disposition = Literal["preserved", "lost"]

# Fail-closed: unknown kinds are load-bearing unless explicitly cosmetic.
COSMETIC_KINDS = frozenset(
    {
        "cosmetic_metadata",
        "description",
        "title",
        "comment",
    }
)


@dataclass(frozen=True)
class SourceSpan:
    path: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceConstruct:
    construct_id: str
    kind: str
    span: SourceSpan
    payload: Any = None

    @property
    def load_bearing(self) -> bool:
        return self.kind not in COSMETIC_KINDS

    def to_dict(self) -> dict[str, Any]:
        return {
            "construct_id": self.construct_id,
            "kind": self.kind,
            "span": self.span.to_dict(),
            "load_bearing": self.load_bearing,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class LedgerEntry:
    construct_id: str
    construct: str
    source_span: SourceSpan
    reason: str
    load_bearing: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "construct_id": self.construct_id,
            "construct": self.construct,
            "source_span": self.source_span.to_dict(),
            "reason": self.reason,
            "load_bearing": self.load_bearing,
        }


@dataclass
class Accounting:
    source_count: int
    preserved_count: int
    lost_count: int
    unaccounted_ids: tuple[str, ...]
    extra_ids: tuple[str, ...]
    double_counted_ids: tuple[str, ...]
    coverage_pct: float | None
    empty_ledger_justified: bool
    ok: bool
    failures: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EXPRESSIBLE_KINDS = frozenset(
    {
        "agent_call",
        "parallel_fanout",
        "phase",
        "work_unit",
        "timeout",
        "prompt_file",
        "dag_node",
        "dag_edge",
    }
)

INEXPRESSIBLE_REASON = {
    "eval_call": "inexpressible:dynamic-eval-not-in-typed-workflow",
    "background_fire_forget": "inexpressible:fire-and-forget-not-in-typed-workflow",
    "native_while": "inexpressible:unbounded-loop-not-in-typed-workflow",
    "unknown_field": "inexpressible:unknown-field-rejected-not-dropped",
    "cosmetic_metadata": "cosmetic:not-in-typed-workflow",
    "description": "cosmetic:not-in-typed-workflow",
    "title": "cosmetic:not-in-typed-workflow",
    "comment": "cosmetic:not-in-typed-workflow",
}


def reason_for(kind: str) -> str:
    return INEXPRESSIBLE_REASON.get(kind, f"inexpressible:{kind}-not-in-typed-workflow")


def translate(
    constructs: Iterable[SourceConstruct],
    *,
    expressible_kinds: frozenset[str] | None = None,
    silent_drop: bool = False,
) -> tuple[list[SourceConstruct], list[LedgerEntry]]:
    """Map each source construct to preserved (typed) or lost (ledger).

    silent_drop=True is the broken-state mutant: inexpressible constructs
    vanish with no ledger row. Accounting must then fail closed.
    """
    allowed = expressible_kinds if expressible_kinds is not None else EXPRESSIBLE_KINDS
    preserved: list[SourceConstruct] = []
    losses: list[LedgerEntry] = []
    for construct in constructs:
        if construct.kind in allowed:
            preserved.append(construct)
            continue
        if silent_drop:
            continue
        losses.append(
            LedgerEntry(
                construct_id=construct.construct_id,
                construct=construct.kind,
                source_span=construct.span,
                reason=reason_for(construct.kind),
                load_bearing=construct.load_bearing,
            )
        )
    return preserved, losses


def account(
    source: Iterable[SourceConstruct],
    preserved: Iterable[SourceConstruct],
    losses: Iterable[LedgerEntry],
) -> Accounting:
    src_ids = [c.construct_id for c in source]
    src_set = set(src_ids)
    if len(src_ids) != len(src_set):
        dup = sorted({i for i in src_ids if src_ids.count(i) > 1})
        return Accounting(
            source_count=len(src_ids),
            preserved_count=0,
            lost_count=0,
            unaccounted_ids=(),
            extra_ids=(),
            double_counted_ids=tuple(dup),
            coverage_pct=None,
            empty_ledger_justified=False,
            ok=False,
            failures=("duplicate-source-construct-id",),
        )

    pres_ids = {c.construct_id for c in preserved}
    loss_ids = {e.construct_id for e in losses}
    double = tuple(sorted(pres_ids & loss_ids))
    accounted = pres_ids | loss_ids
    unaccounted = tuple(sorted(src_set - accounted))
    extra = tuple(sorted(accounted - src_set))
    n_src = len(src_set)
    n_pres = len(pres_ids - loss_ids)
    n_lost = len(loss_ids - pres_ids)
    # Empty source is not 100% by vacuity: a gate that cannot fail is a no-op.
    if n_src == 0:
        coverage: float | None = None
        empty_ok = False
        failures = ("empty-source-fail-closed",)
        ok = False
    else:
        coverage = 100.0 * len(accounted & src_set) / n_src
        failures_list: list[str] = []
        if unaccounted:
            failures_list.append("unaccounted-constructs")
        if extra:
            failures_list.append("ledger-or-preserve-unknown-id")
        if double:
            failures_list.append("double-counted-construct")
        if coverage != 100.0:
            failures_list.append("coverage-not-100")
        empty_ok = n_lost == 0 and not unaccounted and n_pres == n_src
        if n_lost == 0 and not empty_ok:
            failures_list.append("empty-ledger-unjustified")
        failures = tuple(failures_list)
        ok = not failures

    return Accounting(
        source_count=n_src,
        preserved_count=n_pres,
        lost_count=n_lost,
        unaccounted_ids=unaccounted,
        extra_ids=extra,
        double_counted_ids=double,
        coverage_pct=coverage,
        empty_ledger_justified=empty_ok,
        ok=ok,
        failures=failures,
    )


def ledger_from_import(
    source: list[SourceConstruct],
    *,
    silent_drop: bool = False,
) -> tuple[list[SourceConstruct], list[LedgerEntry], Accounting]:
    preserved, losses = translate(source, silent_drop=silent_drop)
    return preserved, losses, account(source, preserved, losses)


def require_ledger_shape(entries: Iterable[LedgerEntry]) -> list[str]:
    """Every loss row must carry construct, span, reason, load-bearing flag."""
    errors: list[str] = []
    for entry in entries:
        if not entry.construct:
            errors.append(f"{entry.construct_id}:missing-construct")
        span = entry.source_span
        if span.start_line < 1 or span.start_col < 1:
            errors.append(f"{entry.construct_id}:span-not-1-indexed")
        if not entry.reason:
            errors.append(f"{entry.construct_id}:missing-reason")
        if not isinstance(entry.load_bearing, bool):
            errors.append(f"{entry.construct_id}:load-bearing-not-bool")
    return errors
