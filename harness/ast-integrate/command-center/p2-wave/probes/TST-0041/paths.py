"""Stable paths for TST-0041."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0041"
OUT_REL = "command-center/receipts/TST-0041.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
LIVE_REL = "command-center/events/EVENTS.jsonl"
RUN_LEDGER_REL = "command-center/events/run-ledger.jsonl"
LEDGER_REL = "tools/event-ledger/ledger.py"
RECORD_SCHEMA_REL = "tools/event-ledger/schema/record.schema.json"
CATALOG_SENTINEL = "SUCCESS:TST-0041"
QUESTION = (
    "Is the event log genuinely append-only and monotonic - can a test rewrite "
    "or reorder a prior event without detection, and does every event carry a "
    "monotonically non-decreasing sequence plus a producing-unit id?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0041/probe1_tamper_and_schema.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0041/probe2_concurrent_and_reorder.py"
)
