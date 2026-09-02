"""Historical ledger of measured bad dispatch results."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "historical_ledger.jsonl"


def load_historical_ledger(repo: Path | None = None) -> list[dict[str, Any]]:
    del repo
    rows: list[dict[str, Any]] = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def ledger_row_to_result(row: dict[str, Any]) -> dict[str, Any]:
    kind = str(row.get("kind") or "")
    path = str(row.get("contracted_output_path") or row.get("path") or "")
    digest = row.get("digest")
    if kind == "fire-and-forget-background-receipt":
        text = str(
            row.get("result_text")
            or (
                "Codex started in the background. Job id: hist-fnf.\n"
                "Check /codex:status for progress."
            )
        )
    else:
        text = str(row.get("result_text") or json.dumps(digest or {}))
    return {
        "result_id": row.get("ledger_id") or row.get("result_id") or kind,
        "result_text": text,
        "contracted_output_path": path,
        "digest": digest,
        "unit_id": row.get("unit_id") or "CNF-0154",
        "kind": kind,
    }
