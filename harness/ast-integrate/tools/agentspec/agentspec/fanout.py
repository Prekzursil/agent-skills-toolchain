"""DynamicFanOut executor: oracle-gated producer receipts.

A DynamicFanOut node runs a PRODUCER whose receipt declares the units to fan
out to. The expansion is gated by :func:`agentspec.oracle.evaluate_producer`:
exit 0 with no usable receipt, or a body that is a progress/status stream,
expands to ZERO units and is classified ``severed-stream`` (the taxonomy
family) with the fine-grained cause in ``reason``. Nothing here trusts the
exit code or the presence of bytes on stdout.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from agentspec.oracle import TAXONOMY_SEVERED_STREAM, evaluate_producer, is_progress_stream

REASON_OK = "ok"
REASON_SCHEMA_INVALID = "schema-invalid"


@dataclass
class ProducerRun:
    exit_code: int
    stdout: str = ""
    receipt: dict[str, Any] | None = None
    receipt_path: str | None = None


def _refuse(reason: str, oracle: dict[str, Any], node_id: str | None, detail: str) -> dict[str, Any]:
    return {
        "cardinality": 0,
        "reason": reason,
        "taxonomy": TAXONOMY_SEVERED_STREAM,
        "units": [],
        "oracle": oracle,
        "node": node_id,
        "detail": detail,
    }


def _units_from_receipt(receipt: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    """Derive the unit list a receipt declares; ``(None, why)`` when it is not usable."""
    raw = receipt.get("units")
    declared = receipt.get("n", receipt.get("count"))
    if raw is None and declared is None:
        return None, "receipt declares neither units nor n"
    if raw is not None:
        if not isinstance(raw, list):
            return None, "receipt.units is not a list"
        units: list[dict[str, Any]] = []
        for i, item in enumerate(raw):
            if isinstance(item, dict):
                if not item.get("id"):
                    return None, f"receipt.units[{i}] has no id"
                units.append(dict(item))
            else:
                units.append({"id": str(item)})
    else:
        try:
            n = int(declared)
        except (TypeError, ValueError):
            return None, f"receipt.n is not an integer: {declared!r}"
        if n < 0:
            return None, f"receipt.n is negative: {n}"
        units = [{"id": f"u{i}"} for i in range(n)]
    if declared is not None:
        try:
            if int(declared) != len(units):
                return None, f"receipt.n={declared!r} disagrees with {len(units)} units"
        except (TypeError, ValueError):
            return None, f"receipt.n is not an integer: {declared!r}"
    ids = [u["id"] for u in units]
    if len(set(ids)) != len(ids):
        return None, "receipt.units carries duplicate ids"
    return units, ""


def expand_dynamic_fanout(run: ProducerRun, *, node: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expand a producer run into units, or refuse with a taxonomy-typed zero expansion."""
    node_id = None if node is None else node.get("id")
    oracle = evaluate_producer(run)
    if not oracle.get("ok"):
        reason = str(oracle.get("reason") or TAXONOMY_SEVERED_STREAM)
        return _refuse(reason, oracle, node_id, f"oracle refused the producer run: {reason}")

    receipt = run.receipt
    if not isinstance(receipt, dict):
        return _refuse(TAXONOMY_SEVERED_STREAM, oracle, node_id, "receipt is not an object")
    if is_progress_stream(json.dumps(receipt, sort_keys=True)):
        return _refuse("progress-stream", oracle, node_id, "the receipt body is a progress stream")

    units, why = _units_from_receipt(receipt)
    if units is None:
        return _refuse(REASON_SCHEMA_INVALID, oracle, node_id, why)
    return {
        "cardinality": len(units),
        "reason": REASON_OK,
        "taxonomy": None,
        "units": units,
        "oracle": oracle,
        "node": node_id,
        "detail": f"receipt declares {len(units)} unit(s)",
    }
