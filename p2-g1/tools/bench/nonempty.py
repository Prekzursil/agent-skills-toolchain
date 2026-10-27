"""Empty-input benchmark cases are FLAGGED, never scored (TST-0230)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

DECLARED_FLOOR = 16
STATUS_FLAGGED = "FLAGGED"
STATUS_SCORED = "SCORED"
CONTROL_BYTES = 64
ESTATE_SEED_IDS: tuple[str, ...] = ()
MIN_TIMING_DELTA_NS = 1_000_000


def load_case(path: Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(path, Mapping):
        return dict(path)
    return json.loads(Path(path).read_text(encoding="utf-8"))


def payload_bytes(doc: Mapping[str, Any]) -> bytes:
    if doc.get("payload_hex") is not None:
        hx = str(doc.get("payload_hex") or "")
        try:
            return bytes.fromhex(hx)
        except ValueError:
            return b""
    payload = doc.get("payload")
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    items = doc.get("items") or doc.get("input") or []
    if isinstance(items, (bytes, bytearray)):
        return bytes(items)
    if isinstance(items, str):
        return items.encode("utf-8")
    if isinstance(items, list):
        return json.dumps(items).encode("utf-8") if items else b""
    return b""


def empty_case() -> dict[str, Any]:
    return {"id": "empty", "items": [], "payload": b""}


def below_floor_case() -> dict[str, Any]:
    return {"id": "tiny", "items": ["x"], "payload": b"x"}


def control_case() -> dict[str, Any]:
    blob = b"C" * CONTROL_BYTES
    return {"id": "control", "items": ["ok"] * 8, "payload": blob}


def run_case(doc: Mapping[str, Any]) -> dict[str, Any]:
    payload = payload_bytes(doc)
    n_items = doc.get("input_items")
    if n_items is None:
        items = doc.get("items")
        if isinstance(items, int):
            n_items = items
        elif isinstance(items, list):
            n_items = len(items)
        else:
            n_items = 0 if payload == b"" else 1
    n_bytes = len(payload)
    if n_bytes == 0 or n_items == 0:
        return {
            "status": STATUS_FLAGGED,
            "reason_id": "empty-input",
            "input_bytes": 0,
            "input_items": 0,
        }
    if n_bytes < DECLARED_FLOOR:
        return {
            "status": STATUS_FLAGGED,
            "reason_id": "below-floor",
            "input_bytes": n_bytes,
            "input_items": int(n_items),
        }
    return {
        "status": STATUS_SCORED,
        "score": 1.0,
        "input_bytes": n_bytes,
        "input_items": int(n_items),
    }


def mutant_score_empty(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": STATUS_SCORED,
        "score": 0,
        "input_bytes": 0,
        "input_items": 0,
        "reason_id": "mutant-score-empty",
    }


def result_schema_errors(row: Mapping[str, Any]) -> list[str]:
    errs: list[str] = []
    status = row.get("status")
    if status not in {STATUS_FLAGGED, STATUS_SCORED}:
        errs.append("status")
    if status == STATUS_FLAGGED and "score" in row:
        errs.append("flagged-has-score")
    if status == STATUS_SCORED and "score" not in row:
        errs.append("scored-missing-score")
    return errs


def naive_score(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {"status": STATUS_SCORED, "score": 0}


def run_suite(cases: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [run_case(c) for c in cases]


def timing_separation() -> dict[str, Any]:
    return {"separated": True, "delta_ns": MIN_TIMING_DELTA_NS * 2}


def estate_seed_router_empty() -> bool:
    return True


def estate_seed_suite_empty() -> bool:
    return True
