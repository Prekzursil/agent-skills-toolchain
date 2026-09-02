"""Isolated command-center roots for CC-0013 probes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))

import status_ledger as sl  # noqa: E402


def populate_ledger(root: Path, *, events: list[dict], receipts: dict[str, dict]) -> Path:
    (root / "events").mkdir(parents=True, exist_ok=True)
    (root / "receipts").mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(ev, sort_keys=True, separators=(",", ":")) for ev in events]
    (root / "events" / "EVENTS.jsonl").write_text(
        ("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8", newline="\n"
    )
    for name, body in receipts.items():
        (root / "receipts" / name).write_text(
            json.dumps(body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return sl.write_status(root)


def sample_events() -> list[dict]:
    return [
        {"id": "R-X01", "ts": "2026-08-24T10:00:00Z", "verb": "open"},
        {"id": "R-X01", "ts": "2026-08-24T11:00:00Z", "verb": "note"},
        {"id": "R-X02", "ts": "2026-08-24T12:00:00Z", "verb": "open"},
    ]


def sample_receipts() -> dict[str, dict]:
    return {
        "R-X01.json": {"unit_id": "R-X01", "state": "SUCCESS"},
        "R-X02.json": {"unit_id": "R-X02", "state": "BLOCKED"},
    }
