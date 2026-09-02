"""Shared fixture loader for IMP-0397 probes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
MONTH = "2026-07"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0397.json"
SCHEMA = REPO / "command-center" / "schema" / "router-telemetry.schema.json"
CONTRACT = HERE / "router-telemetry.contract.json"
SENTINEL = "SENTINEL:IMP-0397:ROUTER-TELEMETRY-SCRUBBED"

sys.path.insert(0, str(REPO / "tools"))
from router import telemetry as T  # noqa: E402


def planted() -> dict[str, str]:
    return json.loads((FIX / "planted.json").read_text(encoding="utf-8"))


def canaries() -> tuple[str, str]:
    doc = planted()
    return str(doc["secret"]), str(doc["abs_path"])


def load_events() -> list[dict]:
    rows = T.load_jsonl(FIX / "EVENTS.jsonl")
    rows.extend(T.load_events_from_dir(FIX / "event-ledger"))
    return rows


def load_indexed() -> list[str]:
    return T.load_capability_ids(FIX / "capability-index.json")


def live_report() -> dict:
    secret, abs_path = canaries()
    return T.month_report(
        load_events(),
        load_indexed(),
        REPO,
        month=MONTH,
        extra_canaries=(secret, abs_path),
    )
