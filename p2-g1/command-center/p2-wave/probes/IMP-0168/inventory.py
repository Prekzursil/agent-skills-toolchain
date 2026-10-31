"""Construct inventory for the three adapter shapes (IMP-0168).

Every source a translation imports is inventoried into explicit constructs
(id, kind, span). Accounting later requires preserved | lost == this inventory,
so the inventory is the denominator that makes an empty ledger provable.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# The expressible target vocabulary: the typed Workflow node/unit kinds.
EXPRESSIBLE_KINDS = frozenset({
    "unit",
    "fanout",
    "barrier",
    "pipeline",
    "human-checkpoint",
    "subworkflow",
})


@dataclass(frozen=True)
class Construct:
    id: str
    kind: str
    span: str
    construct: str


@dataclass(frozen=True)
class Inventory:
    adapter_shape: str
    source: str
    constructs: tuple[Construct, ...]

    def ids(self) -> set[str]:
        return {c.id for c in self.constructs}


_MARKERS = (
    (re.compile(r"^\s*export\s+default\s+function\s+(\w+)"), "unit"),
    (re.compile(r"^\s*export\s+const\s+(\w+)\s*="), "unit"),
    (re.compile(r"^\s*export\s+async\s+function\s+(\w+)"), "unit"),
    (re.compile(r"^\s*parallel\(\s*\["), "fanout"),
    (re.compile(r"^\s*await\s+join\(\s*\["), "barrier"),
    (re.compile(r"^\s*sequence\(\s*\["), "pipeline"),
    (re.compile(r"^\s*await\s+humanApproval\((.*)\)"), "human-checkpoint"),
    (re.compile(r"^\s*runRaw\((.*)\)"), "raw-escape"),
    (re.compile(r"^\s*freeform\(\s*(?:'|\"|`)(\w+)"), "free-form-branch"),
)


def inventory_claude_mjs(path: Path) -> Inventory:
    """Line-structural scan of a claude .mjs workflow source."""
    constructs: list[Construct] = []
    text = path.read_text(encoding="utf-8")
    for lineno, line in enumerate(text.splitlines(), start=1):
        for rx, kind in _MARKERS:
            m = rx.match(line)
            if m:
                name = m.group(1) if m.groups() and m.group(1) else kind
                constructs.append(Construct(
                    id=f"{path.stem}:{name}",
                    kind=kind,
                    span=f"{path.name}:{lineno}",
                    construct=line.strip()[:120],
                ))
                break
    return Inventory("claude_mjs", path.name, tuple(constructs))


def _kind_to_vocab(kind: str) -> str:
    return {
        "WorkUnit": "unit",
        "FanOut": "fanout",
        "Barrier": "barrier",
        "Pipeline": "pipeline",
        "HumanCheckpoint": "human-checkpoint",
        "Subworkflow": "subworkflow",
    }.get(kind, kind)


def inventory_codex_json(path: Path) -> Inventory:
    doc = json.loads(path.read_text(encoding="utf-8"))
    constructs: list[Construct] = []
    for i, raw in enumerate(doc.get("constructs") or [], start=1):
        kind = str(raw.get("kind") or "")
        constructs.append(Construct(
            id=str(raw.get("id") or f"{path.stem}-c{i}"),
            kind=_kind_to_vocab(kind),
            span=f"{path.name}#/{raw.get('at') or i}",
            construct=json.dumps(raw, sort_keys=True)[:120],
        ))
    return Inventory("codex_json", path.name, tuple(constructs))


def inventory_dag_json(path: Path) -> Inventory:
    doc = json.loads(path.read_text(encoding="utf-8"))
    dag = doc.get("dag") or {}
    constructs: list[Construct] = []
    for i, task in enumerate(dag.get("tasks") or [], start=1):
        ttype = str(task.get("type") or "unit")
        constructs.append(Construct(
            id=str(task.get("id") or f"{path.stem}-t{i}"),
            kind=_kind_to_vocab(ttype),
            span=f"{path.name}#/dag/tasks/{i}",
            construct=json.dumps(task, sort_keys=True)[:120],
        ))
    for i, edge in enumerate(dag.get("edges") or [], start=1):
        constructs.append(Construct(
            id=str(edge.get("id") or f"{path.stem}-e{i}"),
            kind="pipeline",
            span=f"{path.name}#/dag/edges/{i}",
            construct=json.dumps(edge, sort_keys=True)[:120],
        ))
    return Inventory("dag_json", path.name, tuple(constructs))


def inventory_file(path: Path) -> Inventory:
    suffix = path.suffix.lower()
    if suffix == ".mjs":
        return inventory_claude_mjs(path)
    doc_probe = json.loads(path.read_text(encoding="utf-8"))
    if "dag" in doc_probe:
        return inventory_dag_json(path)
    return inventory_codex_json(path)
