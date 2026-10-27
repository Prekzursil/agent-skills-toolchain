"""Typed stage extraction from an imported workflow (IMP-0164)."""
from __future__ import annotations

import copy
from typing import Any

KIND_MAP = {
    "agent": "UNIT",
    "unit": "UNIT",
    "parallel": "FAN_OUT",
    "fanout": "FAN_OUT",
    "fan-out": "FAN_OUT",
    "fan_out": "FAN_OUT",
    "barrier": "BARRIER",
    "join": "BARRIER",
    "pipeline": "PIPELINE",
    "loop": "LOOP",
    "gate": "GATE",
    "subworkflow": "SUBWORKFLOW",
    "dynamic_fan_out": "DYNAMIC_FAN_OUT",
    "dynamic-fan-out": "DYNAMIC_FAN_OUT",
}

SCHEMA = "foundry.extracted-stages.v1"


def _span_ok(span: Any, source: str) -> bool:
    if not isinstance(span, dict):
        return False
    try:
        start = int(span["start"])
        end = int(span["end"])
    except (KeyError, TypeError, ValueError):
        return False
    if start < 0 or end < start or end > len(source):
        return False
    return True


def _fan_out_degree(node: dict[str, Any]) -> int | None:
    units = node.get("unit_ids")
    if isinstance(units, list):
        return len(units)
    width = node.get("width")
    if isinstance(width, int):
        return width
    return None


def extract_imported(
    imported: dict[str, Any],
    source: str,
    source_uri: str,
) -> dict[str, Any]:
    nodes = list(imported.get("nodes") or [])
    if not nodes:
        return {
            "id": imported.get("id"),
            "source_uri": source_uri,
            "schema": SCHEMA,
            "stages": None,
            "honest_null": True,
            "extracted_count": 0,
            "anchored_count": 0,
            "unanchored_ids": [],
            "span_coverage": 0.0,
            "span_coverage_formula": "anchored/extracted",
            "ok": False,
        }
    stages: list[dict[str, Any]] = []
    unanchored: list[str] = []
    anchored = 0
    for index, node in enumerate(nodes):
        native = str(node.get("kind") or "").strip().lower()
        kind = KIND_MAP.get(native, "UNKNOWN")
        span = node.get("source_span")
        ok_span = _span_ok(span, source)
        if ok_span:
            anchored += 1
        else:
            unanchored.append(str(node.get("id") or index))
        stage = {
            "index": index,
            "id": node.get("id"),
            "kind": kind,
            "native_kind": node.get("kind"),
            "fan_out_degree": _fan_out_degree(node) if kind == "FAN_OUT" else None,
            "gate": node.get("gate"),
            "inputs": list(node.get("inputs") or []),
            "outputs": list(node.get("outputs") or []),
            "source_span": span if ok_span else None,
            "source_uri": source_uri,
        }
        stages.append(stage)
    extracted = len(stages)
    coverage = anchored / extracted if extracted else 0.0
    return {
        "id": imported.get("id"),
        "source_uri": source_uri,
        "schema": SCHEMA,
        "stages": stages,
        "honest_null": False,
        "extracted_count": extracted,
        "anchored_count": anchored,
        "unanchored_ids": unanchored,
        "span_coverage": coverage,
        "span_coverage_formula": "anchored/extracted",
        "ok": extracted > 0 and not unanchored,
    }


def plant_unanchored(imported: dict[str, Any], stage_id: str) -> dict[str, Any]:
    clone = copy.deepcopy(imported)
    for node in clone.get("nodes") or []:
        if node.get("id") == stage_id:
            node.pop("source_span", None)
    return clone


def projection(extraction: dict[str, Any]) -> list[dict[str, Any]] | None:
    if extraction.get("honest_null") or extraction.get("stages") is None:
        return None
    rows = []
    for stage in extraction["stages"]:
        rows.append(
            {
                "index": stage["index"],
                "id": stage["id"],
                "kind": stage["kind"],
                "fan_out_degree": stage["fan_out_degree"],
                "gate": stage["gate"],
                "inputs": list(stage.get("inputs") or []),
                "outputs": list(stage.get("outputs") or []),
            }
        )
    return rows
