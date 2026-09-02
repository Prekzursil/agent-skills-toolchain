"""Idempotent handled-ledger with dynamic fan-out resume (TST-0168).

The ledger is an append-only JSON event log on disk. A workflow derives its children from its
items deterministically (``child_id_for``) and advances in ticks; each child goes through three
ticks - ``spawn`` (the child exists), ``claim`` (this workflow owns it), ``receipt`` (the child
was executed exactly once and its receipt recorded). A crash is modelled as stopping before a
tick and dropping every in-memory object: resume re-reads the file, RE-DERIVES the children from
the items, and completes only the ticks the ledger does not already show.

Invariants ``inspect`` measures (never declared):
  * every derived child has exactly one receipt          -> ``receipts`` / ``dup_receipts``
  * every spawned child is claimed                        -> ``unowned``
  * a child is executed at most once                      -> ``dup_executes``
A second ``child_receipt`` for the same child is refused with ``DuplicateReceiptError`` unless
the caller explicitly plants it (``allow_duplicate_receipt=True``, used by the mutant control).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

TICK_KINDS: tuple[str, ...] = ("spawn", "claim", "receipt")


class DuplicateReceiptError(RuntimeError):
    """A child already has a receipt; recording a second one is refused."""


def default_items(n: int | None = None) -> list[str]:
    k = 3 if n is None else int(n)
    return [f"item-{i:02d}" for i in range(k)]


def child_id_for(item: Any, index: int | None = None) -> str:
    """Deterministic child id: same item -> same child on every derivation."""
    if isinstance(item, dict):
        return str(item.get("id") or f"child-{index or 0:02d}")
    return f"child:{item}"


def _atomic_write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class HandledLedger:
    """Append-only event log; every read goes back to the bytes on disk."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            _atomic_write(self.path, {"events": []})

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def events(self, kind: str | None = None) -> list[dict[str, Any]]:
        evs = [e for e in (self.load().get("events") or []) if isinstance(e, dict)]
        if kind is None:
            return evs
        return [e for e in evs if e.get("kind") == kind]

    def children(self, kind: str) -> list[str]:
        out: list[str] = []
        for e in self.events(kind):
            cid = str(e.get("child_id"))
            if cid not in out:
                out.append(cid)
        return out

    def receipt_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for e in self.events("child_receipt"):
            cid = str(e.get("child_id"))
            counts[cid] = counts.get(cid, 0) + 1
        return counts

    def is_handled(self, child_id: str) -> bool:
        return child_id in self.receipt_counts()

    def append(self, event: dict[str, Any], *, allow_duplicate_receipt: bool = False) -> None:
        doc = self.load()
        events = list(doc.get("events") or [])
        if event.get("kind") == "child_receipt" and not allow_duplicate_receipt:
            cid = str(event.get("child_id"))
            if any(e.get("kind") == "child_receipt" and str(e.get("child_id")) == cid for e in events):
                raise DuplicateReceiptError(cid)
        events.append(dict(event))
        doc["events"] = events
        _atomic_write(self.path, doc)

    def mark(self, child_id: str, tick: int | None = None, source: str = "mark") -> None:
        """Record one execution and its receipt for ``child_id`` (refuses a second receipt)."""
        if self.is_handled(child_id):
            raise DuplicateReceiptError(child_id)
        self.append({"kind": "child_execute", "tick": tick, "child_id": child_id, "source": source})
        self.append({"kind": "child_receipt", "tick": tick, "child_id": child_id, "source": source})


def _derive(items: list[Any]) -> list[str]:
    return [child_id_for(item, i) for i, item in enumerate(items)]


def inspect(ledger: HandledLedger, items: list[Any] | None = None) -> dict[str, Any]:
    """Measure the ledger's invariants from its events alone."""
    spawned = ledger.children("child_spawn")
    claimed = set(ledger.children("child_claim"))
    receipts = ledger.receipt_counts()
    executes: dict[str, int] = {}
    for e in ledger.events("child_execute"):
        cid = str(e.get("child_id"))
        executes[cid] = executes.get(cid, 0) + 1
    derived_ids = _derive(items) if items is not None else list(spawned)
    unowned = [cid for cid in spawned if cid not in claimed]
    dup_receipts = sorted(cid for cid, n in receipts.items() if n > 1)
    dup_executes = sorted(cid for cid, n in executes.items() if n > 1)
    complete = all(receipts.get(cid) == 1 for cid in derived_ids)
    return {
        "ok": bool(complete and not unowned and not dup_receipts and not dup_executes),
        "derived_ids": derived_ids,
        "spawned": spawned,
        "receipts": receipts,
        "receipt_total": sum(receipts.values()),
        "event_count": len(ledger.events()),
        "unowned": unowned,
        "dup_receipts": dup_receipts,
        "dup_executes": dup_executes,
    }


def tick_plan(items: list[Any]) -> list[tuple[str, str]]:
    """Ticks in execution order: (kind, child_id) with spawn -> claim -> receipt per child."""
    plan: list[tuple[str, str]] = []
    for cid in _derive(list(items)):
        for kind in TICK_KINDS:
            plan.append((kind, cid))
    return plan


def _apply_tick(ledger: HandledLedger, tick_index: int, kind: str, cid: str, source: str) -> bool:
    """Apply one tick idempotently; return True when the ledger changed."""
    if kind == "spawn":
        if cid in ledger.children("child_spawn"):
            return False
        ledger.append({"kind": "child_spawn", "tick": tick_index, "child_id": cid, "source": source})
        return True
    if kind == "claim":
        if cid in ledger.children("child_claim"):
            return False
        ledger.append({"kind": "child_claim", "tick": tick_index, "child_id": cid, "source": source})
        return True
    if kind == "receipt":
        if ledger.is_handled(cid):
            return False
        ledger.mark(cid, tick=tick_index, source=source)
        return True
    raise ValueError(f"unknown tick kind {kind!r}")


class _Workflow:
    def __init__(self, base: Path, items: list[Any]) -> None:
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.items = list(items)
        self.ledger = HandledLedger(self.base / "ledger.json")

    def plan(self) -> list[tuple[str, str]]:
        return tick_plan(self.items)

    def first_spawn_tick(self) -> int:
        return next(i for i, t in enumerate(self.plan()) if t[0] == "spawn")

    def run(self, stop_before: int | None = None) -> dict[str, Any]:
        """Advance tick by tick; ``stop_before=k`` crashes before tick ``k`` is applied."""
        plan = self.plan()
        limit = len(plan) if stop_before is None else max(0, min(int(stop_before), len(plan)))
        for i, (kind, cid) in enumerate(plan[:limit]):
            _apply_tick(self.ledger, i, kind, cid, source="run")
        return inspect(self.ledger, self.items)


class DynamicFanOut:
    """Resume a crashed workflow from its ledger by re-deriving the children from the items."""

    def __init__(self, ledger: Any = None, items: list[Any] | None = None) -> None:
        self.items = list(items or default_items())
        if isinstance(ledger, HandledLedger):
            self.ledger = ledger
        elif ledger is None:
            self.ledger = HandledLedger(Path(tempfile.mkdtemp()) / "ledger.json")
        else:
            self.ledger = HandledLedger(ledger)

    def plan(self) -> list[tuple[str, str]]:
        return tick_plan(self.items)

    def resume(self, *, claim: bool = True, continue_run: bool = True) -> dict[str, Any]:
        before = list(self.ledger.children("child_spawn"))
        derived = _derive(self.items)
        spawns = 0
        claims = 0
        for i, (kind, cid) in enumerate(self.plan()):
            if kind == "spawn":
                spawns += int(_apply_tick(self.ledger, i, kind, cid, source="resume"))
            elif kind == "claim" and claim:
                claims += int(_apply_tick(self.ledger, i, kind, cid, source="resume"))
        after_rederive = inspect(self.ledger, self.items)
        if continue_run:
            for i, (kind, cid) in enumerate(self.plan()):
                if kind == "receipt" and (claim or cid in set(self.ledger.children("child_claim"))):
                    _apply_tick(self.ledger, i, kind, cid, source="resume")
        final = inspect(self.ledger, self.items)
        return {
            "children_before": before,
            "children_after": final["derived_ids"],
            "children_equal": final["derived_ids"] == derived and set(before) <= set(derived),
            "spawns_created_on_resume": spawns,
            "claims_on_resume": claims,
            "after_rederive": after_rederive,
            "final": final,
        }


def make_workflow(base: Any = None, items: list[Any] | None = None) -> _Workflow:
    if items is None and isinstance(base, list):
        items = base
        base = Path(tempfile.mkdtemp())
    if base is None:
        base = Path(tempfile.mkdtemp())
    return _Workflow(Path(base), list(items or default_items()))
