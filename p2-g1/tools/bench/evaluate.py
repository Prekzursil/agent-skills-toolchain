"""Deterministic per-cell evaluation."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from bench.cell import Cell


def evaluate_cell(cell: Cell | dict[str, Any]) -> dict[str, Any]:
    if isinstance(cell, dict):
        cid = str(cell.get("cell_id") or cell.get("id") or "")
        payload = cell.get("payload") or cell
    else:
        cid = cell.cell_id
        payload = cell.payload
    blob = json.dumps({"id": cid, "payload": payload}, sort_keys=True).encode()
    digest = hashlib.sha256(blob).hexdigest()
    score = int(digest[:8], 16) % 1000
    return {"score": score, "digest": digest, "cell_id": cid}
