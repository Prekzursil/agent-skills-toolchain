#!/usr/bin/env python3
"""Shard-20 wave-4: dump remaining receipt schema $defs."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
spec = importlib.util.spec_from_file_location(
    "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
)
gate = importlib.util.module_from_spec(spec)
sys.modules["gate"] = gate
spec.loader.exec_module(gate)
defs = gate.load_schema().get("$defs", {})
for name in ("evidence_item", "probe_result", "test_result", "artifact",
             "downstream_consumer", "negative_control", "reviewer", "retry",
             "timestamps", "manifest_registration", "residual_unknown",
             "terminal_state", "sentinel", "unit_id"):
    print("=" * 20, name)
    print(json.dumps(defs.get(name), indent=1)[:2200])
