"""Dispatch-integrity fan-in: reject fire-and-forget receipts before any digest is read."""
from __future__ import annotations

from .digest_reader import parse_events, read_digest, reset_parse_events
from .gate import evaluate_result
from .ledger import ledger_row_to_result, load_historical_ledger
from .pipeline import fan_in

__all__ = [
    "evaluate_result",
    "fan_in",
    "ledger_row_to_result",
    "load_historical_ledger",
    "parse_events",
    "read_digest",
    "reset_parse_events",
]
