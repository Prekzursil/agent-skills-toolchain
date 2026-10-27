"""Lossy-import ledger: translation losses are loud, not silent (IMP-0168).

translate() classifies every inventoried construct as preserved (expressible in
the typed Workflow) or lost (a ledger row: construct, source span, reason, and a
semantically-load-bearing flag). account() requires preserved_ids | lost_ids ==
source_ids - an empty ledger is justified ONLY when lost==0, unaccounted==0,
preserved==source and source_count>0. An empty SOURCE fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from inventory import EXPRESSIBLE_KINDS, Inventory

REASON_INEXPRESSIBLE = "no-expressible-node-type"


@dataclass(frozen=True)
class LostRow:
    construct_id: str
    kind: str
    span: str
    reason: str
    load_bearing: bool


@dataclass
class Translation:
    adapter_shape: str
    source: str
    source_count: int
    preserved_ids: set[str] = field(default_factory=set)
    lost: list[LostRow] = field(default_factory=list)

    def lost_ids(self) -> set[str]:
        return {row.construct_id for row in self.lost}


_LOAD_BEARING_KINDS = frozenset({"raw-escape", "free-form-branch"})


def translate(inv: Inventory) -> Translation:
    if not inv.constructs:
        raise ValueError("empty source inventory: fails closed, never translates to nothing")
    t = Translation(inv.adapter_shape, inv.source, len(inv.constructs))
    for c in inv.constructs:
        if c.kind in EXPRESSIBLE_KINDS:
            t.preserved_ids.add(c.id)
        else:
            t.lost.append(LostRow(
                construct_id=c.id,
                kind=c.kind,
                span=c.span,
                reason=REASON_INEXPRESSIBLE,
                load_bearing=c.kind in _LOAD_BEARING_KINDS,
            ))
    return t


def translate_silent_drop(inv: Inventory) -> Translation:
    """MUTANT: the silent degradation this module exists to forbid.

    Drops inexpressible constructs from the result entirely instead of writing a
    ledger row - the accounting must go red on this behaviour.
    """
    t = Translation(inv.adapter_shape, inv.source, len(inv.constructs))
    for c in inv.constructs:
        if c.kind in EXPRESSIBLE_KINDS:
            t.preserved_ids.add(c.id)
    return t


def account(inv: Inventory, t: Translation) -> dict[str, Any]:
    """Construct accounting: sums must cover 100 percent of the source inventory."""
    source_ids = inv.ids()
    preserved = set(t.preserved_ids)
    lost = t.lost_ids()
    overlap = preserved & lost
    unaccounted = source_ids - (preserved | lost)
    unknown_ids = (preserved | lost) - source_ids
    covered = len(preserved) + len(lost) - len(overlap)
    total = len(source_ids)
    coverage_pct = (100.0 * covered / total) if total else 0.0
    empty_ledger_justified = (
        len(t.lost) == 0 and not unaccounted and preserved == source_ids and total > 0
    )
    return {
        "source_count": total,
        "preserved_count": len(preserved),
        "lost_count": len(t.lost),
        "coverage_pct": coverage_pct,
        "unaccounted_ids": sorted(unaccounted),
        "overlap_ids": sorted(overlap),
        "unknown_ids": sorted(unknown_ids),
        "empty_ledger_justified": empty_ledger_justified,
        "ok": bool(
            total > 0
            and not overlap
            and not unaccounted
            and not unknown_ids
            and abs(coverage_pct - 100.0) < 1e-9
        ),
    }
