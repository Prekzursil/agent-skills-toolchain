"""Resolve a DynamicFanOut node against a producer receipt."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agentspec.oracle import TAXONOMY_EMPTY_FANOUT, TAXONOMY_SEVERED_STREAM, is_progress_stream
from agentspec.spec import DynamicFanOut, UnitTemplate


@dataclass
class PlannedUnit:
    id: str
    item: Any
    prompt_ref: str = ""


@dataclass
class FanoutResult:
    verdict: str
    cardinality: int
    planned_units: tuple[PlannedUnit, ...]
    schema_validated: bool
    reason: str | None
    capped: bool = False
    source_cardinality: int = 0
    progress_stream: bool = False


def _get_path(doc: Any, path: str) -> Any:
    cur = doc
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def resolve_dynamic_fanout(
    node: DynamicFanOut,
    body: str | None,
    oracle: bool = False,
) -> FanoutResult:
    tmpl: UnitTemplate = node.unit_template
    progress = is_progress_stream(body or "")
    if oracle and progress:
        return FanoutResult(
            verdict="failed",
            cardinality=0,
            planned_units=(),
            schema_validated=False,
            reason=TAXONOMY_SEVERED_STREAM,
            progress_stream=True,
        )
    if body is None:
        return FanoutResult(
            verdict="failed",
            cardinality=0,
            planned_units=(),
            schema_validated=False,
            reason="receipt-missing",
        )
    try:
        doc = json.loads(body)
    except json.JSONDecodeError:
        return FanoutResult(
            verdict="failed",
            cardinality=0,
            planned_units=(),
            schema_validated=False,
            reason="receipt-unparseable",
            progress_stream=progress,
        )
    if not isinstance(doc, dict):
        return FanoutResult(
            verdict="failed",
            cardinality=0,
            planned_units=(),
            schema_validated=False,
            reason="receipt-unparseable",
        )
    items = _get_path(doc, node.item_path)
    if not isinstance(items, list):
        items = []
    source_n = len(items)
    capped = source_n > int(node.max_cardinality)
    used = items[: int(node.max_cardinality)]
    planned = tuple(
        PlannedUnit(id=f"{tmpl.id}:{i}", item=item, prompt_ref=tmpl.prompt_ref)
        for i, item in enumerate(used)
    )
    if not planned:
        return FanoutResult(
            verdict="empty-fanout",
            cardinality=0,
            planned_units=(),
            schema_validated=True,
            reason=TAXONOMY_EMPTY_FANOUT,
            source_cardinality=source_n,
            progress_stream=progress,
        )
    return FanoutResult(
        verdict="planned",
        cardinality=len(planned),
        planned_units=planned,
        schema_validated=True,
        reason=None,
        capped=capped,
        source_cardinality=source_n,
        progress_stream=progress,
    )
