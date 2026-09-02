"""Shared fixture constants for TST-0005 probes. Not a barrier."""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
ABSENT_PATH = "command-center/receipts/TST-0005-ABSENT-ORACLE.json"
CONVINCING_DIGEST = FIXTURES / "convincing-absent.digest.txt"


def load_convincing_digest() -> str:
    return CONVINCING_DIGEST.read_text(encoding="utf-8")
