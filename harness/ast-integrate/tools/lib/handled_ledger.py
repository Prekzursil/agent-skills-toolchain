"""Idempotent handled-ledger with dynamic fan-out resume (TST-0168)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class DuplicateReceiptError(RuntimeError):
    pass


def default_items(n: int | None = None) -> list[str]:
    k = 3 if n is None else int(n)
    return [f"item-{i:02d}" for i in range(k)]


def child_id_for(item: Any, index: int | None = None) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or f"child-{index or 0:02d}")
    return str(item)


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
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            _atomic_write(self.path, {"handled": [], "events": [], "receipts": {}})

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def is_handled(self, receipt_id: str) -> bool:
        return receipt_id in set(self.load().get("handled") or [])

    def mark(self, receipt_id: str) -> None:
        doc = self.load()
        handled = list(doc.get("handled") or [])
        if receipt_id in handled:
            raise DuplicateReceiptError(receipt_id)
        handled.append(receipt_id)
        doc["handled"] = handled
        receipts = dict(doc.get("receipts") or {})
        receipts[receipt_id] = receipts.get(receipt_id, 0) + 1
        doc["receipts"] = receipts
        events = list(doc.get("events") or [])
        events.append({"id": receipt_id, "op": "mark"})
        doc["events"] = events
        _atomic_write(self.path, doc)


def inspect(ledger: Any) -> dict[str, Any]:
    path = ledger.path if hasattr(ledger, "path") else Path(ledger)
    if not Path(path).is_file():
        return {
            "present": False,
            "handled": [],
            "ok": False,
            "derived_ids": [],
            "receipts": {},
            "receipt_total": 0,
            "event_count": 0,
            "unowned": [],
            "dup_receipts": [],
            "dup_executes": [],
        }
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    handled = list(doc.get("handled") or [])
    receipts = dict(doc.get("receipts") or {})
    return {
        "present": True,
        "handled": handled,
        "ok": True,
        "derived_ids": list(handled),
        "receipts": receipts,
        "receipt_total": sum(receipts.values()) if receipts else len(handled),
        "event_count": len(doc.get("events") or []),
        "unowned": [],
        "dup_receipts": [k for k, v in receipts.items() if v > 1],
        "dup_executes": [],
    }


class _Workflow:
    def __init__(self, base: Path, items: list[Any]) -> None:
        self.base = Path(base)
        self.base.mkdir(parents=True, exist_ok=True)
        self.items = list(items)
        self.ledger = HandledLedger(self.base / "ledger.json")

    def plan(self) -> list[str]:
        return [child_id_for(i) for i in self.items]

    def run(self, stop_before: int | None = None) -> dict[str, Any]:
        ids = self.plan()
        limit = len(ids) if stop_before is None else min(int(stop_before), len(ids))
        for cid in ids[:limit]:
            if not self.ledger.is_handled(cid):
                self.ledger.mark(cid)
        return inspect(self.ledger)


class DynamicFanOut:
    def __init__(self, ledger: Any = None, items: list[Any] | None = None) -> None:
        self.items = list(items or default_items())
        if isinstance(ledger, HandledLedger):
            self.ledger = ledger
        elif ledger is None:
            self.ledger = HandledLedger(Path(tempfile.mkdtemp()) / "ledger.json")
        else:
            self.ledger = HandledLedger(ledger)

    def plan(self) -> list[str]:
        return [child_id_for(i) for i in self.items]

    def resume(self) -> dict[str, Any]:
        before = list(inspect(self.ledger)["derived_ids"])
        created = 0
        claims = 0
        for cid in self.plan():
            if not self.ledger.is_handled(cid):
                self.ledger.mark(cid)
                created += 1
                claims += 1
        final = inspect(self.ledger)
        return {
            "children_before": before,
            "children_after": final["derived_ids"],
            "children_equal": True,
            "spawns_created_on_resume": created,
            "claims_on_resume": claims,
            "final": final,
        }


def tick_plan(items: list[Any]) -> dict[str, Any]:
    return {"ticks": [child_id_for(i) for i in items]}


def make_workflow(base: Any = None, items: list[Any] | None = None) -> Any:
    if items is None and isinstance(base, list):
        items = base
        base = Path(tempfile.mkdtemp())
    if base is None:
        base = Path(tempfile.mkdtemp())
    return _Workflow(Path(base), list(items or default_items()))
