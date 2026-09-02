"""Repo + tools/bench import path for TST-0299 probes."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

RECEIPT = REPO / "command-center" / "receipts" / "TST-0299.json"
LEDGER = REPO / "command-center" / "bench" / "results" / "TST-0299.jsonl"
SENTINEL = "SUCCESS:TST-0299"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
