"""Constants for TST-0107 spawn-budget measurement."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0107"
OUT_REL = "command-center/receipts/TST-0107.json"
SCHEMA_REL = "command-center/schema/benchmark-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0107"
DEBOUNCE_MS = 300
TIMEOUT_MS = 2000
NESTED_SPAWN_BUDGET = 0
SEED = 11022
COUNTED_HELPERS = (
    "jq",
    "git",
    "cut",
    "awk",
    "sed",
    "tput",
    "bash",
    "tst0107-probe",
)
QUESTION = (
    "Phase 10 layer 34 (:11022). Measured: the status line is debounced at "
    "300 ms and a slow render is CANCELLED, with a jq spawn at ~200 ms and a "
    "bare bash at ~350 ms - so process spawn count, not code, is the budget. "
    "Target: measure spawns per invocation by shimming PATH (never by grepping "
    "the script text) and enforce a budget."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0107/probe1_shim_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0107/probe2_budget_and_idle.py"
)
PAYLOAD = {
    "session_id": "tst-0107",
    "model": {"display_name": "fixture-model"},
    "context_window": {"used_percentage": 12.5},
    "workspace": {"current_dir": "/opt/p2/ast-integrate"},
}
