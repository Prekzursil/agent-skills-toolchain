"""Stable paths and catalog strings for TST-0050."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0050"
OUT_REL = "command-center/receipts/TST-0050.json"
SCHEMA_REL = "command-center/schema/conformance-report.schema.json"
LOCAL_SCHEMA_REL = (
    "command-center/p2-wave/probes/TST-0050/conformance-report.schema.json"
)
CONTRACT_LIVE_REL = "command-center/phase4/contracts/ARC-0096.json"
CATALOG_SENTINEL = "SUCCESS:TST-0050"
QUESTION = (
    "Does any telemetry path emit a field not declared in the privacy "
    "contract, and is a credential-shaped or path-shaped value ever included?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0050/probe1_live_capture.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0050/probe2_both_states.py"
)
