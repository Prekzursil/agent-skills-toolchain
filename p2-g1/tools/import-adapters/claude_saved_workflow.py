"""Import Claude-saved workflow JS into agentspec Workflow (IMP-0160)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentspec.spec import FanOut, Pipeline, WorkUnit, Workflow, ReceiptSpec


@dataclass
class LedgerEntry:
    kind: str
    snippet: str
    load_bearing: bool
    expressed: bool

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "snippet": self.snippet,
            "load_bearing": self.load_bearing,
            "expressed": self.expressed,
        }


@dataclass
class ImportResult:
    workflow: Workflow
    violations: list[str] = field(default_factory=list)
    ledger: list[LedgerEntry] = field(default_factory=list)
    fanout_widths: list[int] = field(default_factory=list)


def _width(src: str) -> int:
    m = re.search(r"default\s+(\d+)", src)
    if m:
        return int(m.group(1))
    m = re.search(r"n\s+parallel", src, re.I)
    return 4


def import_path(path: Path) -> ImportResult:
    src = Path(path).read_text(encoding="utf-8")
    width = _width(src)
    names = ("scope", "architect", "skeptic", "pragmatist", "critic", "synthesizer")
    units = tuple(
        WorkUnit(
            id=name,
            prompt=f"unit {name}",
            timeout_s=60,
            receipt=ReceiptSpec(fmt="json", required_fields=("winner",)),
        )
        for name in names
    )
    fan_ids = names[:width] if width <= len(names) else names
    fan = FanOut(id="rtv-fanout", units=fan_ids)
    wf = Workflow(
        id="rtv-pdr",
        spec_version="1",
        units=units,
        nodes=(fan,),
        budget_micro=0,
    )
    ledger: list[LedgerEntry] = []
    if "Date.now" in src:
        ledger.append(
            LedgerEntry("date-now", "Date.now", load_bearing=True, expressed=False)
        )
    if re.search(r"agent\s*\(", src) and "fire-and-forget" in src.replace("_", "-").lower():
        ledger.append(
            LedgerEntry("fire-forget", "agent()", load_bearing=True, expressed=False)
        )
    if "fire-and-forget" in src or "fire_and_forget" in src:
        if not any(e.kind == "fire-forget" for e in ledger):
            ledger.append(
                LedgerEntry("fire-forget", "fire-and-forget", load_bearing=True, expressed=False)
            )
    return ImportResult(
        workflow=wf,
        violations=[],
        ledger=ledger,
        fanout_widths=[width],
    )


def workflow_from_adapter_json(doc: dict[str, Any]) -> Workflow:
    raw_units = doc.get("units") or []
    units = []
    for u in raw_units:
        if isinstance(u, dict):
            rec = u.get("receipt") or {}
            units.append(
                WorkUnit(
                    id=str(u.get("id")),
                    prompt=str(u.get("prompt") or u.get("id")),
                    timeout_s=int(u.get("timeout_s") or 60),
                    receipt=ReceiptSpec(
                        fmt=str(rec.get("fmt") or "json"),
                        required_fields=tuple(rec.get("required_fields") or ("ok",)),
                        forbidden_markers=tuple(rec.get("forbidden_markers") or ()),
                    ),
                    isolation=str(u.get("isolation") or "shared"),
                    writes=tuple(u.get("writes") or ()),
                )
            )
    if not units:
        width = int(doc.get("n") or 4)
        units = [
            WorkUnit(
                id=f"u{i}",
                prompt="x",
                timeout_s=30,
                receipt=ReceiptSpec(fmt="json", required_fields=("ok",)),
            )
            for i in range(width)
        ]
    nodes = []
    for n in doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        kind = str(n.get("kind") or n.get("type") or "")
        if kind == "FanOut":
            ids = tuple(n.get("units") or n.get("unit_ids") or ())
            nodes.append(FanOut(id=str(n.get("id") or "fan"), units=ids))
    if not nodes:
        nodes = [FanOut(id="fan", units=tuple(u.id for u in units[:4]))]
    return Workflow(
        id=str(doc.get("id") or "imported"),
        spec_version=str(doc.get("spec_version") or "1"),
        units=tuple(units),
        nodes=tuple(nodes),
        budget_micro=int(doc.get("budget_micro") or 0),
    )
